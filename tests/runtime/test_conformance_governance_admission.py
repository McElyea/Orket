"""Structural governance contract admission, not execution of its declared gates."""
from copy import deepcopy

import pytest

from orket.runtime.policy.conformance_governance_contract import (
    conformance_governance_contract_snapshot,
    validate_conformance_governance_contract,
)

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("case,error", [
    ("empty", "EMPTY"), ("nonobject", "ROW_SCHEMA"), ("missing-id", "SECTION_ID_REQUIRED"),
    ("unknown-id", "SECTION_UNKNOWN:unknown"), ("duplicate", "DUPLICATE_SECTION"),
])
def test_section_admission_refuses_ambiguous_or_incomplete_authority(case, error):
    payload = conformance_governance_contract_snapshot()
    if case == "empty":
        payload["sections"] = []
    elif case == "nonobject":
        payload["sections"][0] = []
    elif case == "missing-id":
        payload["sections"][0]["section_id"] = " "
    elif case == "unknown-id":
        payload["sections"][0]["section_id"] = "unknown"
    else:
        payload["sections"].append(deepcopy(payload["sections"][0]))
    before = deepcopy(payload)
    with pytest.raises(ValueError, match="E_CONFORMANCE_GOVERNANCE_CONTRACT_" + error):
        validate_conformance_governance_contract(payload)
    assert payload == before


@pytest.mark.parametrize("section,field,value,error", [
    ("behavioral_contract_suite", "structural_targets", [], "BEHAVIORAL_TARGETS_MISMATCH"),
    ("behavioral_contract_suite", "live_target", "tests/unit/claim.py", "BEHAVIORAL_LIVE_TARGET_INVALID"),
    ("behavioral_contract_suite", "blocking_claims", [], "BLOCKING_CLAIMS_MISMATCH"),
    ("false_green_hunt_process", "cadence", "optional", "FALSE_GREEN_CADENCE_INVALID"),
    ("false_green_hunt_process", "authorities", [], "FALSE_GREEN_AUTHORITIES_MISMATCH"),
    ("false_green_hunt_process", "checklist_items", [], "FALSE_GREEN_CHECKLIST_MISMATCH"),
    ("golden_transcript_diff_policy", "baseline_artifact_library", "unknown", "GOLDEN_LIBRARY_INVALID"),
    ("golden_transcript_diff_policy", "baseline_artifact_types", [], "GOLDEN_TYPES_MISMATCH"),
    ("golden_transcript_diff_policy", "diff_mode", "uncontrolled", "GOLDEN_DIFF_MODE_INVALID"),
    ("golden_transcript_diff_policy", "block_on", [], "GOLDEN_BLOCKERS_MISMATCH"),
    ("operator_signoff_bundle", "required_sections", [], "SIGNOFF_SECTIONS_MISMATCH"),
    ("operator_signoff_bundle", "required_decision_fields", [], "SIGNOFF_DECISION_FIELDS_MISMATCH"),
    ("operator_signoff_bundle", "required_operator_action_when_eligible", "automatic", "SIGNOFF_ACTION_INVALID"),
    ("repo_introspection_report", "source_artifacts", [], "REPO_SOURCES_MISMATCH"),
    ("repo_introspection_report", "required_fields", [], "REPO_FIELDS_MISMATCH"),
    ("repo_introspection_report", "output_dir", "unrecorded", "REPO_OUTPUT_DIR_INVALID"),
    ("cross_spec_consistency_checker", "required_checks", [], "CROSS_SPEC_CHECKS_MISMATCH"),
    ("cross_spec_consistency_checker", "failure_policy", "ignore", "CROSS_SPEC_FAILURE_POLICY_INVALID"),
    ("cross_spec_consistency_checker", "docs_hygiene_command", "true", "CROSS_SPEC_COMMAND_INVALID"),
])
def test_each_required_governance_field_has_specific_drift_refusal(section, field, value, error):
    payload = conformance_governance_contract_snapshot()
    row = next(row for row in payload["sections"] if row["section_id"] == section)
    row[field] = value
    before = deepcopy(payload)
    with pytest.raises(ValueError, match="E_CONFORMANCE_GOVERNANCE_CONTRACT_" + error):
        validate_conformance_governance_contract(payload)
    assert payload == before


def test_section_order_does_not_change_validated_authority_or_mutate_snapshot():
    original = conformance_governance_contract_snapshot()
    reordered = deepcopy(original)
    reordered["sections"].reverse()
    before = deepcopy(reordered)
    assert validate_conformance_governance_contract(reordered) == validate_conformance_governance_contract(original)
    assert reordered == before and conformance_governance_contract_snapshot() == original
