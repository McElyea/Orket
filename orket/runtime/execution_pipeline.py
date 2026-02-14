from __future__ import annotations

from datetime import UTC, datetime
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.exceptions import CardNotFound, ComplexityViolation
from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.adapters.storage.async_repositories import (
    AsyncSessionRepository,
    AsyncSnapshotRepository,
    AsyncSuccessRepository,
    AsyncRunLedgerRepository,
)
from orket.adapters.vcs.gitea_artifact_exporter import GiteaArtifactExporter
from orket.logging import log_event
from orket.runtime.config_loader import ConfigLoader
from orket.runtime_paths import resolve_runtime_db_path
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
        db_path: Optional[str] = None,
        config_root: Optional[Path] = None,
        cards_repo: Optional[AsyncCardRepository] = None,
        sessions_repo: Optional[AsyncSessionRepository] = None,
        snapshots_repo: Optional[AsyncSnapshotRepository] = None,
        success_repo: Optional[AsyncSuccessRepository] = None,
        run_ledger_repo: Optional[AsyncRunLedgerRepository] = None,
        decision_nodes: Optional[DecisionNodeRegistry] = None,
    ):
        from orket.orchestration.notes import NoteStore

        self.workspace = workspace
        self.department = department
        self.decision_nodes = decision_nodes or DecisionNodeRegistry()
        self.config_root = config_root or Path(".").resolve()
        self.loader = ConfigLoader(self.config_root, department, decision_nodes=self.decision_nodes)
        self.db_path = resolve_runtime_db_path(db_path)

        self.org = self.loader.load_organization()
        self.execution_runtime_node = self.decision_nodes.resolve_execution_runtime(self.org)
        self.pipeline_wiring_node = self.decision_nodes.resolve_pipeline_wiring(self.org)

        self.async_cards = cards_repo or AsyncCardRepository(self.db_path)
        self.sessions = sessions_repo or AsyncSessionRepository(self.db_path)
        self.snapshots = snapshots_repo or AsyncSnapshotRepository(self.db_path)
        self.success = success_repo or AsyncSuccessRepository(self.db_path)
        self.run_ledger = run_ledger_repo or AsyncRunLedgerRepository(self.db_path)
        self.artifact_exporter = GiteaArtifactExporter(self.workspace)

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
        log_event(
            "pipeline_atomic_issue",
            {"card_id": card_id, "parent_epic": parent_epic.name},
            workspace=self.workspace,
        )
        return await self.run_epic(parent_ename, target_issue_id=card_id, **kwargs)

    def _resolve_idesign_mode(self) -> str:
        """
        Resolve iDesign policy mode from env override, then organization process rules.

        Supported modes:
        - force_idesign
        - force_none
        - architect_decides
        """
        raw = ""
        env_raw = (os.environ.get("ORKET_IDESIGN_MODE") or "").strip()
        if env_raw:
            raw = env_raw
        elif self.org and isinstance(getattr(self.org, "process_rules", None), dict):
            raw = str(self.org.process_rules.get("idesign_mode", "")).strip()

        normalized = raw.lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "force_idesign": "force_idesign",
            "force_i_design": "force_idesign",
            "force_none": "force_none",
            "force_nothing": "force_none",
            "none": "force_none",
            "architect_decides": "architect_decides",
            "architect_decide": "architect_decides",
            "let_architect_decide": "architect_decides",
        }
        return aliases.get(normalized, "architect_decides")

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

        idesign_mode = self._resolve_idesign_mode()
        issue_count = len(epic.issues)

        if idesign_mode == "force_idesign" and not epic.architecture_governance.idesign:
            raise ComplexityViolation(
                f"Complexity Gate Violation: iDesign policy is 'force_idesign' for epic '{epic.name}', "
                "but epic architecture_governance.idesign is false."
            )

        if idesign_mode == "architect_decides" and issue_count > threshold and not epic.architecture_governance.idesign:
            log_event(
                "idesign_architect_decision_respected",
                {
                    "epic": epic.name,
                    "issue_count": issue_count,
                    "idesign_threshold": threshold,
                    "idesign": False,
                },
                workspace=self.workspace,
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
        resume_mode = bool(target_issue_id) or any(
            issue.status in {CardStatus.IN_PROGRESS, CardStatus.CODE_REVIEW, CardStatus.AWAITING_GUARD_REVIEW}
            for issue in existing
        )
        if resume_mode:
            await self._resume_stalled_issues(existing, run_id, active_build)

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

        await self.run_ledger.start_run(
            session_id=run_id,
            run_type="epic",
            run_name=epic.name,
            department=self.department,
            build_id=active_build,
            summary={"target_issue_id": target_issue_id, "resume_mode": bool(resume_mode)},
            artifacts=self._run_artifact_refs(run_id),
        )

        workflow_terminal_statuses = {
            CardStatus.DONE,
            CardStatus.CANCELED,
            CardStatus.ARCHIVED,
            CardStatus.BLOCKED,
            CardStatus.GUARD_REJECTED,
            CardStatus.GUARD_APPROVED,
        }
        success_statuses = {CardStatus.DONE, CardStatus.CANCELED, CardStatus.ARCHIVED}

        legacy_transcript: List[Dict[str, Any]] = []
        backlog: List[Any] = []
        session_status = "failed"

        try:
            await self.orchestrator.execute_epic(
                active_build=active_build,
                run_id=run_id,
                epic=epic,
                team=team,
                env=env,
                target_issue_id=target_issue_id,
                resume_mode=resume_mode,
            )

            self.transcript = self.orchestrator.transcript
            legacy_transcript = [
                {"step_index": i, "role": t.role, "issue": t.issue_id, "summary": t.content, "note": t.note}
                for i, t in enumerate(self.transcript)
            ]
            backlog = await self.async_cards.get_by_build(active_build)

            is_workflow_terminal = all(i.status in workflow_terminal_statuses for i in backlog)
            is_success_terminal = all(i.status in success_statuses for i in backlog)
            if is_success_terminal:
                session_status = "done"
            elif is_workflow_terminal:
                session_status = "terminal_failure"
            else:
                session_status = "incomplete"

            await self.sessions.complete_session(run_id, session_status, legacy_transcript)
            log_event("session_end", {"run_id": run_id, "status": session_status}, workspace=self.workspace)
            if not is_workflow_terminal:
                non_terminal = [
                    {
                        "id": issue.id,
                        "status": issue.status.value if hasattr(issue.status, "value") else str(issue.status),
                    }
                    for issue in backlog
                    if issue.status not in workflow_terminal_statuses
                ]
                log_event(
                    "session_incomplete",
                    {"run_id": run_id, "build_id": active_build, "open_issues": non_terminal},
                    workspace=self.workspace,
                )
            elif session_status == "terminal_failure":
                terminal_failure = [
                    {
                        "id": issue.id,
                        "status": issue.status.value if hasattr(issue.status, "value") else str(issue.status),
                    }
                    for issue in backlog
                    if issue.status not in success_statuses
                ]
                log_event(
                    "session_terminal_failure",
                    {"run_id": run_id, "build_id": active_build, "issues": terminal_failure},
                    workspace=self.workspace,
                )
            await self.snapshots.record(
                run_id,
                {"epic": epic.model_dump(), "team": team.model_dump(), "env": env.model_dump(), "build_id": active_build},
                legacy_transcript,
            )

            if is_success_terminal:
                await self.success.record_success(
                    session_id=run_id,
                    success_type="EPIC_COMPLETED",
                    artifact_ref=f"build:{active_build}",
                    human_ack=None,
                )
                log_event("success_recorded", {"run_id": run_id, "type": "EPIC_COMPLETED"}, workspace=self.workspace)

            artifacts = self._run_artifact_refs(run_id)
            gitea_export = await self._export_run_artifacts(
                run_id=run_id,
                run_type="epic",
                run_name=epic.name,
                build_id=active_build,
                session_status=session_status,
                summary=self._build_run_summary(session_status=session_status, backlog=backlog, transcript=legacy_transcript),
            )
            if gitea_export:
                artifacts["gitea_export"] = gitea_export

            await self.run_ledger.finalize_run(
                session_id=run_id,
                status=session_status,
                summary=self._build_run_summary(session_status=session_status, backlog=backlog, transcript=legacy_transcript),
                artifacts=artifacts,
            )

        except Exception as exc:
            self.transcript = self.orchestrator.transcript
            legacy_transcript = [
                {"step_index": i, "role": t.role, "issue": t.issue_id, "summary": t.content, "note": t.note}
                for i, t in enumerate(self.transcript)
            ]
            try:
                backlog = await self.async_cards.get_by_build(active_build)
            except Exception:
                backlog = []

            await self.sessions.complete_session(run_id, "failed", legacy_transcript)
            log_event(
                "session_end",
                {"run_id": run_id, "status": "failed", "failure_class": type(exc).__name__},
                workspace=self.workspace,
            )
            failure_summary = self._build_run_summary(session_status="failed", backlog=backlog, transcript=legacy_transcript)
            artifacts = self._run_artifact_refs(run_id)
            gitea_export = await self._export_run_artifacts(
                run_id=run_id,
                run_type="epic",
                run_name=epic.name,
                build_id=active_build,
                session_status="failed",
                summary=failure_summary,
                failure_class=type(exc).__name__,
                failure_reason=str(exc)[:2000],
            )
            if gitea_export:
                artifacts["gitea_export"] = gitea_export
            await self.run_ledger.finalize_run(
                session_id=run_id,
                status="failed",
                failure_class=type(exc).__name__,
                failure_reason=str(exc)[:2000],
                summary=failure_summary,
                artifacts=artifacts,
            )
            raise

        root_log = Path("workspace/default/orket.log")
        if root_log.exists():
            await self.loader.file_tools.write_file("workspace/default/orket.log", "")

        return legacy_transcript

    def _run_artifact_refs(self, run_id: str) -> Dict[str, str]:
        return {
            "workspace": str(self.workspace),
            "orket_log": str(self.workspace / "orket.log"),
            "observability_root": str(self.workspace / "observability" / sanitize_name(run_id)),
            "agent_output_root": str(self.workspace / "agent_output"),
        }

    async def _export_run_artifacts(
        self,
        *,
        run_id: str,
        run_type: str,
        run_name: str,
        build_id: str,
        session_status: str,
        summary: Dict[str, Any],
        failure_class: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            exported = await self.artifact_exporter.export_run(
                run_id=run_id,
                run_type=run_type,
                run_name=run_name,
                build_id=build_id,
                session_status=session_status,
                summary=summary,
                failure_class=failure_class,
                failure_reason=failure_reason,
            )
            if exported:
                log_event(
                    "run_artifacts_exported",
                    {
                        "run_id": run_id,
                        "provider": exported.get("provider"),
                        "repo": f"{exported.get('owner')}/{exported.get('repo')}",
                        "branch": exported.get("branch"),
                        "path": exported.get("path"),
                        "commit": exported.get("commit"),
                    },
                    workspace=self.workspace,
                )
            return exported
        except Exception as exc:
            log_event(
                "run_artifact_export_failed",
                {
                    "run_id": run_id,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
                workspace=self.workspace,
            )
            return None

    def _build_run_summary(
        self,
        *,
        session_status: str,
        backlog: List[Any],
        transcript: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        status_counts: Dict[str, int] = {}
        for issue in backlog:
            status_key = issue.status.value if hasattr(issue.status, "value") else str(issue.status)
            status_counts[status_key] = status_counts.get(status_key, 0) + 1
        return {
            "session_status": session_status,
            "issue_count": len(backlog),
            "transcript_turns": len(transcript),
            "status_counts": status_counts,
        }

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

        log_event(
            "rock_phase_transition",
            {"rock": rock.name, "phase": "bug_fix"},
            workspace=self.workspace,
        )
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

    async def _resume_stalled_issues(self, issues: List[Any], run_id: str, active_build: str) -> None:
        stalled_states = {CardStatus.IN_PROGRESS, CardStatus.CODE_REVIEW, CardStatus.AWAITING_GUARD_REVIEW}
        for issue in issues:
            if issue.status in stalled_states:
                await self.async_cards.update_status(
                    issue.id,
                    CardStatus.READY,
                    reason="resume_requeue",
                    metadata={"run_id": run_id, "build_id": active_build, "previous_status": issue.status.value},
                )
                log_event(
                    "resume_requeue_issue",
                    {
                        "run_id": run_id,
                        "build_id": active_build,
                        "issue_id": issue.id,
                        "previous_status": issue.status.value,
                        "new_status": CardStatus.READY.value,
                    },
                    workspace=self.workspace,
                )

    async def verify_issue(self, issue_id: str) -> Any:
        return await self.orchestrator.verify_issue(issue_id)


async def orchestrate_card(card_id: str, workspace: Path, **kwargs) -> Any:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_card(card_id, **kwargs)


async def orchestrate(epic_name: str, workspace: Path, **kwargs) -> Any:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_epic(epic_name, **kwargs)


async def orchestrate_rock(rock_name: str, workspace: Path, **kwargs) -> Dict[str, Any]:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_rock(rock_name, **kwargs)

