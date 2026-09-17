"""Application projection of verified publication and unfinished owned execution."""
from __future__ import annotations

import asyncio

from orket.core.contracts.control_plane_models import RunRecord
from orket.core.contracts.runtime_execution_result import RuntimeCollectionResult, RuntimeExecutionResult


class RuntimeExecutionCancelled(asyncio.CancelledError):
    def __init__(self, result: RuntimeExecutionResult | RuntimeCollectionResult):
        super().__init__("Runtime execution cancelled after cleanup observation")
        self.result = result


async def published_execution_result(owner, plan, record) -> RuntimeExecutionResult:
    expected = RunRecord.model_validate(plan.ledger["artifacts"]["control_plane_run_record"])
    run = await owner.control_plane.execution_repository.get_run_record(run_id=expected.run_id)
    if run != expected:
        raise ValueError("E_RUNTIME_RESULT_RETAINED_RUN_CONFLICT")
    truth = await owner.control_plane.publication.repository.get_final_truth(run_id=run.run_id)
    publication_ref = f"epic-publication:{plan.session_id}:sha256:{record.digest()}"
    references = [publication_ref, run.run_id]
    if truth is not None:
        references.append(truth.final_truth_record_id)
    result = RuntimeExecutionResult(session_id=plan.session_id, build_id=plan.request["build_id"],
        observation="published", run=run, final_truth=truth, publication_ref=publication_ref,
        evidence_refs=tuple(references), reason=plan.ledger.get("failure_reason"), transcript=tuple(plan.transcript))
    return RuntimeExecutionResult.model_validate_json(result.model_dump_json())
