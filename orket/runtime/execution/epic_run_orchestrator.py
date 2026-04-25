from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from orket.application.services.runtime_input_service import RuntimeInputService
from orket.application.services.cards_epic_control_plane_service import CardsEpicControlPlaneService
from orket.application.services.control_plane_workload_catalog import (
    build_cards_workload_contract,
    resolve_cards_control_plane_workload_from_contract,
)
from orket.core.cards_runtime_contract import apply_epic_cards_runtime_defaults
from orket.core.contracts import WorkloadContractV1
from orket.exceptions import CardNotFound, ComplexityViolation, ExecutionFailed, OrketInfrastructureError
from orket.logging import log_event
from orket.runtime.config_loader import ConfigLoader
from orket.runtime.deterministic_mode_contract import deterministic_mode_contract_snapshot
from orket.runtime.epic_run_finalize import EpicRunFinalizer
from orket.runtime.epic_run_support import build_base_run_artifacts, set_control_plane_artifacts
from orket.runtime.epic_run_types import (
    CardsRepository,
    EpicRunCallbacks,
    EpicRunContext,
    EpicRunSetup,
    EpicWorkloadShell,
    RunLedger,
    SessionsRepository,
    SnapshotsRepository,
    SuccessRepository,
)
from orket.runtime.phase_c_runtime_truth import normalize_truthful_runtime_policy
from orket.runtime.route_decision_artifact import build_route_decision_artifact
from orket.runtime.run_start_artifacts import capture_run_start_artifacts
from orket.schema import CardStatus, EpicConfig, TeamConfig
from orket.utils import get_eos_sprint, sanitize_name


