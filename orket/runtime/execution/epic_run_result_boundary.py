"""One result boundary for normal execution, recovery, pause and cancellation."""
from __future__ import annotations

import asyncio
import logging
from contextlib import nullcontext

from orket.application.services.epic_admission_service import EpicAdmissionService
from orket.application.services.runtime_execution_observation import shield_observation, unfinished_execution_result
from orket.application.services.runtime_execution_result_service import RuntimeExecutionCancelled
from orket.core.contracts.epic_approval_pause import EPIC_APPROVAL_DENIED
from orket.core.contracts.runtime_execution_result import RuntimeExecutionResult
from orket.exceptions import ApprovalPending, CardNotFound, ComplexityViolation, ExecutionFailed
from orket.runtime.execution.epic_run_approval import restore_approval_context, retain_approval_pause
from orket.runtime.execution.epic_run_support import build_legacy_transcript

logger = logging.getLogger(__name__)


async def run_with_result(owner, setup, recovery_request, export_request, approval_request=None) -> RuntimeExecutionResult:
    try:
        return await _recover_or_execute(owner, setup, recovery_request, export_request, approval_request)
    except asyncio.CancelledError as exc:
        result = await shield_observation(_observe(owner, setup, "cancelled", "Caller cancelled execution"))
        if result is None:
            result = RuntimeExecutionResult(session_id=setup.run_id, build_id=setup.build_id,
                                            observation="cancelled", reason="Caller cancelled before admission")
        raise RuntimeExecutionCancelled(result) from exc
    except ApprovalPending as exc:
        result = await _observe(owner, setup, "approval_pending", str(exc))
        if result is None:
            raise
        return result
    except Exception as exc:
        # Top-level run supervisor: an infrastructure/publication failure cannot
        # be converted into verified terminal truth by recording another failure.
        logger.exception("Runtime outcome unresolved for session %s", setup.run_id)
        result = await _observe(owner, setup, "unresolved", f"{type(exc).__name__}: {exc}")
        if result is None:
            raise
        return result


async def _observe(owner, setup, observation, reason):
    return await unfinished_execution_result(publication=owner.publication, session_id=setup.run_id,
        request=setup.publication_request, observation=observation, reason=reason,
        transcript=build_legacy_transcript(owner.orchestrator.transcript))


async def _recover_or_execute(owner, setup, recovery_request, export_request, approval_request):
    observed_grant = False
    if approval_request is not None:
        if owner.approval_pauses is None:
            raise ValueError("E_EPIC_APPROVAL_SERVICE_REQUIRED")
        observed_grant = await owner.approval_pauses.observe_recovery(
            setup.run_id, setup.publication_request, owner.preparation.export_binding, approval_request)
    admissions = EpicAdmissionService(owner.publication.repository,
        owner_id=owner.runtime_input_service.create_effect_owner_id, now=owner.runtime_input_service.utc_now_iso)
    admission = (await admissions.recover_claim(setup.run_id, setup.publication_request,
                 owner.preparation.export_binding, recovery_request) if recovery_request is not None else None)
    if export_request is not None:
        await owner.preparation.recover_export(setup.run_id, setup.publication_request, export_request)
    await owner.preparation.recover(setup.run_id, setup.publication_request)
    recovered = await owner.publication.recover(setup.run_id, setup.publication_request)
    finalizer = owner._build_finalizer()
    if recovered is None:
        recovered = await finalizer.recover(setup.run_id, setup.publication_request)
    if recovered is not None:
        owner.callbacks.set_transcript(list(recovered.transcript))
        return recovered
    if observed_grant:
        raise ValueError("E_EPIC_APPROVAL_CONTINUATION_UNCERTAIN:grant_already_consumed")
    continuation = (owner.approval_pauses.continuation(
        setup.run_id, setup.publication_request, owner.preparation.export_binding, approval_request)
        if owner.approval_pauses is not None else nullcontext(None))
    async with continuation as pause:
        context = (await restore_approval_context(owner, setup, pause) if pause is not None
                   else await owner._admit_and_initialize(setup, admissions, admission))
        denied = pause is not None and "denied" in pause.decisions.values()
        outcome = await _execute_and_retain(owner, context, finalizer, denied)
    # Workload truth is durable before continuation ownership is released.
    # Export has its own retained owner and may recover independently.
    return await finalizer.finalize_outcome(outcome)


async def _execute_and_retain(owner, context, finalizer, denied):
    failure = ExecutionFailed(EPIC_APPROVAL_DENIED) if denied else None
    try:
        if not denied:
            await owner._execute_workload(context)
    except ApprovalPending:
        await retain_approval_pause(owner, context)
        owner.callbacks.set_transcript(owner.orchestrator.transcript)
        raise
    except (CardNotFound, ComplexityViolation, ExecutionFailed) as exc:
        failure = exc
    owner.callbacks.set_transcript(owner.orchestrator.transcript)
    return await finalizer.retain_outcome(context, owner.orchestrator.transcript, failure)
