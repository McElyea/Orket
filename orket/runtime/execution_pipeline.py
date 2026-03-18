from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles

from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.exceptions import CardNotFound, ComplexityViolation, ExecutionFailed
from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.adapters.storage.async_repositories import (
    AsyncSessionRepository,
    AsyncSnapshotRepository,
    AsyncSuccessRepository,
)
from orket.adapters.vcs.gitea_artifact_exporter import GiteaArtifactExporter
from orket.adapters.storage.gitea_state_adapter import GiteaStateAdapter
from orket.application.services.gitea_state_pilot import (
    collect_gitea_state_pilot_inputs,
    evaluate_gitea_state_pilot_readiness,
)
from orket.application.services.gitea_state_worker import GiteaStateWorker
from orket.application.services.gitea_state_worker_coordinator import GiteaStateWorkerCoordinator
from orket.application.services.runtime_policy import (
    resolve_gitea_worker_max_duration_seconds,
    resolve_gitea_worker_max_idle_streak,
    resolve_gitea_worker_max_iterations,
    resolve_gitea_state_pilot_enabled,
    resolve_run_ledger_mode,
    resolve_state_backend_mode,
)
from orket.application.workflows.protocol_hashing import hash_canonical_json
from orket.logging import log_event
from orket.runtime.config_loader import ConfigLoader
from orket.runtime.phase_c_runtime_truth import (
    collect_phase_c_packet2_facts,
    collect_source_attribution_facts,
    normalize_truthful_runtime_policy,
    resolve_source_attribution_gate_failure_reason,
)
from orket.runtime.protocol_receipt_materializer import materialize_protocol_receipts
from orket.runtime.route_decision_artifact import build_route_decision_artifact
from orket.runtime.run_ledger_factory import build_run_ledger_repository
from orket.runtime.run_summary import (
    PACKET1_MISSING_TOKEN,
    build_degraded_run_summary_payload,
    generate_run_summary_for_finalize,
    write_run_summary_artifact,
)
from orket.runtime.run_summary_artifact_provenance import normalize_artifact_provenance_facts
from orket.runtime.run_start_artifacts import capture_run_start_artifacts
from orket.runtime.deterministic_mode_contract import deterministic_mode_contract_snapshot
from orket.runtime.state_transition_registry import validate_state_token
from orket.runtime.workload_adapters import build_cards_workload_contract
from orket.runtime.workload_shell import SharedWorkloadShell
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
from orket.settings import load_user_settings


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
        run_ledger_repo: Optional[Any] = None,
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
        self.state_backend_mode = self._resolve_state_backend_mode()
        self.run_ledger_mode = self._resolve_run_ledger_mode()
        self.gitea_state_pilot_enabled = self._resolve_gitea_state_pilot_enabled()
        self._validate_state_backend_mode()
        self.execution_runtime_node = self.decision_nodes.resolve_execution_runtime(self.org)
        self.pipeline_wiring_node = self.decision_nodes.resolve_pipeline_wiring(self.org)

        self.async_cards = cards_repo or AsyncCardRepository(self.db_path)
        self.sessions = sessions_repo or AsyncSessionRepository(self.db_path)
        self.snapshots = snapshots_repo or AsyncSnapshotRepository(self.db_path)
        self.success = success_repo or AsyncSuccessRepository(self.db_path)
        if run_ledger_repo is not None:
            self.run_ledger = run_ledger_repo
        else:
            self.run_ledger = build_run_ledger_repository(
                mode=self.run_ledger_mode,
                db_path=self.db_path,
                workspace_root=self.workspace,
                telemetry_sink=self._emit_run_ledger_telemetry,
                primary_mode="sqlite",
            )
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
        setattr(self.orchestrator, "run_ledger", self.run_ledger)
        self.workload_shell = SharedWorkloadShell()

    def _resolve_state_backend_mode(self) -> str:
        env_raw = (os.environ.get("ORKET_STATE_BACKEND_MODE") or "").strip()
        process_raw = ""
        if self.org and isinstance(getattr(self.org, "process_rules", None), dict):
            process_raw = str(self.org.process_rules.get("state_backend_mode", "")).strip()
        user_raw = str(load_user_settings().get("state_backend_mode", "")).strip()
        return resolve_state_backend_mode(env_raw, process_raw, user_raw)

    def _resolve_run_ledger_mode(self) -> str:
        env_raw = (os.environ.get("ORKET_RUN_LEDGER_MODE") or "").strip()
        process_raw = ""
        if self.org and isinstance(getattr(self.org, "process_rules", None), dict):
            process_raw = str(self.org.process_rules.get("run_ledger_mode", "")).strip()
        user_raw = str(load_user_settings().get("run_ledger_mode", "")).strip()
        return resolve_run_ledger_mode(env_raw, process_raw, user_raw)

    def _validate_state_backend_mode(self) -> None:
        if self.state_backend_mode != "gitea":
            return
        # When backend mode is explicitly forced through env, require explicit env pilot
        # enablement as well to avoid hidden host/user setting leakage.
        env_mode = (os.environ.get("ORKET_STATE_BACKEND_MODE") or "").strip().lower()
        env_pilot_raw = (os.environ.get("ORKET_ENABLE_GITEA_STATE_PILOT") or "").strip()
        if env_mode == "gitea" and not env_pilot_raw:
            raise ValueError(
                "State backend mode 'gitea' requires pilot enablement "
                "(set ORKET_ENABLE_GITEA_STATE_PILOT=true or runtime policy gitea_state_pilot_enabled=true)."
            )
        if not self.gitea_state_pilot_enabled:
            raise ValueError(
                "State backend mode 'gitea' requires pilot enablement "
                "(set ORKET_ENABLE_GITEA_STATE_PILOT=true or runtime policy gitea_state_pilot_enabled=true)."
            )
        readiness = evaluate_gitea_state_pilot_readiness(collect_gitea_state_pilot_inputs())
        if not bool(readiness.get("ready")):
            failures = ", ".join(list(readiness.get("failures") or [])) or "unknown readiness failure"
            raise ValueError(f"State backend mode 'gitea' pilot readiness failed: {failures}")

    async def _emit_run_ledger_telemetry(self, payload: Dict[str, Any]) -> None:
        log_event(
            "run_ledger_telemetry",
            {
                "run_ledger_mode": self.run_ledger_mode,
                **dict(payload or {}),
            },
            workspace=self.workspace,
        )

    def _resolve_gitea_state_pilot_enabled(self) -> bool:
        env_raw = (os.environ.get("ORKET_ENABLE_GITEA_STATE_PILOT") or "").strip()
        process_raw = ""
        if self.org and isinstance(getattr(self.org, "process_rules", None), dict):
            process_raw = str(self.org.process_rules.get("gitea_state_pilot_enabled", "")).strip()
        user_raw = str(load_user_settings().get("gitea_state_pilot_enabled", "")).strip()
        return bool(resolve_gitea_state_pilot_enabled(env_raw, process_raw, user_raw))

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

    async def run_gitea_state_loop(
        self,
        *,
        worker_id: str,
        fetch_limit: int = 5,
        lease_seconds: int = 30,
        renew_interval_seconds: float = 5.0,
        max_iterations: int | None = None,
        max_idle_streak: int | None = None,
        max_duration_seconds: float | None = None,
        idle_sleep_seconds: float = 0.0,
        summary_out: str | Path | None = None,
    ) -> Dict[str, Any]:
        if self.state_backend_mode != "gitea":
            raise ValueError("run_gitea_state_loop requires state_backend_mode='gitea'")
        readiness = evaluate_gitea_state_pilot_readiness(collect_gitea_state_pilot_inputs())
        if not bool(readiness.get("ready")):
            failures = ", ".join(list(readiness.get("failures") or [])) or "unknown readiness failure"
            raise RuntimeError(f"State backend mode 'gitea' pilot readiness failed: {failures}")

        process_rules = getattr(self.org, "process_rules", {}) if self.org else {}
        user_settings = load_user_settings()
        effective_max_iterations = resolve_gitea_worker_max_iterations(
            max_iterations,
            os.environ.get("ORKET_GITEA_WORKER_MAX_ITERATIONS"),
            process_rules.get("gitea_worker_max_iterations"),
            user_settings.get("gitea_worker_max_iterations"),
        )
        effective_max_idle_streak = resolve_gitea_worker_max_idle_streak(
            max_idle_streak,
            os.environ.get("ORKET_GITEA_WORKER_MAX_IDLE_STREAK"),
            process_rules.get("gitea_worker_max_idle_streak"),
            user_settings.get("gitea_worker_max_idle_streak"),
        )
        effective_max_duration_seconds = resolve_gitea_worker_max_duration_seconds(
            max_duration_seconds,
            os.environ.get("ORKET_GITEA_WORKER_MAX_DURATION_SECONDS"),
            process_rules.get("gitea_worker_max_duration_seconds"),
            user_settings.get("gitea_worker_max_duration_seconds"),
        )

        inputs = collect_gitea_state_pilot_inputs()
        adapter = GiteaStateAdapter(
            base_url=str(inputs.get("gitea_url") or ""),
            token=str(inputs.get("gitea_token") or ""),
            owner=str(inputs.get("gitea_owner") or ""),
            repo=str(inputs.get("gitea_repo") or ""),
        )
        worker = GiteaStateWorker(
            adapter=adapter,
            worker_id=str(worker_id),
            lease_seconds=lease_seconds,
            renew_interval_seconds=renew_interval_seconds,
        )
        coordinator = GiteaStateWorkerCoordinator(
            worker=worker,
            fetch_limit=fetch_limit,
            max_iterations=effective_max_iterations,
            max_idle_streak=effective_max_idle_streak,
            max_duration_seconds=effective_max_duration_seconds,
            idle_sleep_seconds=idle_sleep_seconds,
        )

        async def _work_fn(card: Dict[str, Any]) -> Dict[str, Any]:
            target = str(card.get("card_id") or "").strip()
            if not target:
                raise ValueError("missing card_id in gitea snapshot payload")
            await self.run_card(target)
            return {"card_id": target, "result": "ok"}

        summary = await coordinator.run(work_fn=_work_fn, summary_out=summary_out)
        return {
            "worker_id": str(worker_id),
            "fetch_limit": max(1, int(fetch_limit)),
            "max_iterations": int(effective_max_iterations),
            "max_idle_streak": int(effective_max_idle_streak),
            "max_duration_seconds": float(effective_max_duration_seconds),
            "summary": summary,
        }

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
        # iDesign is backburnered by default; opt-in explicitly with ORKET_IDESIGN_MODE
        # or process_rules.idesign_mode when needed.
        return aliases.get(normalized, "force_none")

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
        epic_params = epic.params if isinstance(epic.params, dict) else {}
        phase_c_truth_policy = normalize_truthful_runtime_policy(epic_params.get("truthful_runtime"))

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
        cards_workload_contract = build_cards_workload_contract(
            epic=epic,
            run_id=run_id,
            build_id=active_build,
            workspace=self.workspace,
            department=self.department,
        )

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

        deterministic_mode_contract = deterministic_mode_contract_snapshot()
        route_decision_artifact = build_route_decision_artifact(
            run_id=run_id,
            workload_kind="epic",
            execution_runtime_node=self.execution_runtime_node,
            pipeline_wiring_node=self.pipeline_wiring_node,
            target_issue_id=target_issue_id,
            resume_mode=resume_mode,
            deterministic_mode_enabled=bool(deterministic_mode_contract.get("deterministic_mode_enabled")),
        )

        log_event(
            "session_start",
            {"epic": epic.name, "run_id": run_id, "build_id": active_build},
            workspace=self.workspace,
        )
        run_contract_artifacts = await asyncio.to_thread(
            capture_run_start_artifacts,
            workspace=self.workspace,
            run_id=run_id,
            workload=epic.name,
        )
        capability_manifest = run_contract_artifacts.get("capability_manifest")
        if isinstance(capability_manifest, dict):
            active_capabilities_allowed = [
                str(token).strip().lower()
                for token in (capability_manifest.get("capabilities_allowed") or [])
                if str(token).strip()
            ]
            active_run_determinism_class = (
                str(
                    capability_manifest.get("run_determinism_class")
                    or run_contract_artifacts.get("run_determinism_class")
                    or "workspace"
                )
                .strip()
                .lower()
            )
        else:
            active_capabilities_allowed = ["workspace"]
            active_run_determinism_class = (
                str(run_contract_artifacts.get("run_determinism_class") or "workspace").strip().lower()
            )
        if active_run_determinism_class not in {"pure", "workspace", "external"}:
            active_run_determinism_class = "workspace"
        compatibility_map_snapshot = run_contract_artifacts.get("compatibility_map_snapshot")
        if isinstance(compatibility_map_snapshot, dict):
            raw_mappings = compatibility_map_snapshot.get("mappings")
            raw_mappings = raw_mappings if isinstance(raw_mappings, dict) else {}
            active_compatibility_mappings = {
                str(tool_name).strip(): dict(mapping or {})
                for tool_name, mapping in raw_mappings.items()
                if str(tool_name).strip() and isinstance(mapping, dict)
            }
        else:
            active_compatibility_mappings = {}
        self.orchestrator.active_capabilities_allowed = active_capabilities_allowed or ["workspace"]
        self.orchestrator.active_run_determinism_class = active_run_determinism_class
        self.orchestrator.active_compatibility_mappings = active_compatibility_mappings

        await self.run_ledger.start_run(
            session_id=run_id,
            run_type="epic",
            run_name=epic.name,
            department=self.department,
            build_id=active_build,
            artifacts={
                **self._run_artifact_refs(run_id),
                **dict(run_contract_artifacts),
                "deterministic_mode_contract": dict(deterministic_mode_contract),
                "route_decision_artifact": dict(route_decision_artifact),
                "packet1_facts": self._build_packet1_facts(intended_model=env.model),
            },
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

            async def _execute_cards_workload(_contract):
                await self.orchestrator.execute_epic(
                    active_build=active_build,
                    run_id=run_id,
                    epic=epic,
                    team=team,
                    env=env,
                    target_issue_id=target_issue_id,
                    resume_mode=resume_mode,
                )
                return None

            await self.workload_shell.execute(
                contract_payload=cards_workload_contract,
                execute_fn=_execute_cards_workload,
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
            session_status = validate_state_token(domain="session", state=session_status)

            failure_reason = None
            artifacts = self._run_artifact_refs(run_id)
            artifacts.update(dict(run_contract_artifacts))
            artifacts["deterministic_mode_contract"] = dict(deterministic_mode_contract)
            artifacts["route_decision_artifact"] = dict(route_decision_artifact)
            artifacts["packet1_facts"] = self._build_packet1_facts(intended_model=env.model)
            receipt_projection = await self._materialize_protocol_receipts(run_id=run_id)
            if receipt_projection:
                artifacts["protocol_receipts"] = receipt_projection
            source_attribution_facts = await collect_source_attribution_facts(
                workspace=self.workspace,
                policy=phase_c_truth_policy,
            )
            gate_failure_reason = resolve_source_attribution_gate_failure_reason(source_attribution_facts)
            if session_status == "done" and gate_failure_reason is not None:
                session_status = validate_state_token(domain="session", state="terminal_failure")
                failure_reason = gate_failure_reason
                log_event(
                    "source_attribution_gate_blocked",
                    {
                        "run_id": run_id,
                        "failure_reason": failure_reason,
                        "mode": source_attribution_facts.get("mode"),
                        "missing_requirements": list(source_attribution_facts.get("missing_requirements") or []),
                    },
                    workspace=self.workspace,
                )

            await self.sessions.complete_session(run_id, session_status, legacy_transcript)
            session_end_payload = {"run_id": run_id, "status": session_status}
            if failure_reason is not None:
                session_end_payload["failure_reason"] = failure_reason
            log_event("session_end", session_end_payload, workspace=self.workspace)
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
                    {
                        "run_id": run_id,
                        "build_id": active_build,
                        "issues": terminal_failure,
                        "failure_reason": failure_reason,
                    },
                    workspace=self.workspace,
                )
            await self.snapshots.record(
                run_id,
                {
                    "epic": epic.model_dump(),
                    "team": team.model_dump(),
                    "env": env.model_dump(),
                    "build_id": active_build,
                },
                legacy_transcript,
            )

            if session_status == "done":
                await self.success.record_success(
                    session_id=run_id,
                    success_type="EPIC_COMPLETED",
                    artifact_ref=f"build:{active_build}",
                    human_ack=None,
                )
                log_event("success_recorded", {"run_id": run_id, "type": "EPIC_COMPLETED"}, workspace=self.workspace)

            summary_finalized_at = datetime.now(UTC).isoformat()
            run_summary, artifacts = await self._materialize_run_summary(
                run_id=run_id,
                session_status=session_status,
                failure_reason=failure_reason,
                artifacts=artifacts,
                finalized_at=summary_finalized_at,
                phase_c_truth_policy=phase_c_truth_policy,
            )
            gitea_export = await self._export_run_artifacts(
                run_id=run_id,
                run_type="epic",
                run_name=epic.name,
                build_id=active_build,
                session_status=session_status,
                summary=run_summary,
                failure_reason=failure_reason,
            )
            if gitea_export:
                artifacts["gitea_export"] = gitea_export

            ledger_finalized_at = datetime.now(UTC).isoformat()
            await self.run_ledger.finalize_run(
                session_id=run_id,
                status=session_status,
                failure_reason=failure_reason,
                summary=run_summary,
                artifacts=artifacts,
                finalized_at=ledger_finalized_at,
            )

        except (
            CardNotFound,
            ComplexityViolation,
            ExecutionFailed,
            RuntimeError,
            ValueError,
            TypeError,
            OSError,
            asyncio.TimeoutError,
        ) as exc:
            self.transcript = self.orchestrator.transcript
            legacy_transcript = [
                {"step_index": i, "role": t.role, "issue": t.issue_id, "summary": t.content, "note": t.note}
                for i, t in enumerate(self.transcript)
            ]
            try:
                backlog = await self.async_cards.get_by_build(active_build)
            except (RuntimeError, ValueError, TypeError, OSError):
                backlog = []

            failed_status = validate_state_token(domain="session", state="failed")
            await self.sessions.complete_session(run_id, failed_status, legacy_transcript)
            log_event(
                "session_end",
                {"run_id": run_id, "status": failed_status, "failure_class": type(exc).__name__},
                workspace=self.workspace,
            )
            artifacts = self._run_artifact_refs(run_id)
            artifacts.update(dict(run_contract_artifacts))
            artifacts["deterministic_mode_contract"] = dict(deterministic_mode_contract)
            artifacts["route_decision_artifact"] = dict(route_decision_artifact)
            artifacts["packet1_facts"] = self._build_packet1_facts(intended_model=env.model)
            receipt_projection = await self._materialize_protocol_receipts(run_id=run_id)
            if receipt_projection:
                artifacts["protocol_receipts"] = receipt_projection
            summary_finalized_at = datetime.now(UTC).isoformat()
            failure_summary, artifacts = await self._materialize_run_summary(
                run_id=run_id,
                session_status=failed_status,
                failure_reason=str(exc)[:2000],
                artifacts=artifacts,
                finalized_at=summary_finalized_at,
                phase_c_truth_policy=phase_c_truth_policy,
            )
            gitea_export = await self._export_run_artifacts(
                run_id=run_id,
                run_type="epic",
                run_name=epic.name,
                build_id=active_build,
                session_status=failed_status,
                summary=failure_summary,
                failure_class=type(exc).__name__,
                failure_reason=str(exc)[:2000],
            )
            if gitea_export:
                artifacts["gitea_export"] = gitea_export
            ledger_finalized_at = datetime.now(UTC).isoformat()
            await self.run_ledger.finalize_run(
                session_id=run_id,
                status=failed_status,
                failure_class=type(exc).__name__,
                failure_reason=str(exc)[:2000],
                summary=failure_summary,
                artifacts=artifacts,
                finalized_at=ledger_finalized_at,
            )
            raise

        return legacy_transcript

    def _run_artifact_refs(self, run_id: str) -> Dict[str, str]:
        return {
            "workspace": str(self.workspace),
            "orket_log": str(self.workspace / "orket.log"),
            "observability_root": str(self.workspace / "observability" / sanitize_name(run_id)),
            "agent_output_root": str(self.workspace / "agent_output"),
        }

    def _build_packet1_facts(
        self,
        *,
        intended_model: str | None,
        runtime_telemetry: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        provider = (
            str(os.environ.get("ORKET_LLM_PROVIDER") or os.environ.get("ORKET_MODEL_PROVIDER") or "ollama")
            .strip()
            .lower()
        )
        configured_profile = self._normalize_packet1_token(os.environ.get("ORKET_LOCAL_PROMPTING_PROFILE_ID"))
        fallback_profile = self._normalize_packet1_token(os.environ.get("ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID"))
        telemetry = dict(runtime_telemetry or {})
        intended_model_token = self._normalize_packet1_token(intended_model) or self._normalize_packet1_token(
            telemetry.get("requested_model")
        )
        actual_provider = (
            str(
                telemetry.get("provider_backend")
                or telemetry.get("provider_name")
                or telemetry.get("provider")
                or provider
            )
            .strip()
            .lower()
            or provider
        )
        actual_model = (
            self._normalize_packet1_token(telemetry.get("model")) or intended_model_token or PACKET1_MISSING_TOKEN
        )
        actual_profile = self._normalize_packet1_token(telemetry.get("profile_id")) or "default"
        resolution_path = str(telemetry.get("profile_resolution_path") or "").strip().lower()
        fallback_detected = resolution_path == "fallback"
        retry_count = telemetry.get("retries")
        retry_occurred = isinstance(retry_count, int) and retry_count > 0
        intended_profile = configured_profile or (fallback_profile if fallback_detected else "") or actual_profile
        return {
            "intended_provider": provider,
            "intended_model": intended_model_token or PACKET1_MISSING_TOKEN,
            "intended_profile": intended_profile or PACKET1_MISSING_TOKEN,
            "actual_provider": actual_provider,
            "actual_model": actual_model,
            "actual_profile": actual_profile,
            "path_mismatch": False,
            "mismatch_reason": "none",
            "retry_occurred": retry_occurred,
            "repair_occurred": False,
            "fallback_occurred": fallback_detected,
            "fallback_path_detected": fallback_detected,
            "machine_mismatch_indicator": True,
            "output_presented_as_normal_success": True,
            "execution_profile": "fallback" if fallback_detected else "normal",
        }

    @staticmethod
    def _normalize_packet1_token(value: Any) -> str:
        if value is None:
            return ""
        raw = str(value).strip()
        if not raw or raw.lower() in {"none", "unknown"}:
            return ""
        return raw

    def _merge_packet1_facts(
        self,
        existing_packet1_facts: Dict[str, Any],
        updated_packet1_facts: Dict[str, Any],
    ) -> Dict[str, Any]:
        merged = dict(existing_packet1_facts)
        for key, value in updated_packet1_facts.items():
            if key in {
                "intended_provider",
                "intended_model",
                "intended_profile",
                "actual_provider",
                "actual_model",
                "actual_profile",
            }:
                if str(value).strip() == PACKET1_MISSING_TOKEN and self._normalize_packet1_token(
                    existing_packet1_facts.get(key)
                ):
                    continue
            merged[key] = value
        return merged

    def _select_primary_work_artifact_output(
        self,
        *,
        artifact_provenance_facts: Dict[str, Any] | None = None,
    ) -> Dict[str, str]:
        facts = normalize_artifact_provenance_facts(artifact_provenance_facts)
        entries = list(facts.get("artifacts") or [])
        entries = [
            entry for entry in entries if str(entry.get("artifact_type") or "").strip() != "source_attribution_receipt"
        ]
        if not entries:
            return {}
        selected = max(
            entries,
            key=lambda entry: (
                int(entry.get("turn_index") or 0),
                str(entry.get("produced_at") or ""),
                str(entry.get("artifact_path") or ""),
            ),
        )
        artifact_path = str(selected.get("artifact_path") or "").strip()
        if not artifact_path:
            return {}
        return {"id": artifact_path, "kind": "artifact"}

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
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
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

    async def _materialize_run_summary(
        self,
        *,
        run_id: str,
        session_status: str,
        failure_reason: str | None,
        artifacts: Dict[str, Any],
        finalized_at: str,
        phase_c_truth_policy: Dict[str, Any] | None = None,
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        resolved_artifacts = dict(artifacts)
        repair_entries = await self._resolve_packet2_repair_entries(run_id=run_id)
        artifact_provenance_artifacts = await self._resolve_artifact_provenance_artifacts(run_id=run_id)
        packet1_artifacts = await self._resolve_packet1_artifacts(
            run_id=run_id,
            repair_entries=repair_entries,
            artifact_provenance_facts=artifact_provenance_artifacts.get("artifact_provenance_facts"),
        )
        packet2_artifacts = await self._resolve_packet2_artifacts(
            run_id=run_id,
            repair_entries=repair_entries,
            artifact_provenance_facts=artifact_provenance_artifacts.get("artifact_provenance_facts"),
            phase_c_truth_policy=phase_c_truth_policy,
        )
        existing_packet1_facts = dict(resolved_artifacts.get("packet1_facts") or {})
        merged_packet1_facts = self._merge_packet1_facts(
            existing_packet1_facts,
            dict(packet1_artifacts.get("packet1_facts") or {}),
        )
        if merged_packet1_facts:
            resolved_artifacts["packet1_facts"] = merged_packet1_facts
        existing_packet2_facts = dict(resolved_artifacts.get("packet2_facts") or {})
        merged_packet2_facts = {
            **existing_packet2_facts,
            **dict(packet2_artifacts.get("packet2_facts") or {}),
        }
        if merged_packet2_facts:
            resolved_artifacts["packet2_facts"] = merged_packet2_facts
        existing_artifact_provenance_facts = normalize_artifact_provenance_facts(
            resolved_artifacts.get("artifact_provenance_facts")
        )
        merged_artifact_provenance_facts = {
            **existing_artifact_provenance_facts,
            **normalize_artifact_provenance_facts(artifact_provenance_artifacts.get("artifact_provenance_facts")),
        }
        if merged_artifact_provenance_facts:
            resolved_artifacts["artifact_provenance_facts"] = merged_artifact_provenance_facts
        runtime_verification_path = str(packet1_artifacts.get("runtime_verification_path") or "").strip()
        if runtime_verification_path:
            resolved_artifacts["runtime_verification_path"] = runtime_verification_path
        run_identity = resolved_artifacts.get("run_identity")
        started_at = None
        if isinstance(run_identity, dict):
            started_at = str(run_identity.get("start_time") or "").strip() or None
        try:
            run_summary = await generate_run_summary_for_finalize(
                workspace=self.workspace,
                run_id=run_id,
                status=session_status,
                failure_reason=failure_reason,
                started_at=started_at,
                ended_at=finalized_at,
                artifacts=resolved_artifacts,
            )
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            resolved_artifacts["run_summary_generation_error"] = {
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            await self._record_packet1_emission_failure(
                run_id=run_id,
                stage="generation",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            log_event(
                "run_summary_generation_failed",
                {"run_id": run_id, "error_type": type(exc).__name__, "error": str(exc)},
                workspace=self.workspace,
            )
            run_summary = build_degraded_run_summary_payload(
                run_id=run_id,
                status=session_status,
                failure_reason=failure_reason,
                artifacts=resolved_artifacts,
            )
        try:
            run_summary_path = await write_run_summary_artifact(
                root=self.workspace,
                session_id=run_id,
                payload=run_summary,
            )
            resolved_artifacts["run_summary_path"] = str(run_summary_path)
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            await self._record_packet1_emission_failure(
                run_id=run_id,
                stage="write",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            log_event(
                "run_summary_artifact_write_failed",
                {"run_id": run_id, "error_type": type(exc).__name__, "error": str(exc)},
                workspace=self.workspace,
            )
        resolved_artifacts["run_summary"] = dict(run_summary)
        return run_summary, resolved_artifacts

    async def _resolve_packet1_artifacts(
        self,
        *,
        run_id: str,
        repair_entries: List[Dict[str, Any]] | None = None,
        artifact_provenance_facts: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        runtime_verification_path = self.workspace / "agent_output" / "verification" / "runtime_verification.json"
        runtime_telemetry = await self._resolve_packet1_runtime_telemetry(run_id=run_id)
        repair_facts = self._build_packet1_repair_facts(repair_entries or [])
        packet1_facts = {
            **self._build_packet1_facts(intended_model=None, runtime_telemetry=runtime_telemetry),
            **repair_facts,
        }
        primary_work_artifact = self._select_primary_work_artifact_output(
            artifact_provenance_facts=artifact_provenance_facts
        )
        if primary_work_artifact:
            packet1_facts["primary_work_artifact_output"] = primary_work_artifact
        if runtime_verification_path.exists():
            if "primary_work_artifact_output" not in packet1_facts:
                packet1_facts["primary_artifact_output"] = {
                    "id": "agent_output/verification/runtime_verification.json",
                    "kind": "artifact",
                }
            return {
                "runtime_verification_path": str(runtime_verification_path),
                "packet1_facts": packet1_facts,
            }
        return {"packet1_facts": packet1_facts}

    async def _resolve_packet2_artifacts(
        self,
        *,
        run_id: str,
        repair_entries: List[Dict[str, Any]] | None = None,
        artifact_provenance_facts: Dict[str, Any] | None = None,
        phase_c_truth_policy: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        packet2_facts = await collect_phase_c_packet2_facts(
            workspace=self.workspace,
            run_id=run_id,
            cards_repo=self.async_cards,
            policy=phase_c_truth_policy,
            artifact_provenance_facts=artifact_provenance_facts,
        )
        packet2_facts.update(self._build_packet2_facts(repair_entries=repair_entries or []))
        if not packet2_facts:
            return {}
        await self._record_packet2_facts(run_id=run_id, packet2_facts=packet2_facts)
        return {"packet2_facts": packet2_facts}

    async def _resolve_artifact_provenance_artifacts(self, *, run_id: str) -> Dict[str, Any]:
        entries = await self._resolve_artifact_provenance_entries(run_id=run_id)
        artifact_provenance_facts = self._build_artifact_provenance_facts(entries=entries)
        if not artifact_provenance_facts:
            return {}
        await self._record_artifact_provenance_facts(
            run_id=run_id,
            artifact_provenance_facts=artifact_provenance_facts,
        )
        return {"artifact_provenance_facts": artifact_provenance_facts}

    async def _resolve_packet1_runtime_telemetry(self, *, run_id: str) -> Dict[str, Any]:
        candidate_paths = await asyncio.to_thread(self._packet1_model_response_paths, run_id)
        selected: Dict[str, Any] = {}
        for path in candidate_paths:
            try:
                async with aiofiles.open(path, mode="r", encoding="utf-8") as handle:
                    payload = json.loads(await handle.read())
            except (OSError, ValueError, TypeError):
                continue
            if not isinstance(payload, dict):
                continue
            selected = payload
        return selected

    async def _resolve_packet2_repair_entries(self, *, run_id: str) -> List[Dict[str, Any]]:
        log_path = self.workspace / "orket.log"
        if not log_path.exists():
            return []
        repairs_by_id: Dict[str, Dict[str, Any]] = {}
        try:
            async with aiofiles.open(log_path, mode="r", encoding="utf-8") as handle:
                async for line in handle:
                    if not line.strip():
                        continue
                    try:
                        payload = json.loads(line)
                    except (ValueError, TypeError):
                        continue
                    if not isinstance(payload, dict):
                        continue
                    if str(payload.get("event") or "").strip() != "turn_corrective_reprompt":
                        continue
                    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
                    if str(data.get("session_id") or "").strip() != str(run_id):
                        continue
                    reasons = sorted(
                        {str(reason).strip() for reason in (data.get("contract_reasons") or []) if str(reason).strip()}
                    )
                    if not reasons:
                        continue
                    issue_id = str(data.get("issue_id") or "").strip()
                    turn_index_raw = data.get("turn_index")
                    turn_index = max(0, int(turn_index_raw)) if isinstance(turn_index_raw, int) else 0
                    repair_id = (
                        f"repair:{issue_id}:{turn_index}:corrective_reprompt"
                        if issue_id
                        else f"repair:turn:{turn_index}:corrective_reprompt"
                    )
                    existing = repairs_by_id.get(repair_id)
                    if existing is None:
                        entry: Dict[str, Any] = {
                            "repair_id": repair_id,
                            "turn_index": turn_index,
                            "source_event": "turn_corrective_reprompt",
                            "strategy": "corrective_reprompt",
                            "reasons": reasons,
                            "material_change": True,
                        }
                        if issue_id:
                            entry["issue_id"] = issue_id
                        repairs_by_id[repair_id] = entry
                        continue
                    existing["reasons"] = sorted(set(list(existing.get("reasons") or []) + reasons))
        except OSError:
            return []
        return [repairs_by_id[key] for key in sorted(repairs_by_id)]

    async def _resolve_artifact_provenance_entries(self, *, run_id: str) -> List[Dict[str, Any]]:
        receipt_entries = await self._resolve_artifact_provenance_entries_from_receipts(run_id=run_id)
        artifacts_by_path: Dict[str, Dict[str, Any]] = {
            str(entry["artifact_path"]): dict(entry) for entry in receipt_entries
        }
        log_entries = await self._resolve_artifact_provenance_entries_from_logs(
            run_id=run_id,
            existing_paths=set(artifacts_by_path),
        )
        for entry in log_entries:
            artifacts_by_path[str(entry["artifact_path"])] = dict(entry)
        return [artifacts_by_path[key] for key in sorted(artifacts_by_path)]

    async def _resolve_artifact_provenance_entries_from_receipts(self, *, run_id: str) -> List[Dict[str, Any]]:
        receipt_paths = await asyncio.to_thread(self._artifact_provenance_receipt_paths, run_id)
        artifacts_by_path: Dict[str, Dict[str, Any]] = {}
        for receipt_path in receipt_paths:
            issue_id, role_name, turn_index = self._artifact_provenance_receipt_context(
                receipt_path=receipt_path,
                run_id=run_id,
            )
            try:
                async with aiofiles.open(receipt_path, mode="r", encoding="utf-8") as handle:
                    async for line in handle:
                        if not line.strip():
                            continue
                        try:
                            payload = json.loads(line)
                        except (ValueError, TypeError):
                            continue
                        if not isinstance(payload, dict):
                            continue
                        entry = await self._artifact_provenance_entry_from_receipt(
                            receipt=payload,
                            issue_id=issue_id,
                            role_name=role_name,
                            turn_index=turn_index,
                        )
                        if entry is not None:
                            artifacts_by_path[str(entry["artifact_path"])] = entry
            except OSError:
                continue
        return [artifacts_by_path[key] for key in sorted(artifacts_by_path)]

    async def _resolve_artifact_provenance_entries_from_logs(
        self,
        *,
        run_id: str,
        existing_paths: set[str],
    ) -> List[Dict[str, Any]]:
        log_path = self.workspace / "orket.log"
        if not log_path.exists():
            return []
        starts_by_operation: Dict[str, Dict[str, Any]] = {}
        artifacts_by_path: Dict[str, Dict[str, Any]] = {}
        try:
            async with aiofiles.open(log_path, mode="r", encoding="utf-8") as handle:
                async for line in handle:
                    if not line.strip():
                        continue
                    try:
                        payload = json.loads(line)
                    except (ValueError, TypeError):
                        continue
                    if not isinstance(payload, dict):
                        continue
                    event_name = str(payload.get("event") or "").strip()
                    if event_name not in {"tool_call_start", "tool_call_result"}:
                        continue
                    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
                    if str(data.get("session_id") or "").strip() != str(run_id):
                        continue
                    operation_id = str(data.get("operation_id") or "").strip()
                    if not operation_id:
                        continue
                    if event_name == "tool_call_start":
                        if str(data.get("tool") or "").strip() != "write_file":
                            continue
                        starts_by_operation[operation_id] = {
                            "issue_id": str(data.get("issue_id") or "").strip(),
                            "role_name": str(data.get("role") or payload.get("role") or "").strip(),
                            "turn_index": int(data.get("turn_index") or 0),
                            "tool_args": dict(data.get("args") or {}) if isinstance(data.get("args"), dict) else {},
                        }
                        continue
                    if not bool(data.get("ok")):
                        continue
                    start = starts_by_operation.get(operation_id)
                    if start is None:
                        continue
                    entry = await self._artifact_provenance_entry_from_log_pair(
                        run_id=run_id,
                        operation_id=operation_id,
                        start=start,
                    )
                    if entry is None:
                        continue
                    artifact_path = str(entry.get("artifact_path") or "")
                    if artifact_path in existing_paths:
                        continue
                    artifacts_by_path[artifact_path] = entry
        except OSError:
            return []
        return [artifacts_by_path[key] for key in sorted(artifacts_by_path)]

    async def _artifact_provenance_entry_from_receipt(
        self,
        *,
        receipt: Dict[str, Any],
        issue_id: str,
        role_name: str,
        turn_index: int,
    ) -> Dict[str, Any] | None:
        if str(receipt.get("tool") or "").strip() != "write_file":
            return None
        execution_result = receipt.get("execution_result")
        if not isinstance(execution_result, dict) or not bool(execution_result.get("ok")):
            return None
        artifact_location = await asyncio.to_thread(
            self._resolve_workspace_artifact_location,
            execution_result,
            receipt,
        )
        if artifact_location is None:
            return None
        artifact_path, resolved_artifact_path = artifact_location
        source_hash = str(receipt.get("receipt_digest") or receipt.get("tool_call_hash") or "").strip()
        if not source_hash:
            return None
        produced_at = await asyncio.to_thread(self._artifact_produced_at, resolved_artifact_path)
        if not produced_at:
            return None
        manifest = (
            dict(receipt.get("tool_invocation_manifest") or {})
            if isinstance(receipt.get("tool_invocation_manifest"), dict)
            else {}
        )
        entry: Dict[str, Any] = {
            "artifact_path": artifact_path,
            "artifact_type": self._artifact_type_for_path(artifact_path),
            "generator": "tool.write_file",
            "generator_version": str(manifest.get("tool_contract_version") or "1.0.0"),
            "source_hash": source_hash,
            "produced_at": produced_at,
            "truth_classification": "direct",
            "step_id": str(receipt.get("step_id") or "").strip(),
            "operation_id": str(receipt.get("operation_id") or "").strip(),
            "issue_id": str(issue_id or "").strip(),
            "role_name": str(role_name or "").strip(),
            "turn_index": int(turn_index),
            "tool_call_hash": str(receipt.get("tool_call_hash") or "").strip(),
            "receipt_digest": str(receipt.get("receipt_digest") or "").strip(),
        }
        return entry

    async def _artifact_provenance_entry_from_log_pair(
        self,
        *,
        run_id: str,
        operation_id: str,
        start: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        artifact_location = await asyncio.to_thread(
            self._resolve_workspace_artifact_location,
            {},
            {"tool_args": dict(start.get("tool_args") or {})},
        )
        if artifact_location is None:
            return None
        artifact_path, resolved_artifact_path = artifact_location
        produced_at = await asyncio.to_thread(self._artifact_produced_at, resolved_artifact_path)
        if not produced_at:
            return None
        issue_id = str(start.get("issue_id") or "").strip()
        role_name = str(start.get("role_name") or "").strip()
        turn_index = int(start.get("turn_index") or 0)
        step_id = f"{issue_id}:{turn_index}" if issue_id and turn_index > 0 else ""
        source_hash = self._artifact_log_source_hash(
            run_id=run_id,
            operation_id=operation_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            tool_args=dict(start.get("tool_args") or {}),
        )
        return {
            "artifact_path": artifact_path,
            "artifact_type": self._artifact_type_for_path(artifact_path),
            "generator": "tool.write_file",
            "generator_version": "unversioned",
            "source_hash": source_hash,
            "produced_at": produced_at,
            "truth_classification": "direct",
            "step_id": step_id,
            "operation_id": operation_id,
            "issue_id": issue_id,
            "role_name": role_name,
            "turn_index": turn_index,
        }

    def _build_packet1_repair_facts(self, repair_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not repair_entries:
            return {}
        repair_reasons = sorted(
            {
                str(reason).strip()
                for entry in repair_entries
                for reason in list(entry.get("reasons") or [])
                if str(reason).strip()
            }
        )
        repair_strategies = sorted(
            {
                str(entry.get("strategy") or "").strip()
                for entry in repair_entries
                if str(entry.get("strategy") or "").strip()
            }
        )
        return {
            "repair_occurred": True,
            "repair_material_change": True,
            "repair_strategy": repair_strategies[0] if len(repair_strategies) == 1 else "multiple_repair_strategies",
            "repair_reasons": repair_reasons,
        }

    def _build_packet2_facts(self, *, repair_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not repair_entries:
            return {}
        return {
            "repair_entries": [dict(entry) for entry in repair_entries],
            "final_disposition": "accepted_with_repair",
        }

    def _build_artifact_provenance_facts(self, *, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not entries:
            return {}
        return {
            "artifacts": [dict(entry) for entry in entries],
        }

    def _packet1_model_response_paths(self, run_id: str) -> List[Path]:
        observability_root = self.workspace / "observability" / sanitize_name(run_id)
        if not observability_root.exists():
            return []
        return sorted(observability_root.rglob("model_response_raw.json"))

    def _artifact_provenance_receipt_paths(self, run_id: str) -> List[Path]:
        observability_root = self.workspace / "observability" / sanitize_name(run_id)
        if not observability_root.exists():
            return []
        return sorted(observability_root.rglob("protocol_receipts.log"))

    def _artifact_provenance_receipt_context(self, *, receipt_path: Path, run_id: str) -> tuple[str, str, int]:
        session_root = self.workspace / "observability" / sanitize_name(run_id)
        try:
            relative_path = receipt_path.relative_to(session_root)
        except ValueError:
            return "", "", 0
        parts = relative_path.parts
        if len(parts) < 3:
            return "", "", 0
        issue_id = str(parts[0]).strip()
        turn_token = str(parts[1]).strip()
        turn_index = 0
        role_name = ""
        if "_" in turn_token:
            raw_turn_index, role_name = turn_token.split("_", 1)
            try:
                turn_index = max(0, int(raw_turn_index))
            except ValueError:
                turn_index = 0
        return issue_id, role_name.strip(), turn_index

    def _resolve_workspace_artifact_location(
        self,
        execution_result: Dict[str, Any],
        receipt: Dict[str, Any],
    ) -> tuple[str, Path] | None:
        raw_path = str(execution_result.get("path") or "").strip()
        if not raw_path:
            tool_args = receipt.get("tool_args") if isinstance(receipt.get("tool_args"), dict) else {}
            raw_path = str(tool_args.get("path") or "").strip()
        if not raw_path:
            return None
        workspace_root = self.workspace.resolve()
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = workspace_root / candidate
        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(workspace_root):
            return None
        if not resolved.exists() or not resolved.is_file():
            return None
        return resolved.relative_to(workspace_root).as_posix(), resolved

    @staticmethod
    def _artifact_type_for_path(artifact_path: str) -> str:
        normalized = str(artifact_path or "").strip().lower()
        if normalized.endswith("/source_attribution_receipt.json"):
            return "source_attribution_receipt"
        if normalized.endswith("/requirements.txt"):
            return "requirements_document"
        if normalized.endswith("/design.txt"):
            return "design_document"
        if normalized.endswith(".py"):
            return "source_code"
        if normalized.endswith(".json"):
            return "json_document"
        if normalized.endswith(".txt") or normalized.endswith(".md"):
            return "document"
        return "file"

    @staticmethod
    def _artifact_produced_at(path: Path) -> str:
        try:
            stat_result = path.stat()
        except OSError:
            return ""
        return datetime.fromtimestamp(stat_result.st_mtime, UTC).isoformat()

    @staticmethod
    def _artifact_log_source_hash(
        *,
        run_id: str,
        operation_id: str,
        issue_id: str,
        role_name: str,
        turn_index: int,
        tool_args: Dict[str, Any],
    ) -> str:
        return hash_canonical_json(
            {
                "run_id": str(run_id),
                "operation_id": str(operation_id),
                "issue_id": str(issue_id),
                "role_name": str(role_name),
                "turn_index": int(turn_index),
                "tool": "write_file",
                "tool_args": dict(tool_args),
            }
        )

    async def _record_packet1_emission_failure(
        self,
        *,
        run_id: str,
        stage: str,
        error_type: str,
        error: str,
    ) -> None:
        payload = {
            "session_id": str(run_id),
            "run_id": str(run_id),
            "stage": str(stage),
            "error_type": str(error_type),
            "error": str(error),
            "packet1_conformance": {
                "status": "non_conformant",
                "reasons": ["packet1_emission_failure"],
            },
        }
        if hasattr(self.run_ledger, "append_event"):
            try:
                await self.run_ledger.append_event(
                    session_id=str(run_id),
                    kind="packet1_emission_failure",
                    payload={"packet1_facts": payload["packet1_conformance"], **payload},
                )
            except (RuntimeError, ValueError, TypeError, OSError, AttributeError):
                pass
        log_event("packet1_emission_failure", payload, workspace=self.workspace)

    async def _record_packet2_facts(
        self,
        *,
        run_id: str,
        packet2_facts: Dict[str, Any],
    ) -> None:
        if not hasattr(self.run_ledger, "append_event"):
            return
        try:
            await self.run_ledger.append_event(
                session_id=str(run_id),
                kind="packet2_fact",
                payload={"packet2_facts": dict(packet2_facts)},
            )
        except (RuntimeError, ValueError, TypeError, OSError, AttributeError):
            return

    async def _record_artifact_provenance_facts(
        self,
        *,
        run_id: str,
        artifact_provenance_facts: Dict[str, Any],
    ) -> None:
        if not hasattr(self.run_ledger, "append_event"):
            return
        try:
            await self.run_ledger.append_event(
                session_id=str(run_id),
                kind="artifact_provenance_fact",
                payload={"artifact_provenance_facts": dict(artifact_provenance_facts)},
            )
        except (RuntimeError, ValueError, TypeError, OSError, AttributeError):
            return

    async def _materialize_protocol_receipts(self, *, run_id: str) -> Dict[str, Any] | None:
        if not hasattr(self.run_ledger, "append_receipt"):
            return None
        if not hasattr(self.run_ledger, "append_event"):
            return None
        if not hasattr(self.run_ledger, "list_events"):
            return None
        try:
            summary = await materialize_protocol_receipts(
                workspace=self.workspace,
                session_id=str(run_id),
                run_ledger=self.run_ledger,
            )
            if int(summary.get("source_receipts") or 0) > 0:
                log_event(
                    "protocol_receipts_materialized",
                    {
                        "run_id": str(run_id),
                        **dict(summary),
                    },
                    workspace=self.workspace,
                )
            return summary
        except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as exc:
            log_event(
                "protocol_receipt_materialization_failed",
                {
                    "run_id": str(run_id),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                workspace=self.workspace,
            )
            return None

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
