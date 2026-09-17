"""Synthetic typed results for contract tests; these are not runtime evidence."""
from orket.core.contracts.control_plane_models import FinalTruthRecord, RunRecord
from orket.core.contracts.runtime_execution_result import RuntimeExecutionResult


def published_result(*, success=True, session_id="fixture-session", transcript=()):
    truth = FinalTruthRecord(final_truth_record_id="fixture-truth", run_id="fixture-run",
        result_class="success" if success else "failed",
        completion_classification="completion_satisfied" if success else "completion_unsatisfied",
        evidence_sufficiency_classification="evidence_sufficient", residual_uncertainty_classification="no_residual_uncertainty",
        degradation_classification="no_degradation", closure_basis="normal_execution",
        terminality_basis="completed_terminal", authority_sources=["receipt_evidence"])
    run = RunRecord(run_id="fixture-run", workload_id="fixture-workload", workload_version="1",
        policy_snapshot_id="fixture-policy", policy_digest="fixture-policy-digest",
        configuration_snapshot_id="fixture-config", configuration_digest="fixture-config-digest",
        creation_timestamp="2026-09-13T00:00:00Z", admission_decision_receipt_ref="fixture-admission",
        lifecycle_state="completed" if success else "failed_terminal", final_truth_record_id=truth.final_truth_record_id)
    return RuntimeExecutionResult(session_id=session_id, observation="published", run=run, final_truth=truth,
        publication_ref="fixture-publication", evidence_refs=("fixture-publication",), transcript=tuple(transcript))