@dataclass(frozen=True)
class EpicRunOrchestrator:
    workspace: Path
    department: str
    organization: Any
    runtime_input_service: RuntimeInputService
    execution_runtime_node: Any
    pipeline_wiring_service: Any
    cards_repo: CardsRepository
    sessions_repo: SessionsRepository
    snapshots_repo: SnapshotsRepository
    success_repo: SuccessRepository
    run_ledger: RunLedger
    cards_epic_control_plane: CardsEpicControlPlaneService
    loader: ConfigLoader
    orchestrator: Any
    workload_shell: EpicWorkloadShell
    callbacks: EpicRunCallbacks

    async def run(
        self,
        epic_name: str,
        *,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        target_issue_id: str | None = None,
        model_override: str = "",
        **_: Any,
    ) -> list[dict[str, Any]]:
        del driver_steered
        setup = await self._load_setup(
            epic_name=epic_name,
            build_id=build_id,
            session_id=session_id,
            target_issue_id=target_issue_id,
            model_override=model_override,
        )
        setup = await self._ensure_session_and_cards(setup)
        context = await self._initialize_run(setup)
        finalizer = self._build_finalizer()
        try:
            await self._execute_workload(context)
            transcript = self.orchestrator.transcript
            self.callbacks.set_transcript(transcript)
            return await finalizer.finalize_success(context=context, transcript=transcript)
        except (CardNotFound, ComplexityViolation, ExecutionFailed, OrketInfrastructureError) as exc:
            transcript = self.orchestrator.transcript
            self.callbacks.set_transcript(transcript)
            await finalizer.finalize_failure(context=context, transcript=transcript, exc=exc)
            raise

    async def _load_setup(
        self,
        *,
        epic_name: str,
        build_id: str | None,
        session_id: str | None,
        target_issue_id: str | None,
        model_override: str,
    ) -> EpicRunSetup:
        epic = await self.loader.load_asset_async("epics", epic_name, EpicConfig)
        team = await self.loader.load_asset_async("teams", epic.team, TeamConfig)
        env = await self.loader.load_environment_asset_async(epic.environment)
        if model_override:
            env = env.model_copy(update={"model": model_override})
        epic_params = epic.params if isinstance(epic.params, dict) else {}
        self._validate_idesign_policy(epic=epic, issue_count=len(epic.issues))
        requested_run_id = session_id or self.runtime_input_service.create_session_id()
        run_id = self.execution_runtime_node.select_run_id(requested_run_id)
        active_build = self.execution_runtime_node.select_epic_build_id(build_id, epic_name, sanitize_name)
        cards_workload_contract = build_cards_workload_contract(
            epic=epic,
            run_id=run_id,
            build_id=active_build,
            workspace=self.workspace,
            department=self.department,
        )
        control_plane_workload_record = resolve_cards_control_plane_workload_from_contract(
            contract_payload=cards_workload_contract,
            department=self.department,
        )
        return EpicRunSetup(
            epic=epic,
            team=team,
            env=env,
            run_id=run_id,
            build_id=active_build,
            target_issue_id=target_issue_id,
            resume_mode=False,
            model_override=model_override,
            phase_c_truth_policy=normalize_truthful_runtime_policy(epic_params.get("truthful_runtime")),
            cards_workload_contract=cards_workload_contract,
            control_plane_workload_record=control_plane_workload_record,
        )

    def _validate_idesign_policy(self, *, epic: Any, issue_count: int) -> None:
        threshold = 7
        if self.organization and self.organization.architecture:
            threshold = self.organization.architecture.idesign_threshold
        idesign_mode = self.callbacks.resolve_idesign_mode()
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

    async def _ensure_session_and_cards(self, setup: EpicRunSetup) -> EpicRunSetup:
        if not await self.sessions_repo.get_session(setup.run_id):
            await self.sessions_repo.start_session(
                setup.run_id,
                {
                    "type": "epic",
                    "name": setup.epic.name,
                    "department": self.department,
                    "task_input": setup.epic.description,
                },
            )
        existing = await self.cards_repo.get_by_build(setup.build_id)
        resume_mode = bool(setup.target_issue_id) or any(
            issue.status in {CardStatus.IN_PROGRESS, CardStatus.CODE_REVIEW, CardStatus.AWAITING_GUARD_REVIEW}
            for issue in existing
        )
        preserve_issue_ids = {str(setup.target_issue_id).strip()} if setup.target_issue_id else set()
        if resume_mode:
            await self.callbacks.resume_stalled_issues(
                existing,
                setup.run_id,
                setup.build_id,
                preserve_issue_ids=preserve_issue_ids,
            )
        if existing:
            await self._reconcile_existing_cards(setup=setup, existing=existing)
        epic_params = setup.epic.params if isinstance(setup.epic.params, dict) else {}
        for issue in setup.epic.issues:
            issue.params = apply_epic_cards_runtime_defaults(
                issue_params=getattr(issue, "params", None),
                epic_params=epic_params,
            )
            if any(existing_issue.id == issue.id for existing_issue in existing):
                continue
            await self.cards_repo.save(self._card_payload(issue=issue, setup=setup))
        return replace(setup, resume_mode=resume_mode)

    async def _reconcile_existing_cards(self, *, setup: EpicRunSetup, existing: list[Any]) -> None:
        if setup.target_issue_id:
            await self.callbacks.resume_target_issue_if_existing(
                issues=existing,
                target_issue_id=setup.target_issue_id,
                run_id=setup.run_id,
                active_build=setup.build_id,
            )
            return
        await self.cards_repo.reset_build(setup.build_id)

    def _card_payload(self, *, issue: Any, setup: EpicRunSetup) -> dict[str, Any]:
        payload: dict[str, Any] = dict(issue.model_dump(by_alias=True))
        payload.update(
            {
                "session_id": setup.run_id,
                "build_id": setup.build_id,
                "sprint": get_eos_sprint(),
                "status": CardStatus.READY,
            }
        )
        return payload

    async def _initialize_run(self, setup: EpicRunSetup) -> EpicRunContext:
        deterministic_mode_contract = deterministic_mode_contract_snapshot()
        route_decision_artifact = build_route_decision_artifact(
            run_id=setup.run_id,
            workload_kind="epic",
            execution_runtime_node=self.execution_runtime_node,
            pipeline_wiring_service=self.pipeline_wiring_service,
            target_issue_id=setup.target_issue_id,
            resume_mode=setup.resume_mode,
            deterministic_mode_enabled=bool(deterministic_mode_contract.get("deterministic_mode_enabled")),
        )
        (
            control_plane_run,
            control_plane_attempt,
            control_plane_start_step,
            control_plane_checkpoint,
            control_plane_checkpoint_acceptance,
        ) = (
            await self.cards_epic_control_plane.begin_execution(
                session_id=setup.run_id,
                build_id=setup.build_id,
                epic_name=setup.epic.name,
                department=self.department,
                workload=setup.control_plane_workload_record,
                resume_mode=setup.resume_mode,
                target_issue_id=setup.target_issue_id,
            )
        )
        log_event(
            "session_start",
            {"epic": setup.epic.name, "run_id": setup.run_id, "build_id": setup.build_id},
            workspace=self.workspace,
        )
        run_contract_artifacts = await asyncio.to_thread(
            capture_run_start_artifacts,
            workspace=self.workspace,
            run_id=setup.run_id,
            workload=setup.epic.name,
        )
        self._apply_runtime_capabilities(run_contract_artifacts)
        context = EpicRunContext(
            setup=setup,
            deterministic_mode_contract=deterministic_mode_contract,
            route_decision_artifact=route_decision_artifact,
            control_plane_run=control_plane_run,
            control_plane_attempt=control_plane_attempt,
            control_plane_start_step=control_plane_start_step,
            control_plane_checkpoint=control_plane_checkpoint,
            control_plane_checkpoint_acceptance=control_plane_checkpoint_acceptance,
            run_contract_artifacts=run_contract_artifacts,
        )
        await self._start_run_ledger(context)
        return context

    def _apply_runtime_capabilities(self, run_contract_artifacts: dict[str, Any]) -> None:
        capability_manifest = run_contract_artifacts.get("capability_manifest")
        if isinstance(capability_manifest, dict):
            allowed = [
                str(token).strip().lower()
                for token in (capability_manifest.get("capabilities_allowed") or [])
                if str(token).strip()
            ]
            determinism_class = str(
                capability_manifest.get("run_determinism_class")
                or run_contract_artifacts.get("run_determinism_class")
                or "workspace"
            ).strip().lower()
        else:
            allowed = ["workspace"]
            determinism_class = str(run_contract_artifacts.get("run_determinism_class") or "workspace").strip().lower()
        if determinism_class not in {"pure", "workspace", "external"}:
            determinism_class = "workspace"
        compatibility_map = run_contract_artifacts.get("compatibility_map_snapshot")
        raw_mappings = compatibility_map.get("mappings") if isinstance(compatibility_map, dict) else {}
        self.orchestrator.active_capabilities_allowed = allowed or ["workspace"]
        self.orchestrator.active_run_determinism_class = determinism_class
        self.orchestrator.active_compatibility_mappings = {
            str(tool_name).strip(): dict(mapping or {})
            for tool_name, mapping in (raw_mappings if isinstance(raw_mappings, dict) else {}).items()
            if str(tool_name).strip() and isinstance(mapping, dict)
        }

    async def _start_run_ledger(self, context: EpicRunContext) -> None:
        artifacts = build_base_run_artifacts(callbacks=self.callbacks, context=context)
        artifacts["control_plane_workload_record"] = context.setup.control_plane_workload_record.model_dump(mode="json")
        set_control_plane_artifacts(
            artifacts,
            control_plane_run=context.control_plane_run,
            control_plane_attempt=context.control_plane_attempt,
            control_plane_step=context.control_plane_start_step,
            control_plane_checkpoint=context.control_plane_checkpoint,
            control_plane_checkpoint_acceptance=context.control_plane_checkpoint_acceptance,
        )
        await self.run_ledger.start_run(
            session_id=context.setup.run_id,
            run_type="epic",
            run_name=context.setup.epic.name,
            department=self.department,
            build_id=context.setup.build_id,
            artifacts=artifacts,
        )

    async def _execute_workload(self, context: EpicRunContext) -> None:
        async def _execute_cards_workload(_contract: WorkloadContractV1) -> None:
            await self.orchestrator.execute_epic(
                active_build=context.setup.build_id,
                run_id=context.setup.run_id,
                epic=context.setup.epic,
                team=context.setup.team,
                env=context.setup.env,
                target_issue_id=context.setup.target_issue_id,
                resume_mode=context.setup.resume_mode,
                model_override=context.setup.model_override or None,
            )

        await self.workload_shell.execute(
            contract_payload=context.setup.cards_workload_contract,
            execute_fn=_execute_cards_workload,
        )

    def _build_finalizer(self) -> EpicRunFinalizer:
        return EpicRunFinalizer(
            workspace=self.workspace,
            cards_repo=self.cards_repo,
            sessions_repo=self.sessions_repo,
            snapshots_repo=self.snapshots_repo,
            success_repo=self.success_repo,
            run_ledger=self.run_ledger,
            cards_epic_control_plane=self.cards_epic_control_plane,
            callbacks=self.callbacks,
        )
