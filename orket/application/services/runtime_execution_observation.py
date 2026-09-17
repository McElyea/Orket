"""Read retained identities without publishing a terminal outcome on failure."""
from __future__ import annotations

import asyncio
import logging

from orket.core.contracts.control_plane_models import RunRecord
from orket.core.contracts.runtime_execution_result import RuntimeExecutionResult

logger = logging.getLogger(__name__)


async def unfinished_execution_result(*, publication, session_id, request, observation, reason, transcript=()):
    references = []
    run = truth = None
    try:
        async with publication.repository.transaction(session_id) as tx:
            admission = await tx.get_admission()
            if admission is None or admission.request != request:
                return None
            references.append(f"epic-admission:{session_id}:sha256:{admission.digest()}")
            records = (await tx.get(), await tx.get_preparation(), await tx.get_outcome(),
                       await tx.approval_pauses.latest())
            recoveries = await tx.approval_pauses.recoveries()
            references.extend(f"epic-approval-recovery:{session_id}:sha256:{record.digest()}" for record in recoveries)
        artifacts = None
        for kind, record in zip(("publication", "preparation", "outcome", "approval-pause"), records, strict=True):
            if record is None:
                continue
            references.append(f"epic-{kind}:{session_id}:sha256:{record.digest()}")
            if artifacts is None:
                artifacts = (record.plan.ledger["artifacts"] if kind in {"publication", "preparation"}
                             else record.artifacts)
        if artifacts is None:
            row = await publication.ledger.get_run(session_id)
            artifacts = row.get("artifact_json", {}) if row else {}
        retained = artifacts.get("control_plane_run_record")
        if retained:
            identity = RunRecord.model_validate(retained).run_id
            references.append(identity)
            run = await publication.control_plane.execution_repository.get_run_record(run_id=identity)
            if run is not None:
                truth = await publication.control_plane.publication.repository.get_final_truth(run_id=identity)
                if truth is not None:
                    references.append(truth.final_truth_record_id)
                    if truth.final_truth_record_id != run.final_truth_record_id:
                        truth = None
                        reason += "; E_RUNTIME_RESULT_TRUTH_IDENTITY_CONFLICT"
    except Exception as exc:
        # This is the last observation boundary after an owned execution failed.
        # Retain uncertainty even when its evidence store is itself unavailable.
        logger.exception("Runtime observation failed for session %s", session_id)
        reason += f"; observation unavailable: {type(exc).__name__}: {exc}"
    return RuntimeExecutionResult(session_id=session_id, build_id=request["build_id"], observation=observation,
        run=run, final_truth=truth, evidence_refs=tuple(references), reason=reason, transcript=tuple(transcript))


async def shield_observation(awaitable):
    """Repeated caller cancellation must not abandon the evidence reader."""
    task = asyncio.create_task(awaitable)
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
    return task.result()
