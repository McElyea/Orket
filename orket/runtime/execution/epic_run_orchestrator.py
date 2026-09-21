from __future__ import annotations

from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.cards_epic_control_plane_service import CardsEpicControlPlaneService
from orket.application.services.control_plane_workload_catalog import (
    build_cards_workload_contract,
    resolve_cards_control_plane_workload_from_contract,
)
from orket.application.services.epic_approval_pause_service import EpicApprovalPauseService
from orket.application.services.epic_preparation_service import EpicPreparationService
from orket.application.services.epic_publication_service import EpicPublicationService
from orket.application.services.epic_workload_outcome_service import EpicWorkloadOutcomeService
from orket.application.services.execution_policy_input_service import capture_execution_identifiers
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.cards_runtime_contract import apply_epic_cards_runtime_defaults
from orket.core.contracts import WorkloadContractV1
from orket.core.contracts.eos_calendar import EosSprintBaseline
from orket.core.contracts.epic_approval_recovery import EpicApprovalRecoveryRequest
from orket.core.contracts.epic_export_recovery import EpicExportRecoveryRequest
from orket.core.contracts.epic_publication import EpicAdmissionRecoveryRequest
from orket.core.contracts.repositories import CardRepository
from orket.core.contracts.runtime_execution_result import RuntimeExecutionResult
from orket.exceptions import (
    ComplexityViolation,
)
from orket.logging import log_event
from orket.runtime.config_loader import ConfigLoader
from orket.runtime.deterministic_mode_contract import deterministic_mode_contract_snapshot
from orket.runtime.epic_run_finalize import EpicRunFinalizer
from orket.runtime.epic_run_support import build_execution_artifacts
from orket.runtime.epic_run_types import (
    EpicRunCallbacks,
    EpicRunContext,
    EpicRunSetup,
    EpicWorkloadShell,
    RunLedger,
    SessionsRepository,
    SnapshotsRepository,
    SuccessRepository,
)
from orket.runtime.execution.epic_run_result_boundary import run_with_result
from orket.runtime.phase_c_runtime_truth import normalize_truthful_runtime_policy
from orket.runtime.route_decision_artifact import build_route_decision_artifact
from orket.runtime.run_start_artifacts import capture_run_start_artifacts
from orket.schema import CardStatus, EpicConfig, TeamConfig


@dataclass(frozen=True)
class EpicRunOrchestrator:
    workspace: Path
    department: str
    organization: Any
    runtime_input_service: RuntimeInputService
    execution_runtime_node: Any
    pipeline_wiring_service: Any
    cards_repo: CardRepository
    sessions_repo: SessionsRepository
    snapshots_repo: SnapshotsRepository
    success_repo: SuccessRepository
    run_ledger: RunLedger
    cards_epic_control_plane: CardsEpicControlPlaneService
    loader: ConfigLoader
    orchestrator: Any
    workload_shell: EpicWorkloadShell
    callbacks: EpicRunCallbacks
    publication: EpicPublicationService
    preparation: EpicPreparationService
    approval_pauses: EpicApprovalPauseService | None = None
    eos_calendar: EosSprintBaseline = EosSprintBaseline()

    async def run(
        self,
        epic_name: str,
        *,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        target_issue_id: str | None = None,
        model_override: str = "",
        admission_recovery: dict[str, Any] | None = None,
        export_recovery: dict[str, Any] | None = None, approval_recovery: dict[str, Any] | None = None,
        **_: Any,
    ) -> RuntimeExecutionResult:
        del driver_steered
        if sum(value is not None for value in (admission_recovery, export_recovery, approval_recovery)) > 1:
            raise ValueError("E_EPIC_RECOVERY_REQUESTS_EXCLUSIVE")
        export_request = EpicExportRecoveryRequest.model_validate(export_recovery) if export_recovery is not None else None
        if export_request is not None and session_id != export_request.session_id:
            raise ValueError("E_EPIC_EXPORT_RECOVERY_SESSION_REQUIRED")
        recovery_request = EpicAdmissionRecoveryRequest.model_validate(admission_recovery) if admission_recovery is not None else None
        if recovery_request is not None and session_id != recovery_request.session_id:
            raise ValueError("E_EPIC_ADMISSION_RECOVERY_SESSION_REQUIRED")
        approval_request = EpicApprovalRecoveryRequest.model_validate(approval_recovery) if approval_recovery is not None else None
        if approval_request is not None and session_id != approval_request.session_id:
            raise ValueError("E_EPIC_APPROVAL_RECOVERY_SESSION_REQUIRED")
        setup = await self._load_setup(
            epic_name=epic_name,
            build_id=build_id,
            session_id=session_id,
            target_issue_id=target_issue_id,
            model_override=model_override,
        )
        return await run_with_result(self, setup, recovery_request, export_request, approval_request)

    async def _admit_and_initialize(self, setup, admissions, admission):
        if admission is None:
            admission = await admissions.claim(setup.run_id, setup.publication_request, self.preparation.export_binding)
        admission = await admissions.begin_initialization(admission)
        setup = await self._ensure_session_and_cards(replace(setup, admission=admission))
        return await self._initialize_run(setup)

    async def _load_setup(
        self,
        *,
        epic_name: str,
        build_id: str | None,
        session_id: str | None,
        target_issue_id: str | None,
        model_override: str,
    ) -> EpicRunSetup:
        run_id, active_build = capture_execution_identifiers(self.execution_runtime_node, self.runtime_input_service,
            name=epic_name, session_id=session_id, build_id=build_id)
        calendar_sprint = self.eos_calendar.current_sprint(self.runtime_input_service.utc_now().astimezone())
        epic = await self.loader.load_asset_async("epics", epic_name, EpicConfig)
        team = await self.loader.load_asset_async("teams", epic.team, TeamConfig)
        env = await self.loader.load_environment_asset_async(epic.environment)
        if model_override:
            env = env.model_copy(update={"model": model_override})
        epic_params = epic.params if isinstance(epic.params, dict) else {}
        self._validate_idesign_policy(epic=epic, issue_count=len(epic.issues))
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
            epic_asset=epic_name,
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
            calendar_sprint=calendar_sprint,
            publication_request={"scope": self.publication.request_scope(run_id), "contract": cards_workload_contract,
                                 "epic": epic.model_dump(), "build_id": active_build, "department": self.department,
                                 "team": team.model_dump(), "environment": env.model_dump(),
                                 "target_issue_id": target_issue_id},
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
                "sprint": setup.calendar_sprint,
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
        run_contract_artifacts = await run_owned_thread(
            partial(capture_run_start_artifacts, workspace=self.workspace, run_id=setup.run_id,
                    workload=setup.epic.name, now=self.runtime_input_service.utc_now()),
            label="capture run-start artifacts",
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
        artifacts = build_execution_artifacts(callbacks=self.callbacks, context=context)
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
                **({"approval_resume_turns": context.approval_resume_turns}
                   if context.approval_resume_turns is not None else {}),
            )

        await self.workload_shell.execute(
            contract_payload=context.setup.cards_workload_contract,
            execute_fn=_execute_cards_workload,
        )

    def _build_finalizer(self) -> EpicRunFinalizer:
        return EpicRunFinalizer(
            outcomes=EpicWorkloadOutcomeService(self.publication.repository, self.run_ledger),
            preparation=self.preparation,
            publication=self.publication,
            workspace=self.workspace,
            cards_repo=self.cards_repo,
            cards_epic_control_plane=self.cards_epic_control_plane,
            callbacks=self.callbacks,
        )
