"""Pure contract checks; these do not prove runtime evidence or persistence gates."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from orket.core.contracts.card_completion import (
    AcceptanceRequirement,
    CardAcceptanceEvidence,
    CardAcceptancePlan,
    CompletionEvidenceSnapshot,
    CompletionScope,
    CompletionState,
)
from orket.core.policies.card_completion import evaluate_card_completion

pytestmark = pytest.mark.contract


def _plan() -> CardAcceptancePlan:
    return CardAcceptancePlan(
        acceptance_ref="cli-output.v1", policy_ref="test-policy.v1", policy_digest="0" * 64,
        workload_id="exact-output-cli.v1",
        requirements=(AcceptanceRequirement(
            criterion_id="expected-output", description="The declared input produces the exact expected output.",
            verifier_ref="exact-cli-output.v1", verifier_digest="1" * 64, evidence_class="behavioral_verification",
        ),),
    )


def _scope() -> CompletionScope:
    return CompletionScope(card_id="card-1", run_id="run-1", attempt_id="attempt-1", workload_id="exact-output-cli.v1",
                           input_digest="2" * 64, artifact_manifest_digest="3" * 64)


def _evidence(plan: CardAcceptancePlan | None = None) -> CardAcceptanceEvidence:
    plan = plan or _plan()
    return CardAcceptanceEvidence(
        evidence_ref="evidence:1", evidence_digest="4" * 64, plan_digest=plan.digest, scope=_scope(),
        criterion_id="expected-output", verifier_ref="exact-cli-output.v1", verifier_digest="1" * 64,
        evidence_class="behavioral_verification", observation="passed", source="runtime_verifier",
    )


def _evaluate(*records: CardAcceptanceEvidence, **snapshot_options):
    return evaluate_card_completion(plan=_plan(), scope=_scope(), snapshot=CompletionEvidenceSnapshot(
        records=records, **{"inventory_complete": True, **snapshot_options},
    ))


# Layer: contract
def test_sufficiency_is_limited_to_declared_acceptance_and_exact_evidence():
    evidence = _evidence()
    decision = _evaluate(evidence)
    assert decision.sufficient
    assert decision.state == CompletionState.SATISFIED
    assert decision.plan_digest == _plan().digest
    assert decision.scope == _scope()
    assert decision.evidence_refs == (evidence.evidence_ref,)
    assert not decision.diagnostics
    assert not decision.missing_criteria


@pytest.mark.parametrize("missing", ["plan", "scope", "evidence", "inventory", "body_verification"])
# Layer: contract
def test_absent_acceptance_or_unverified_evidence_cannot_authorize_completion(missing):
    snapshot = CompletionEvidenceSnapshot(
        records=() if missing == "evidence" else (_evidence(),),
        inventory_complete=missing != "inventory",
        diagnostics=("evidence:1:retained_body_digest_mismatch",) if missing == "body_verification" else (),
    )
    decision = evaluate_card_completion(plan=None if missing == "plan" else _plan(),
                                        scope=None if missing == "scope" else _scope(), snapshot=snapshot)
    assert not decision.sufficient
    assert decision.diagnostics
    if missing == "evidence":
        assert decision.missing_criteria == ("expected-output",)


@pytest.mark.parametrize("changes,diagnostic", [
    ({"evidence_class": "not_evaluated"}, "evidence_class_mismatch"),
    ({"evidence_class": "syntax_only"}, "evidence_class_mismatch"),
    ({"evidence_class": "command_execution"}, "evidence_class_mismatch"),
    ({"source": "model_self_report"}, "evidence_source_not_admitted"),
    ({"observation": "failed"}, "accepted_check_failed"),
    ({"observation": "not_evaluated"}, "accepted_check_not_evaluated"),
    ({"verifier_ref": "unaccepted-verifier.v1"}, "verifier_mismatch"),
    ({"verifier_digest": "5" * 64}, "verifier_mismatch"),
    ({"plan_digest": "6" * 64}, "acceptance_plan_mismatch"),
    ({"criterion_id": "self-reported-done"}, "undeclared_criterion"),
])
# Layer: contract
def test_weaker_failed_self_reported_or_substituted_checks_never_satisfy_behavior(changes, diagnostic):
    evidence = CardAcceptanceEvidence.model_validate({**_evidence().model_dump(), **changes})
    decision = _evaluate(evidence)
    assert not decision.sufficient
    assert decision.missing_criteria == ("expected-output",)
    assert any(row.endswith(diagnostic) for row in decision.diagnostics)
    if changes.get("observation") == "failed":
        assert decision.state == CompletionState.FAILED


@pytest.mark.parametrize("field,value", [
    ("card_id", "card-2"), ("run_id", "run-2"), ("attempt_id", "attempt-2"),
    ("workload_id", "another-workload.v1"), ("input_digest", "5" * 64), ("artifact_manifest_digest", "6" * 64),
])
# Layer: contract
def test_stale_or_cross_scope_evidence_is_insufficient(field, value):
    scope = CompletionScope.model_validate({**_scope().model_dump(), field: value})
    evidence = CardAcceptanceEvidence.model_validate({**_evidence().model_dump(), "scope": scope})
    decision = _evaluate(evidence)
    assert not decision.sufficient
    assert "expected-output:completion_scope_mismatch" in decision.diagnostics


# Layer: contract
def test_conflicting_duplicate_evidence_cannot_be_reduced_to_a_passing_subset():
    failed = CardAcceptanceEvidence.model_validate({**_evidence().model_dump(), "observation": "failed",
                                                    "evidence_ref": "evidence:2"})
    for records in ((_evidence(), failed), (failed, _evidence()), (_evidence(), _evidence())):
        decision = _evaluate(*records)
        assert not decision.sufficient
        assert "expected-output:duplicate_criterion_evidence" in decision.diagnostics


# Layer: contract
def test_every_declared_criterion_must_be_covered_and_evidence_refs_cannot_alias():
    second = AcceptanceRequirement.model_validate({**_plan().requirements[0].model_dump(), "criterion_id": "second-input"})
    plan = CardAcceptancePlan.model_validate({**_plan().model_dump(), "requirements": (*_plan().requirements, second)})
    first_evidence = _evidence(plan)
    incomplete = evaluate_card_completion(plan=plan, scope=_scope(), snapshot=CompletionEvidenceSnapshot(
        records=(first_evidence,), inventory_complete=True))
    assert not incomplete.sufficient
    assert incomplete.missing_criteria == ("second-input",)
    second_evidence = CardAcceptanceEvidence.model_validate({**first_evidence.model_dump(), "criterion_id": "second-input"})
    aliased = evaluate_card_completion(plan=plan, scope=_scope(), snapshot=CompletionEvidenceSnapshot(
        records=(first_evidence, second_evidence), inventory_complete=True))
    assert not aliased.sufficient
    assert "second-input:duplicate_evidence_reference" in aliased.diagnostics


@pytest.mark.parametrize("change", ["policy", "acceptance", "criterion", "verifier", "workload"])
# Layer: contract
def test_changing_accepted_policy_or_coverage_invalidates_previous_evidence(change):
    payload = _plan().model_dump(mode="json")
    if change == "policy":
        payload["policy_digest"] = "9" * 64
    elif change == "acceptance":
        payload["acceptance_ref"] = "cli-output.v2"
    elif change == "criterion":
        payload["requirements"][0]["description"] = "An additional case must be handled."
    elif change == "verifier":
        payload["requirements"][0]["verifier_digest"] = "8" * 64
    else:
        payload["workload_id"] = "different-workload.v1"
    changed = CardAcceptancePlan.model_validate(payload)
    assert changed.digest != _plan().digest
    decision = evaluate_card_completion(plan=changed, scope=_scope(), snapshot=CompletionEvidenceSnapshot(
        records=(_evidence(),), inventory_complete=True))
    assert not decision.sufficient
    assert "expected-output:acceptance_plan_mismatch" in decision.diagnostics


# Layer: contract
def test_empty_ambiguous_or_unknown_contract_inputs_fail_closed():
    for requirements in ([], [_plan().requirements[0], _plan().requirements[0]]):
        with pytest.raises(ValidationError):
            CardAcceptancePlan.model_validate({**_plan().model_dump(), "requirements": requirements})
    for changes in ({"evidence_class": "not_evaluated"}, {"verifier_digest": ""}):
        with pytest.raises(ValidationError):
            AcceptanceRequirement.model_validate({**_plan().requirements[0].model_dump(), **changes})
    for changes in ({"inventory_complete": "true"}, {"runtime_verifier_ok": True}):
        with pytest.raises(ValidationError):
            CompletionEvidenceSnapshot.model_validate(changes)
    round_trip = CardAcceptancePlan.model_validate_json(json.dumps(_plan().model_dump(mode="json")))
    assert round_trip.digest == _plan().digest
    with pytest.raises(ValidationError):
        round_trip.requirements[0].description = "Mutated coverage"
