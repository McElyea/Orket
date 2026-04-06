from __future__ import annotations

import asyncio
import contextlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import aiofiles

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.adapters.storage.async_repositories import (
    AsyncSessionRepository,
    AsyncSnapshotRepository,
    AsyncSuccessRepository,
)
from orket.adapters.storage.gitea_state_adapter import GiteaStateAdapter
from orket.adapters.vcs.gitea_artifact_exporter import GiteaArtifactExporter
from orket.application.services.cards_epic_control_plane_service import CardsEpicControlPlaneService
from orket.application.services.gitea_state_control_plane_checkpoint_service import (
    build_gitea_state_control_plane_checkpoint_service,
)
from orket.application.services.gitea_state_control_plane_execution_service import (
    build_gitea_state_control_plane_execution_service,
)
from orket.application.services.gitea_state_control_plane_lease_service import (
    build_gitea_state_control_plane_lease_service,
)
from orket.application.services.gitea_state_control_plane_reservation_service import (
    build_gitea_state_control_plane_reservation_service,
)
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
)
from orket.application.workflows.protocol_hashing import hash_canonical_json
from orket.core.cards_runtime_contract import normalize_scenario_truth_alignment, summarize_cards_runtime_issues
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.exceptions import CardNotFound
from orket.logging import log_event
from orket.orchestration.orchestration_config import OrchestrationConfig
from orket.runtime.config_loader import ConfigLoader
from orket.runtime.epic_run_orchestrator import EpicRunOrchestrator
from orket.runtime.epic_run_types import EpicRunCallbacks
from orket.runtime.phase_c_runtime_truth import collect_phase_c_packet2_facts
from orket.runtime.protocol_receipt_materializer import materialize_protocol_receipts
from orket.runtime.run_ledger_factory import build_run_ledger_repository
from orket.runtime.run_start_artifacts import validate_run_identity_projection
from orket.runtime.run_summary import (
    PACKET1_MISSING_TOKEN,
    build_degraded_run_summary_payload,
    generate_run_summary_for_finalize,
    write_run_summary_artifact,
)
from orket.runtime.run_summary_artifact_provenance import normalize_artifact_provenance_facts
from orket.runtime.runtime_context import OrketRuntimeContext
from orket.runtime.settings import resolve_str
from orket.runtime.workload_shell import SharedWorkloadShell
from orket.runtime_paths import resolve_control_plane_db_path
from orket.schema import (
    CardStatus,
    EpicConfig,
    IssueConfig,
    RockConfig,
)
from orket.settings import load_user_settings, load_user_settings_async
from orket.utils import sanitize_name

_RUN_SUMMARY_RUN_IDENTITY_ERROR_PREFIX = "run_summary_run_identity_"
# EpicRunOrchestrator now owns cards workload authority resolution via
# resolve_cards_control_plane_workload_from_contract.
_TRANSIENT_RUN_IDENTITY_ARTIFACT_KEYS = ("run_identity", "run_identity_path")


def _is_run_summary_run_identity_error(exc: Exception) -> bool:
    return str(exc).strip().startswith(_RUN_SUMMARY_RUN_IDENTITY_ERROR_PREFIX)


def _strip_transient_run_identity_artifacts(artifacts: dict[str, Any]) -> None:
    for key in _TRANSIENT_RUN_IDENTITY_ARTIFACT_KEYS:
        artifacts.pop(key, None)


