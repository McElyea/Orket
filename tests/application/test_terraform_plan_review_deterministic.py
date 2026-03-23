from __future__ import annotations

import json

import pytest

from orket.application.terraform_review.deterministic import analyze_plan, parse_plan_json

from tests.application.terraform_plan_review_support import load_fixture_case, load_fixture_manifest


@pytest.mark.contract
def test_terraform_fixture_manifest_locks_expected_outcomes() -> None:
    """Layer: contract. Verifies every Terraform fixture carries verdict and publish expectations explicitly."""
    manifest = load_fixture_manifest()
    assert manifest
    for payload in manifest.values():
        assert "expected_publish_decision" in payload
        assert "expected_summary_status" in payload
        assert "expected_final_verdict_source" in payload


@pytest.mark.unit
def test_deterministic_analysis_classifies_replace_and_records_forbidden_hit() -> None:
    """Layer: unit. Verifies Terraform replace actions normalize to the v1 forbidden-operation contract."""
    case = load_fixture_case("explicit_replace")
    plan_payload = json.loads(case.plan_bytes.decode("utf-8"))
    analysis = analyze_plan(plan_payload=plan_payload, forbidden_operations=case.forbidden_operations)
    assert analysis.analysis_complete is True
    assert analysis.action_counts["replace"] == 1
    assert [item.operation for item in analysis.forbidden_operation_hits] == ["replace"]


@pytest.mark.unit
def test_parse_plan_json_rejects_invalid_json() -> None:
    """Layer: unit. Verifies invalid Terraform JSON input fails closed before deterministic verdicting."""
    case = load_fixture_case("invalid_json_plan")
    payload, error = parse_plan_json(case.plan_bytes)
    assert payload is None
    assert error == "invalid_json_plan"
