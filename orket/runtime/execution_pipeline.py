from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.exceptions import CardNotFound, ComplexityViolation
from orket.infrastructure.async_card_repository import AsyncCardRepository
from orket.infrastructure.async_repositories import (
    AsyncSessionRepository,
    AsyncSnapshotRepository,
    AsyncSuccessRepository,
)
from orket.logging import log_event
from orket.runtime.config_loader import ConfigLoader
from orket.schema import (
    CardStatus,
    EnvironmentConfig,
    EpicConfig,
    IssueConfig,
    RockConfig,
    TeamConfig,
)
from orket.utils import get_eos_sprint, sanitize_name


class ExecutionPipeline:
    """
    The central engine for Orket Unit execution.
    Load -> Validate -> Plan -> Execute -> Persist -> Report
    """

    def __init__(
        self,
        workspace: Path,
        department: str = "core",
        db_path: str = "orket_persistence.db",
        config_root: Optional[Path] = None,
        cards_repo: Optional[AsyncCardRepository] = None,
        sessions_repo: Optional[AsyncSessionRepository] = None,
        snapshots_repo: Optional[AsyncSnapshotRepository] = None,
        success_repo: Optional[AsyncSuccessRepository] = None,
        decision_nodes: Optional[DecisionNodeRegistry] = None,
    ):
        from orket.orchestration.notes import NoteStore

        self.workspace = workspace
        self.department = department
        self.decision_nodes = decision_nodes or DecisionNodeRegistry()
        self.config_root = config_root or Path(".").resolve()
        self.loader = ConfigLoader(self.config_root, department, decision_nodes=self.decision_nodes)
        self.db_path = db_path

        self.org = self.loader.load_organization()
        self.execution_runtime_node = self.decision_nodes.resolve_execution_runtime(self.org)
        self.pipeline_wiring_node = self.decision_nodes.resolve_pipeline_wiring(self.org)

        self.async_cards = cards_repo or AsyncCardRepository(self.db_path)
        self.sessions = sessions_repo or AsyncSessionRepository(self.db_path)
        self.snapshots = snapshots_repo or AsyncSnapshotRepository(self.db_path)
        self.success = success_repo or AsyncSuccessRepository(self.db_path)

        self.notes = NoteStore()
        self.transcript = []
        self.sandbox_orchestrator = self.pipeline_wiring_node.create_sandbox_orchestrator(
            workspace=self.workspace,
            organization=self.org,
        )
        self.webhook_db = self.pipeline_wiring_node.create_webhook_database()
        self.bug_fix_manager = self.pipeline_wiring_node.create_bug_fix_manager(
            organization=self.org,
            webhook_db=self.webhook_db,
        )
        self.orchestrator = self.pipeline_wiring_node.create_orchestrator(
            workspace=self.workspace,
            async_cards=self.async_cards,
            snapshots=self.snapshots,
            org=self.org,
            config_root=self.config_root,
            db_path=self.db_path,
            loader=self.loader,
            sandbox_orchestrator=self.sandbox_orchestrator,
        )

    async def run_card(self, card_id: str, **kwargs) -> Any:
        epics = await self.loader.list_assets_async("epics")
        if card_id in epics:
            return await self.run_epic(card_id, **kwargs)

        rocks = await self.loader.list_assets_async("rocks")
        if card_id in rocks:
            return await self.run_rock(card_id, **kwargs)

        parent_epic, parent_ename, _ = await self._find_parent_epic(card_id)
        if not parent_epic:
            raise CardNotFound(f"Card {card_id} not found.")
        print(f"  [PIPELINE] Executing Atomic Issue: {card_id} (Parent: {parent_epic.name})")
        return await self.run_epic(parent_ename, target_issue_id=card_id, **kwargs)

    async def run_epic(
        self,
        epic_name: str,
        build_id: str = None,
        session_id: str = None,
        driver_steered: bool = False,
        target_issue_id: str = None,
        **kwargs,
    ) -> List[Dict]:
        epic = await self.loader.load_asset_async("epics", epic_name, EpicConfig)
        team = await self.loader.load_asset_async("teams", epic.team, TeamConfig)
        env = await self.loader.load_asset_async("environments", epic.environment, EnvironmentConfig)

        threshold = 7
        if self.org and self.org.architecture:
            threshold = self.org.architecture.idesign_threshold

        if len(epic.issues) > threshold and not epic.architecture_governance.idesign:
            raise ComplexityViolation(
                f"Complexity Gate Violation: Epic '{epic.name}' has {len(epic.issues)} issues "
                f"which exceeds the threshold of {threshold}. iDesign structure is REQUIRED."
            )

        run_id = self.execution_runtime_node.select_run_id(session_id)
        active_build = self.execution_runtime_node.select_epic_build_id(build_id, epic_name, sanitize_name)

        if not await self.sessions.get_session(run_id):
            await self.sessions.start_session(
                run_id,
                {
                    "type": "epic",
                    "name": epic.name,
                    "department": self.department,
                    "task_input": epic.description,
                },
            )

        existing = await self.async_cards.get_by_build(active_build)
        if existing:
            if target_issue_id:
                if any(ex.id == target_issue_id for ex in existing):
                    await self.async_cards.update_status(target_issue_id, CardStatus.READY)
            else:
                await self.async_cards.reset_build(active_build)

        for issue in epic.issues:
            if not any(ex.id == issue.id for ex in existing):
                card_data = issue.model_dump(by_alias=True)
                card_data.update(
                    {
                        "session_id": run_id,
                        "build_id": active_build,
                        "sprint": get_eos_sprint(),
                        "status": CardStatus.READY,
                    }
                )
                await self.async_cards.save(card_data)

        log_event(
            "session_start",
            {"epic": epic.name, "run_id": run_id, "build_id": active_build},
            workspace=self.workspace,
        )

        await self.orchestrator.execute_epic(
            active_build=active_build,
            run_id=run_id,
            epic=epic,
            team=team,
            env=env,
            target_issue_id=target_issue_id,
        )

        self.transcript = self.orchestrator.transcript

        legacy_transcript = [
            {"step_index": i, "role": t.role, "issue": t.issue_id, "summary": t.content, "note": t.note}
            for i, t in enumerate(self.transcript)
        ]
        await self.sessions.complete_session(run_id, "done", legacy_transcript)
        log_event("session_end", {"run_id": run_id}, workspace=self.workspace)
        await self.snapshots.record(
            run_id,
            {"epic": epic.model_dump(), "team": team.model_dump(), "env": env.model_dump(), "build_id": active_build},
            legacy_transcript,
        )

        backlog = await self.async_cards.get_by_build(active_build)
        is_truly_done = all(i.status in [CardStatus.DONE, CardStatus.CANCELED] for i in backlog)
        if is_truly_done:
            await self.success.record_success(
                session_id=run_id,
                success_type="EPIC_COMPLETED",
                artifact_ref=f"build:{active_build}",
                human_ack=None,
            )
            log_event("success_recorded", {"run_id": run_id, "type": "EPIC_COMPLETED"}, workspace=self.workspace)

        root_log = Path("workspace/default/orket.log")
        if root_log.exists():
            await self.loader.file_tools.write_file("workspace/default/orket.log", "")

        return legacy_transcript

    async def run_rock(
        self,
        rock_name: str,
        build_id: str = None,
        session_id: str = None,
        driver_steered: bool = False,
        **kwargs,
    ) -> Dict:
        rock = await self.loader.load_asset_async("rocks", rock_name, RockConfig)
        sid = self.execution_runtime_node.select_rock_session_id(session_id)
        active_build = self.execution_runtime_node.select_rock_build_id(build_id, rock_name, sanitize_name)
        results = []
        for entry in rock.epics:
            epic_ws = self.workspace / entry["epic"]
            sub_pipeline = self.pipeline_wiring_node.create_sub_pipeline(
                parent_pipeline=self,
                epic_workspace=epic_ws,
                department=entry["department"],
            )
            res = await sub_pipeline.run_epic(
                entry["epic"],
                build_id=active_build,
                session_id=sid,
                driver_steered=driver_steered,
            )
            results.append({"epic": entry["epic"], "transcript": res})

        print(f"  [PHASE] Rock '{rock.name}' complete. Starting Bug Fix Phase...")
        await self.bug_fix_manager.start_phase(rock.id)

        return {"rock": rock.name, "results": results}

    async def _find_parent_epic(self, issue_id: str) -> tuple[EpicConfig | None, str | None, IssueConfig | None]:
        for ename in await self.loader.list_assets_async("epics"):
            try:
                epic = await self.loader.load_asset_async("epics", ename, EpicConfig)
                for issue in epic.issues:
                    if issue.id == issue_id:
                        return epic, ename, issue
            except (FileNotFoundError, ValueError, CardNotFound):
                continue
        return None, None, None

    async def verify_issue(self, issue_id: str) -> Any:
        return await self.orchestrator.verify_issue(issue_id)


async def orchestrate_card(card_id: str, workspace: Path, **kwargs) -> Any:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_card(card_id, **kwargs)


async def orchestrate(epic_name: str, workspace: Path, **kwargs) -> Any:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_epic(epic_name, **kwargs)


async def orchestrate_rock(rock_name: str, workspace: Path, **kwargs) -> Dict[str, Any]:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_rock(rock_name, **kwargs)