class ExecutionPipeline:
    """
    The central engine for Orket Unit execution.
    Load -> Validate -> Plan -> Execute -> Persist -> Report
    """

    def __init__(
        self,
        workspace: Path,
        department: str = "core",
        db_path: str | None = None,
        config_root: Path | None = None,
        cards_repo: AsyncCardRepository | None = None,
        sessions_repo: AsyncSessionRepository | None = None,
        snapshots_repo: AsyncSnapshotRepository | None = None,
        success_repo: AsyncSuccessRepository | None = None,
        run_ledger_repo: Any | None = None,
        decision_nodes: DecisionNodeRegistry | None = None,
        runtime_context: OrketRuntimeContext | None = None,
    ):
        from orket.orchestration.notes import NoteStore

        runtime_nodes = decision_nodes or DecisionNodeRegistry()
        self.runtime_context = runtime_context or OrketRuntimeContext.from_env(
            workspace_root=workspace,
            department=department,
            db_path=db_path,
            config_root=config_root,
            cards_repo=cards_repo,
            sessions_repo=sessions_repo,
            snapshots_repo=snapshots_repo,
            success_repo=success_repo,
            run_ledger_repo=run_ledger_repo,
            decision_nodes=runtime_nodes,
            config_loader_factory=ConfigLoader,
            config_loader_kwargs={"decision_nodes": runtime_nodes},
            run_ledger_factory=build_run_ledger_repository,
            telemetry_sink=self._emit_run_ledger_telemetry,
        )
        self.workspace = self.runtime_context.workspace_root
        self.department = self.runtime_context.department
        self.decision_nodes = self.runtime_context.decision_nodes
        self.config_root = self.runtime_context.config_root
        self.loader = self.runtime_context.loader
        self.db_path = self.runtime_context.db_path
        self.org = self.runtime_context.org
        self.orchestration_config = self.runtime_context.orchestration_config
        self.user_settings = dict(self.runtime_context.user_settings)
        self.state_backend_mode = self.runtime_context.state_backend_mode
        self.run_ledger_mode = self.runtime_context.run_ledger_mode
        self.gitea_state_pilot_enabled = self.runtime_context.gitea_state_pilot_enabled
        self.execution_runtime_node = self.decision_nodes.resolve_execution_runtime(self.org)
        self.pipeline_wiring_node = self.decision_nodes.resolve_pipeline_wiring(self.org)

        self.async_cards = self.runtime_context.cards_repo
        self.sessions = self.runtime_context.sessions_repo
        self.snapshots = self.runtime_context.snapshots_repo
        self.success = self.runtime_context.success_repo
        self.run_ledger = self.runtime_context.run_ledger
        self.artifact_exporter = GiteaArtifactExporter(self.workspace)

        self.notes = NoteStore()
        self.transcript: list[dict[str, Any]] = []
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
        self.orchestrator.run_ledger = self.run_ledger
        self.cards_epic_control_plane = CardsEpicControlPlaneService(
            execution_repository=self.orchestrator.control_plane_execution_repository,
            publication=self.orchestrator.control_plane_publication,
        )
        self.workload_shell = SharedWorkloadShell()

    def _process_rules_value(self, key: str) -> str:
        process_rules = getattr(self.org, "process_rules", None) if self.org else None
        if process_rules is None:
            return ""
        if isinstance(process_rules, dict) or hasattr(process_rules, "get"):
            value = process_rules.get(key, "")
        else:
            value = getattr(process_rules, key, "")
        return str(value or "").strip()

    def _resolve_state_backend_mode(self) -> str:
        user_settings = getattr(self, "user_settings", None)
        if not isinstance(user_settings, dict):
            loaded = load_user_settings()
            user_settings = loaded if isinstance(loaded, dict) else {}
        return OrchestrationConfig(self.org).resolve_state_backend_mode(user_settings=user_settings)

    def _resolve_run_ledger_mode(self) -> str:
        user_settings = getattr(self, "user_settings", None)
        if not isinstance(user_settings, dict):
            loaded = load_user_settings()
            user_settings = loaded if isinstance(loaded, dict) else {}
        return OrchestrationConfig(self.org).resolve_run_ledger_mode(user_settings=user_settings)

    def _validate_state_backend_mode(self) -> None:
        self.orchestration_config.validate_state_backend_mode(
            self.state_backend_mode,
            self.gitea_state_pilot_enabled,
        )

    async def _emit_run_ledger_telemetry(self, payload: dict[str, Any]) -> None:
        log_event(
            "run_ledger_telemetry",
            {
                "run_ledger_mode": self.run_ledger_mode,
                **dict(payload or {}),
            },
            workspace=self.workspace,
        )

    def _resolve_gitea_state_pilot_enabled(self) -> bool:
        user_settings = getattr(self, "user_settings", None)
        if not isinstance(user_settings, dict):
            loaded = load_user_settings()
            user_settings = loaded if isinstance(loaded, dict) else {}
        return OrchestrationConfig(self.org).resolve_gitea_state_pilot_enabled(user_settings=user_settings)

    async def run_card(
        self,
        card_id: str,
        *,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        target_issue_id: str | None = None,
        model_override: str | None = None,
    ) -> Any:
        """Canonical public runtime dispatcher over normalized card facts."""
        target_kind, parent_epic_name = await self._resolve_run_card_target(card_id)
        if target_kind == "epic":
            return await self._run_epic_entry(
                card_id,
                build_id=build_id,
                session_id=session_id,
                driver_steered=driver_steered,
                target_issue_id=target_issue_id,
                model_override=model_override,
            )
        if target_kind == "epic_collection":
            return await self._run_epic_collection_entry(
                card_id,
                build_id=build_id,
                session_id=session_id,
                driver_steered=driver_steered,
                model_override=model_override,
            )
        return await self._run_issue_entry(
            card_id,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered,
            parent_epic_name=parent_epic_name,
            target_issue_id=target_issue_id,
            model_override=model_override,
        )

    async def _resolve_run_card_target(self, card_id: str) -> tuple[str, str | None]:
        """Resolve one normalized runtime target kind from explicit asset facts."""
        epics = await self.loader.list_assets_async("epics")
        if card_id in epics:
            return "epic", None

        rocks = await self.loader.list_assets_async("rocks")
        if card_id in rocks:
            return "epic_collection", None

        parent_epic, parent_ename, _ = await self._find_parent_epic(card_id)
        if parent_epic and parent_ename:
            return "issue", parent_ename

        raise CardNotFound(f"Card {card_id} not found.")

    async def run_issue(
        self,
        issue_id: str,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        model_override: str | None = None,
    ) -> Any:
        """Compatibility wrapper over the canonical run_card surface."""
        return await self.run_card(
            issue_id,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered,
            model_override=model_override,
        )

    async def run_rock(
        self,
        rock_name: str,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        model_override: str | None = None,
    ) -> Any:
        """Legacy compatibility wrapper over the canonical run_card surface."""
        return await self.run_card(
            rock_name,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered,
            model_override=model_override,
        )

    async def _run_issue_entry(
        self,
        issue_id: str,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        parent_epic_name: str | None = None,
        target_issue_id: str | None = None,
        model_override: str | None = None,
    ) -> Any:
        parent_ename = parent_epic_name
        if parent_ename is None:
            parent_epic, parent_ename, _ = await self._find_parent_epic(issue_id)
            if not parent_epic or parent_ename is None:
                raise CardNotFound(f"Card {issue_id} not found.")
        log_event(
            "pipeline_atomic_issue",
            {"card_id": issue_id, "parent_epic": parent_ename},
            workspace=self.workspace,
        )
        del target_issue_id
        return await self._run_epic_entry(
            parent_ename,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered,
            target_issue_id=issue_id,
            model_override=model_override,
        )

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
    ) -> dict[str, Any]:
        if self.state_backend_mode != "gitea":
            raise ValueError("run_gitea_state_loop requires state_backend_mode='gitea'")
        readiness = evaluate_gitea_state_pilot_readiness(collect_gitea_state_pilot_inputs())
        if not bool(readiness.get("ready")):
            failures = ", ".join(list(readiness.get("failures") or [])) or "unknown readiness failure"
            raise RuntimeError(f"State backend mode 'gitea' pilot readiness failed: {failures}")

        process_rules = getattr(self.org, "process_rules", None) if self.org else None

        def process_rules_get(key: str, default: Any = None) -> Any:
            if process_rules is None:
                return default
            if isinstance(process_rules, dict):
                return process_rules.get(key, default)
            getter = getattr(process_rules, "get", None)
            if callable(getter):
                return getter(key, default)
            return getattr(process_rules, key, default)

        raw_user_settings = await load_user_settings_async()
        user_settings = raw_user_settings if isinstance(raw_user_settings, dict) else {}
        effective_max_iterations = resolve_gitea_worker_max_iterations(
            max_iterations,
            resolve_str("ORKET_GITEA_WORKER_MAX_ITERATIONS"),
            process_rules_get("gitea_worker_max_iterations"),
            user_settings.get("gitea_worker_max_iterations"),
        )
        effective_max_idle_streak = resolve_gitea_worker_max_idle_streak(
            max_idle_streak,
            resolve_str("ORKET_GITEA_WORKER_MAX_IDLE_STREAK"),
            process_rules_get("gitea_worker_max_idle_streak"),
            user_settings.get("gitea_worker_max_idle_streak"),
        )
        effective_max_duration_seconds = resolve_gitea_worker_max_duration_seconds(
            max_duration_seconds,
            resolve_str("ORKET_GITEA_WORKER_MAX_DURATION_SECONDS"),
            process_rules_get("gitea_worker_max_duration_seconds"),
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
            control_plane_checkpoint_service=build_gitea_state_control_plane_checkpoint_service(
                resolve_control_plane_db_path()
            ),
            control_plane_execution_service=build_gitea_state_control_plane_execution_service(
                resolve_control_plane_db_path()
            ),
            control_plane_lease_service=build_gitea_state_control_plane_lease_service(
                resolve_control_plane_db_path()
            ),
            control_plane_reservation_service=build_gitea_state_control_plane_reservation_service(
                resolve_control_plane_db_path()
            ),
        )
        coordinator = GiteaStateWorkerCoordinator(
            worker=worker,
            fetch_limit=fetch_limit,
            max_iterations=effective_max_iterations,
            max_idle_streak=effective_max_idle_streak,
            max_duration_seconds=effective_max_duration_seconds,
            idle_sleep_seconds=idle_sleep_seconds,
        )

        async def _work_fn(card: dict[str, Any]) -> dict[str, Any]:
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
        raw = resolve_str(
            "ORKET_IDESIGN_MODE",
            process_rules=getattr(self.org, "process_rules", None),
            process_key="idesign_mode",
        )

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
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        target_issue_id: str | None = None,
        model_override: str | None = None,
    ) -> list[dict[str, Any]]:
        """Compatibility wrapper over the canonical run_card surface."""
        result = await self.run_card(
            epic_name,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered,
            target_issue_id=target_issue_id,
            model_override=model_override,
        )
        return cast(list[dict[str, Any]], result)

    def _build_epic_run_orchestrator(self) -> EpicRunOrchestrator:
        return EpicRunOrchestrator(
            workspace=self.workspace,
            department=self.department,
            organization=self.org,
            execution_runtime_node=self.execution_runtime_node,
            pipeline_wiring_node=self.pipeline_wiring_node,
            cards_repo=self.async_cards,
            sessions_repo=self.sessions,
            snapshots_repo=self.snapshots,
            success_repo=self.success,
            run_ledger=self.run_ledger,
            cards_epic_control_plane=self.cards_epic_control_plane,
            loader=self.loader,
            orchestrator=self.orchestrator,
            workload_shell=self.workload_shell,
            callbacks=EpicRunCallbacks(
                resolve_idesign_mode=self._resolve_idesign_mode,
                resume_stalled_issues=self._resume_stalled_issues,
                resume_target_issue_if_existing=self._resume_target_issue_if_existing,
                run_artifact_refs=self._run_artifact_refs,
                build_packet1_facts=self._build_packet1_facts,
                materialize_protocol_receipts=self._materialize_protocol_receipts,
                materialize_run_summary=self._materialize_run_summary,
                export_run_artifacts=self._export_run_artifacts,
                set_transcript=lambda transcript: setattr(self, "transcript", transcript),
            ),
        )

    async def _run_epic_entry(
        self,
        epic_name: str,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        target_issue_id: str | None = None,
        model_override: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self._build_epic_run_orchestrator().run(
            epic_name,
            build_id=build_id,
            session_id=session_id,
            driver_steered=driver_steered,
            target_issue_id=target_issue_id,
            model_override=str(model_override or "").strip(),
        )

    def _run_artifact_refs(self, run_id: str) -> dict[str, str]:
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
        runtime_telemetry: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
        existing_packet1_facts: dict[str, Any],
        updated_packet1_facts: dict[str, Any],
    ) -> dict[str, Any]:
        merged = dict(existing_packet1_facts)
        for key, value in updated_packet1_facts.items():
            if key in {
                "intended_provider",
                "intended_model",
                "intended_profile",
                "actual_provider",
                "actual_model",
                "actual_profile",
            } and str(value).strip() == PACKET1_MISSING_TOKEN and self._normalize_packet1_token(
                existing_packet1_facts.get(key)
            ):
                continue
            merged[key] = value
        return merged

    def _select_primary_work_artifact_output(
        self,
        *,
        artifact_provenance_facts: dict[str, Any] | None = None,
    ) -> dict[str, str]:
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
        output: dict[str, str] = {"id": artifact_path, "kind": "artifact"}
        for field in (
            "control_plane_run_id",
            "control_plane_attempt_id",
            "control_plane_step_id",
        ):
            token = str(selected.get(field) or "").strip()
            if token:
                output[field] = token
        return output

    async def _export_run_artifacts(
        self,
        *,
        run_id: str,
        run_type: str,
        run_name: str,
        build_id: str,
        session_status: str,
        summary: dict[str, Any],
        failure_class: str | None = None,
        failure_reason: str | None = None,
    ) -> dict[str, Any] | None:
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
        artifacts: dict[str, Any],
        finalized_at: str,
        phase_c_truth_policy: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        resolved_artifacts = dict(artifacts)
        repair_entries = await self._resolve_packet2_repair_entries(run_id=run_id)
        artifact_provenance_artifacts = await self._resolve_artifact_provenance_artifacts(run_id=run_id)
        cards_runtime_artifacts = await self._resolve_cards_runtime_artifacts(
            run_id=run_id,
            session_status=session_status,
            failure_reason=failure_reason,
        )
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
        if cards_runtime_artifacts:
            resolved_artifacts.update(cards_runtime_artifacts)
        runtime_verification_path = str(packet1_artifacts.get("runtime_verification_path") or "").strip()
        if runtime_verification_path:
            resolved_artifacts["runtime_verification_path"] = runtime_verification_path
        try:
            run_identity = resolved_artifacts.get("run_identity")
            started_at = None
            if run_identity is not None:
                started_at = validate_run_identity_projection(
                    run_identity,
                    error_prefix="run_summary_run_identity",
                )["start_time"]
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
            if _is_run_summary_run_identity_error(exc):
                # Do not let invalid bootstrap identity shape degraded summary output.
                _strip_transient_run_identity_artifacts(resolved_artifacts)
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
        repair_entries: list[dict[str, Any]] | None = None,
        artifact_provenance_facts: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
        repair_entries: list[dict[str, Any]] | None = None,
        artifact_provenance_facts: dict[str, Any] | None = None,
        phase_c_truth_policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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

    async def _resolve_artifact_provenance_artifacts(self, *, run_id: str) -> dict[str, Any]:
        entries = await self._resolve_artifact_provenance_entries(run_id=run_id)
        artifact_provenance_facts = self._build_artifact_provenance_facts(entries=entries)
        if not artifact_provenance_facts:
            return {}
        await self._record_artifact_provenance_facts(
            run_id=run_id,
            artifact_provenance_facts=artifact_provenance_facts,
        )
        return {"artifact_provenance_facts": artifact_provenance_facts}

    async def _resolve_packet1_runtime_telemetry(self, *, run_id: str) -> dict[str, Any]:
        candidate_paths = await asyncio.to_thread(self._packet1_model_response_paths, run_id)
        selected: dict[str, Any] = {}
        for path in candidate_paths:
            try:
                async with aiofiles.open(path, encoding="utf-8") as handle:
                    payload = json.loads(await handle.read())
            except (OSError, ValueError, TypeError):
                continue
            if not isinstance(payload, dict):
                continue
            selected = payload
        return selected

    async def _resolve_packet2_repair_entries(self, *, run_id: str) -> list[dict[str, Any]]:
        log_path = self.workspace / "orket.log"
        if not log_path.exists():
            return []
        repairs_by_id: dict[str, dict[str, Any]] = {}
        try:
            async with aiofiles.open(log_path, encoding="utf-8") as handle:
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
                    raw_data = payload.get("data")
                    data: dict[str, Any] = dict(raw_data) if isinstance(raw_data, dict) else {}
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
                        entry: dict[str, Any] = {
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

    async def _resolve_cards_runtime_artifacts(
        self,
        *,
        run_id: str,
        session_status: str,
        failure_reason: str | None,
    ) -> dict[str, Any]:
        log_path = self.workspace / "orket.log"
        if not log_path.exists():
            return {}
        issues: dict[str, dict[str, Any]] = {}
        try:
            async with aiofiles.open(log_path, encoding="utf-8") as handle:
                async for line in handle:
                    if not line.strip():
                        continue
                    try:
                        payload = json.loads(line)
                    except (ValueError, TypeError):
                        continue
                    if not isinstance(payload, dict):
                        continue
                    if str(payload.get("event") or "").strip() not in {
                        "turn_start",
                        "turn_complete",
                        "turn_failed",
                        "odr_prebuild_completed",
                        "odr_prebuild_failed",
                    }:
                        continue
                    raw_data = payload.get("data")
                    data: dict[str, Any] = dict(raw_data) if isinstance(raw_data, dict) else {}
                    if str(data.get("session_id") or "").strip() != str(run_id):
                        continue
                    issue_id = str(data.get("issue_id") or "").strip()
                    if not issue_id:
                        continue
                    row = issues.setdefault(issue_id, {"issue_id": issue_id})
                    for key in (
                        "execution_profile",
                        "builder_seat_choice",
                        "reviewer_seat_choice",
                        "profile_traits",
                        "seat_coercion",
                        "artifact_contract",
                        "scenario_truth",
                        "odr_active",
                        "odr_stop_reason",
                        "odr_valid",
                        "odr_pending_decisions",
                        "odr_artifact_path",
                    ):
                        if key not in data:
                            continue
                        value = data.get(key)
                        if value is None:
                            continue
                        if isinstance(value, str) and not value.strip():
                            continue
                        if isinstance(value, (list, dict)) and not value:
                            continue
                        row[key] = value
        except OSError:
            return {}
        summary = summarize_cards_runtime_issues(list(issues.values()))
        if not summary:
            return {}
        summary["stop_reason"] = self._resolve_cards_stop_reason(
            session_status=session_status,
            failure_reason=failure_reason,
        )
        scenario_truth_alignment = normalize_scenario_truth_alignment(
            scenario_truth=summary.get("scenario_truth"),
            observed_terminal_status=session_status,
        )
        if scenario_truth_alignment:
            summary["scenario_truth_alignment"] = scenario_truth_alignment
        return {"cards_runtime_facts": summary}

    @staticmethod
    def _resolve_cards_stop_reason(*, session_status: str, failure_reason: str | None) -> str:
        explicit_failure = str(failure_reason or "").strip()
        if explicit_failure:
            return explicit_failure
        token = str(session_status or "").strip().lower()
        if token == "done":
            return "completed"
        if token == "incomplete":
            return "open_issues_remaining"
        if token == "terminal_failure":
            return "terminal_failure"
        if token == "failed":
            return "failed"
        return token or "unknown"

    async def _resolve_artifact_provenance_entries(self, *, run_id: str) -> list[dict[str, Any]]:
        receipt_entries = await self._resolve_artifact_provenance_entries_from_receipts(run_id=run_id)
        artifacts_by_path: dict[str, dict[str, Any]] = {
            str(entry["artifact_path"]): dict(entry) for entry in receipt_entries
        }
        log_entries = await self._resolve_artifact_provenance_entries_from_logs(
            run_id=run_id,
            existing_paths=set(artifacts_by_path),
        )
        for entry in log_entries:
            artifacts_by_path[str(entry["artifact_path"])] = dict(entry)
        return [artifacts_by_path[key] for key in sorted(artifacts_by_path)]

    async def _resolve_artifact_provenance_entries_from_receipts(self, *, run_id: str) -> list[dict[str, Any]]:
        receipt_paths = await asyncio.to_thread(self._artifact_provenance_receipt_paths, run_id)
        artifacts_by_path: dict[str, dict[str, Any]] = {}
        for receipt_path in receipt_paths:
            issue_id, role_name, turn_index = self._artifact_provenance_receipt_context(
                receipt_path=receipt_path,
                run_id=run_id,
            )
            try:
                async with aiofiles.open(receipt_path, encoding="utf-8") as handle:
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
    ) -> list[dict[str, Any]]:
        log_path = self.workspace / "orket.log"
        if not log_path.exists():
            return []
        starts_by_operation: dict[str, dict[str, Any]] = {}
        artifacts_by_path: dict[str, dict[str, Any]] = {}
        try:
            async with aiofiles.open(log_path, encoding="utf-8") as handle:
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
                    raw_data = payload.get("data")
                    data: dict[str, Any] = dict(raw_data) if isinstance(raw_data, dict) else {}
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
        receipt: dict[str, Any],
        issue_id: str,
        role_name: str,
        turn_index: int,
    ) -> dict[str, Any] | None:
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
        entry: dict[str, Any] = {
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
        for field in (
            "control_plane_run_id",
            "control_plane_attempt_id",
            "control_plane_step_id",
        ):
            token = str(manifest.get(field) or "").strip()
            if token:
                entry[field] = token
        return entry

    async def _artifact_provenance_entry_from_log_pair(
        self,
        *,
        run_id: str,
        operation_id: str,
        start: dict[str, Any],
    ) -> dict[str, Any] | None:
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

    def _build_packet1_repair_facts(self, repair_entries: list[dict[str, Any]]) -> dict[str, Any]:
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

    def _build_packet2_facts(self, *, repair_entries: list[dict[str, Any]]) -> dict[str, Any]:
        if not repair_entries:
            return {}
        return {
            "repair_entries": [dict(entry) for entry in repair_entries],
            "final_disposition": "accepted_with_repair",
        }

    def _build_artifact_provenance_facts(self, *, entries: list[dict[str, Any]]) -> dict[str, Any]:
        if not entries:
            return {}
        return {
            "artifacts": [dict(entry) for entry in entries],
        }

    def _packet1_model_response_paths(self, run_id: str) -> list[Path]:
        observability_root = self.workspace / "observability" / sanitize_name(run_id)
        if not observability_root.exists():
            return []
        return sorted(observability_root.rglob("model_response_raw.json"))

    def _artifact_provenance_receipt_paths(self, run_id: str) -> list[Path]:
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
        execution_result: dict[str, Any],
        receipt: dict[str, Any],
    ) -> tuple[str, Path] | None:
        raw_path = str(execution_result.get("path") or "").strip()
        if not raw_path:
            raw_tool_args = receipt.get("tool_args")
            tool_args: dict[str, Any] = dict(raw_tool_args) if isinstance(raw_tool_args, dict) else {}
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
        tool_args: dict[str, Any],
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
            with contextlib.suppress(RuntimeError, ValueError, TypeError, OSError, AttributeError):
                await self.run_ledger.append_event(
                    session_id=str(run_id),
                    kind="packet1_emission_failure",
                    payload={"packet1_facts": payload["packet1_conformance"], **payload},
                )
        log_event("packet1_emission_failure", payload, workspace=self.workspace)

    async def _record_packet2_facts(
        self,
        *,
        run_id: str,
        packet2_facts: dict[str, Any],
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
        artifact_provenance_facts: dict[str, Any],
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

    async def _materialize_protocol_receipts(self, *, run_id: str) -> dict[str, Any] | None:
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

    async def _run_epic_collection_entry(
        self,
        collection_name: str,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        model_override: str | None = None,
    ) -> dict[str, Any]:
        collection = await self.loader.load_asset_async("rocks", collection_name, RockConfig)
        sid = self.execution_runtime_node.select_epic_collection_session_id(session_id)
        active_build = self.execution_runtime_node.select_epic_collection_build_id(
            build_id, collection_name, sanitize_name
        )
        results = []
        for entry in collection.epics:
            epic_ws = self.workspace / entry["epic"]
            sub_pipeline = self.pipeline_wiring_node.create_sub_pipeline(
                parent_pipeline=self,
                epic_workspace=epic_ws,
                department=entry["department"],
            )
            res = await sub_pipeline.run_card(
                entry["epic"],
                build_id=active_build,
                session_id=sid,
                driver_steered=driver_steered,
                model_override=model_override,
            )
            results.append({"epic": entry["epic"], "transcript": res})

        log_event(
            "epic_collection_phase_transition",
            {"collection": collection.name, "phase": "bug_fix"},
            workspace=self.workspace,
        )
        await self.bug_fix_manager.start_phase(collection.id)

        return {"collection": collection.name, "results": results}

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

    async def _resume_target_issue_if_existing(
        self,
        *,
        issues: list[Any],
        target_issue_id: str,
        run_id: str,
        active_build: str,
    ) -> None:
        target_issue = next(
            (issue for issue in issues if str(getattr(issue, "id", "")).strip() == str(target_issue_id).strip()),
            None,
        )
        if target_issue is None:
            return
        current_status = getattr(target_issue, "status", None)
        current_status_value = getattr(current_status, "value", current_status)
        current_status_token = str(current_status_value or "").strip() or "unknown"
        try:
            normalized_status = CardStatus(current_status_token.lower())
        except ValueError:
            normalized_status = None
        if normalized_status in {
            CardStatus.READY,
            CardStatus.IN_PROGRESS,
            CardStatus.CODE_REVIEW,
            CardStatus.AWAITING_GUARD_REVIEW,
        }:
            log_event(
                "resume_target_issue_preserved",
                {
                    "run_id": run_id,
                    "build_id": active_build,
                    "issue_id": str(getattr(target_issue, "id", "")).strip(),
                    "current_status": current_status_token,
                },
                workspace=self.workspace,
            )
            return
        metadata = {
            "run_id": run_id,
            "build_id": active_build,
            "target_issue_id": str(target_issue_id).strip(),
            "previous_status": current_status_token,
        }
        await self.async_cards.update_status(
            str(getattr(target_issue, "id", "")).strip(),
            CardStatus.READY,
            reason="resume_target_issue",
            metadata=metadata,
        )
        target_issue.status = CardStatus.READY
        await self._publish_resume_transition_control_plane(
            issue=target_issue,
            current_status=current_status,
            target_status=CardStatus.READY,
            run_id=run_id,
            reason="resume_target_issue",
            metadata=metadata,
        )
        log_event(
            "resume_target_issue_requeued",
            {
                "run_id": run_id,
                "build_id": active_build,
                "issue_id": str(getattr(target_issue, "id", "")).strip(),
                "previous_status": current_status_token,
                "new_status": CardStatus.READY.value,
            },
            workspace=self.workspace,
        )

    async def _resume_stalled_issues(
        self,
        issues: list[Any],
        run_id: str,
        active_build: str,
        *,
        preserve_issue_ids: set[str] | None = None,
    ) -> None:
        stalled_states = {CardStatus.IN_PROGRESS, CardStatus.CODE_REVIEW, CardStatus.AWAITING_GUARD_REVIEW}
        preserved_ids = {str(issue_id).strip() for issue_id in (preserve_issue_ids or set()) if str(issue_id).strip()}
        for issue in issues:
            issue_id = str(getattr(issue, "id", "")).strip()
            if issue_id in preserved_ids:
                continue
            if issue.status in stalled_states:
                current_status = issue.status
                current_status_token = str(
                    current_status.value if hasattr(current_status, "value") else current_status
                ).strip() or "unknown"
                metadata = {
                    "run_id": run_id,
                    "build_id": active_build,
                    "previous_status": current_status_token,
                }
                await self.async_cards.update_status(
                    issue_id,
                    CardStatus.READY,
                    reason="resume_requeue",
                    metadata=metadata,
                )
                issue.status = CardStatus.READY
                await self._publish_resume_transition_control_plane(
                    issue=issue,
                    current_status=current_status,
                    target_status=CardStatus.READY,
                    run_id=run_id,
                    reason="resume_requeue",
                    metadata=metadata,
                )
                log_event(
                    "resume_requeue_issue",
                    {
                        "run_id": run_id,
                        "build_id": active_build,
                        "issue_id": issue_id,
                        "previous_status": current_status_token,
                        "new_status": CardStatus.READY.value,
                    },
                    workspace=self.workspace,
                )

    async def _publish_resume_transition_control_plane(
        self,
        *,
        issue: Any,
        current_status: CardStatus | str | None,
        target_status: CardStatus,
        run_id: str,
        reason: str,
        metadata: dict[str, Any],
    ) -> None:
        issue_id = str(getattr(issue, "id", "")).strip()
        if not issue_id or not str(run_id or "").strip():
            return
        assignee = getattr(issue, "assignee", None)
        normalized_reason = str(reason or "").strip().lower()
        issue_control_plane = getattr(self.orchestrator, "issue_control_plane", None)
        handled_by_dispatch = False
        if issue_control_plane is not None:
            handled_by_dispatch = await issue_control_plane.publish_issue_transition(
                session_id=run_id,
                issue_id=issue_id,
                current_status=current_status or "unknown",
                target_status=target_status,
                reason=normalized_reason,
                assignee=assignee,
                turn_index=metadata.get("turn_index"),
                review_turn=bool(metadata.get("review_turn", False)),
            )
        scheduler_control_plane = getattr(self.orchestrator, "scheduler_control_plane", None)
        if scheduler_control_plane is None or handled_by_dispatch or normalized_reason == "turn_dispatch":
            return
        await scheduler_control_plane.publish_scheduler_transition(
            session_id=run_id,
            issue_id=issue_id,
            current_status=current_status or "unknown",
            target_status=target_status,
            reason=normalized_reason,
            assignee=assignee,
            metadata=dict(metadata),
        )

    async def verify_issue(self, issue_id: str) -> Any:
        return await self.orchestrator.verify_issue(issue_id)


async def orchestrate_card(card_id: str, workspace: Path, **kwargs: Any) -> Any:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_card(card_id, **kwargs)


async def orchestrate(epic_name: str, workspace: Path, **kwargs: Any) -> Any:
    return await ExecutionPipeline(workspace, kwargs.get("department", "core")).run_card(epic_name, **kwargs)
