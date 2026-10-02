"""Contract: report consistency only, not native deployment acceptance."""
from copy import deepcopy

import pytest

from orket.application.services import microservices_acceptance_reports as reports
from tests.application.test_microservices_acceptance_reports import _valid_unlock_criteria

pytestmark = pytest.mark.contract


def _pattern():
    return {"run_count": 2, "session_status_counts": {"failed": 1, "done": 1},
            "pattern_counters": {"z": 0, "a": 2}, "invalid_payload_signals": {"schema": 0}}


def _unlock():
    return {"unlocked": True, "criteria": _valid_unlock_criteria(), "failures": []}


def _comparison():
    modes = reports.ARCHITECTURE_PILOT_COMPARISON_MODES
    return {"available": True, "pass_rate_delta_microservices_minus_monolith": 0,
            "runtime_failure_rate_delta_microservices_minus_monolith": 0,
            "reviewer_rejection_rate_delta_microservices_minus_monolith": 0,
            "invalid_payload_signals_by_architecture": {mode: {"schema": 0} for mode in modes},
            "invalid_payload_signal_totals_by_architecture": dict.fromkeys(modes, 0),
            "invalid_payload_failures": []}


def _stability():
    return {"stable": True, "artifact_count": 2, "required_consecutive": 2,
            "checks": [{"stable": True, "failures": []}, {"stable": True, "failures": []}],
            "failures": []}


@pytest.mark.parametrize("normalize,refusal", [
    (reports.normalize_live_acceptance_pattern_report, {}),
    (reports.normalize_microservices_unlock_report, {}),
    (reports.normalize_architecture_pilot_comparison, None),
    (reports.normalize_microservices_pilot_stability_report, {}),
])
@pytest.mark.parametrize("value", [None, [], "not a report"])
def test_non_object_reports_do_not_gain_acceptance(normalize, refusal, value):
    assert normalize(value) == refusal


@pytest.mark.parametrize("field,value", [
    ("run_count", True), ("run_count", -1), ("run_count", "2"),
    ("session_status_counts", None), ("session_status_counts", {"done": 1}),
    ("pattern_counters", {"": 0}), ("pattern_counters", {1: 0}),
    ("invalid_payload_signals", {"schema": True}),
    ("invalid_payload_signals", {"schema": -1}),
    ("invalid_payload_signals", {"schema": "0"}),
])
def test_pattern_counts_must_be_typed_nonnegative_and_reconcile(field, value):
    payload = {**_pattern(), field: value}
    before = deepcopy(payload)
    assert reports.normalize_live_acceptance_pattern_report(payload) == {}
    assert payload == before


@pytest.mark.parametrize("batch", [None, "", "batch-1"])
def test_valid_pattern_preserves_counts_and_canonical_counter_order(batch):
    payload = {**_pattern(), "batch_id": batch}
    result = reports.normalize_live_acceptance_pattern_report(payload)
    assert result["run_count"] == sum(result["session_status_counts"].values()) == 2
    assert list(result["pattern_counters"]) == ["a", "z"]
    assert ("batch_id" in result) == bool(batch)
    if batch:
        assert result["batch_id"] == batch
    result["pattern_counters"]["a"] = 999
    assert payload["pattern_counters"]["a"] == 2


@pytest.mark.parametrize("changes", [
    {"unlocked": 1}, {"failures": None}, {"criteria": None}, {"criteria": {}},
    {"criteria": {"": {"ok": True, "failures": []}}},
    {"criteria": {"gate": None}}, {"criteria": {"gate": {"ok": 1, "failures": []}}},
    {"criteria": {"gate": {"ok": True, "failures": None}}},
    {"criteria": {"gate": {"ok": True, "failures": ["contradiction"]}}},
    {"criteria": {"gate": {"ok": False, "failures": []}}},
    {"failures": ["contradiction"]},
    {"criteria": {"gate": {"ok": False, "failures": ["failed"]}}},
    {"unlocked": False},
    {"unlocked": False, "failures": ["no failing criterion"]},
    {"unlocked": False, "failures": ["different: failed"],
     "criteria": {"gate": {"ok": False, "failures": ["failed"]}}},
])
def test_unlock_claim_requires_matching_criteria_and_failure_evidence(changes):
    payload = {**_unlock(), **changes}
    before = deepcopy(payload)
    assert reports.normalize_microservices_unlock_report(payload) == {}
    assert payload == before


def test_valid_failed_unlock_retains_reason_metadata_and_optional_variant():
    payload = _unlock()
    payload.update(unlocked=False, failures=["matrix_stability: threshold failed"],
                   recommended_default_builder_variant=" ")
    payload["criteria"]["matrix_stability"] = {"ok": False, "failures": ["threshold failed"], "observed": 0.4}
    result = reports.normalize_microservices_unlock_report(payload)
    assert result["unlocked"] is False and result["failures"] == payload["failures"]
    assert result["criteria"]["matrix_stability"]["observed"] == 0.4
    assert "recommended_default_builder_variant" not in result


@pytest.mark.parametrize("changes", [
    {"available": 1}, {"pass_rate_delta_microservices_minus_monolith": True},
    {"runtime_failure_rate_delta_microservices_minus_monolith": "0"},
    {"reviewer_rejection_rate_delta_microservices_minus_monolith": None},
    {"invalid_payload_failures": [1]}, {"invalid_payload_signals_by_architecture": None},
    {"invalid_payload_signals_by_architecture": {}},
    {"invalid_payload_signal_totals_by_architecture": {}},
    {"invalid_payload_signals_by_architecture": {"force_monolith": None, "force_microservices": {}}},
])
def test_available_comparison_requires_exact_modes_and_typed_evidence(changes):
    assert reports.normalize_architecture_pilot_comparison({**_comparison(), **changes}) is None


def test_unavailable_comparison_does_not_preserve_stale_success_metrics():
    payload = {**_comparison(), "available": False}
    assert reports.normalize_architecture_pilot_comparison(payload) == {"available": False}


@pytest.mark.parametrize("changes", [
    {"stable": 1}, {"failures": None}, {"checks": None},
    {"artifact_count": -1}, {"artifact_count": "2"}, {"required_consecutive": 0},
    {"required_consecutive": "2"}, {"checks": [None]},
    {"checks": [{"stable": 1, "failures": []}]},
    {"checks": [{"stable": True, "failures": None}]},
    {"failures": ["contradiction"]}, {"stable": False},
    {"required_consecutive": 3},
    {"checks": [{"stable": True, "failures": []}, {"stable": False, "failures": ["failed"]}]},
])
def test_stability_claim_requires_sufficient_consistent_tail(changes):
    payload = {**_stability(), **changes}
    before = deepcopy(payload)
    assert reports.normalize_microservices_pilot_stability_report(payload) == {}
    assert payload == before


def test_failed_stability_preserves_diagnostic_evidence_and_copies_failure_lists():
    payload = _stability()
    payload.update(stable=False, failures=["insufficient stable tail"], operator_note="retained")
    payload["checks"][1] = {"stable": False, "failures": ["runtime failed"], "artifact": "run-2.json"}
    result = reports.normalize_microservices_pilot_stability_report(payload)
    assert result["stable"] is False and result["operator_note"] == "retained"
    assert result["checks"][1]["artifact"] == "run-2.json"
    result["checks"][1]["failures"].append("caller addition")
    assert payload["checks"][1]["failures"] == ["runtime failed"]
