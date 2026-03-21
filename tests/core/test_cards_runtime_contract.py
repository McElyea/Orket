from __future__ import annotations

from types import SimpleNamespace

import pytest

from orket.core.cards_runtime_contract import (
    ODR_EXECUTION_PROFILE,
    resolve_cards_runtime,
    summarize_cards_runtime_issues,
)

pytestmark = pytest.mark.unit


def test_resolve_cards_runtime_exposes_cached_odr_result_fields() -> None:
    issue = SimpleNamespace(
        seat="coder",
        params={
            "execution_profile": ODR_EXECUTION_PROFILE,
            "artifact_contract": {
                "kind": "artifact",
                "primary_output": "agent_output/out.py",
                "required_write_paths": ["agent_output/out.py"],
            },
            "odr_result": {
                "odr_valid": True,
                "odr_pending_decisions": 0,
                "odr_stop_reason": "STABLE_DIFF_FLOOR",
                "odr_artifact_path": "observability/run/ISSUE/odr_refinement.json",
                "odr_requirement": "Write agent_output/out.py with a deterministic add(a, b) function.",
            },
        },
    )

    runtime = resolve_cards_runtime(issue=issue)

    assert runtime["execution_profile"] == ODR_EXECUTION_PROFILE
    assert runtime["odr_active"] is True
    assert runtime["odr_valid"] is True
    assert runtime["odr_pending_decisions"] == 0
    assert runtime["odr_stop_reason"] == "STABLE_DIFF_FLOOR"
    assert runtime["odr_artifact_path"] == "observability/run/ISSUE/odr_refinement.json"
    assert runtime["odr_requirement"].startswith("Write agent_output/out.py")


def test_summarize_cards_runtime_issues_carries_odr_artifact_path() -> None:
    summary = summarize_cards_runtime_issues(
        [
            {
                "issue_id": "ISSUE-1",
                "execution_profile": ODR_EXECUTION_PROFILE,
                "odr_active": True,
                "odr_valid": False,
                "odr_pending_decisions": 2,
                "odr_stop_reason": "UNRESOLVED_DECISIONS",
                "odr_artifact_path": "observability/run/ISSUE-1/odr_refinement.json",
            }
        ]
    )

    assert summary["execution_profile"] == ODR_EXECUTION_PROFILE
    assert summary["odr_active"] is True
    assert summary["odr_valid"] is False
    assert summary["odr_pending_decisions"] == 2
    assert summary["odr_stop_reason"] == "UNRESOLVED_DECISIONS"
    assert summary["odr_artifact_path"] == "observability/run/ISSUE-1/odr_refinement.json"


def test_resolve_cards_runtime_preserves_configured_odr_auditor_model() -> None:
    issue = SimpleNamespace(
        seat="coder",
        params={
            "execution_profile": ODR_EXECUTION_PROFILE,
            "artifact_contract": {
                "kind": "artifact",
                "primary_output": "agent_output/out.py",
                "required_write_paths": ["agent_output/out.py"],
            },
            "cards_runtime": {
                "odr_auditor_model": "qwen2.5:7b",
            },
        },
    )

    runtime = resolve_cards_runtime(issue=issue)

    assert runtime["odr_auditor_model"] == "qwen2.5:7b"
