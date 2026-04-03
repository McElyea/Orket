from __future__ import annotations

from types import SimpleNamespace

import pytest

from orket.core.cards_runtime_contract import (
    CRITIQUE_COMMENT_EXECUTION_PROFILE,
    ODR_EXECUTION_PROFILE,
    REVIEW_COMMENT_EXECUTION_PROFILE,
    TRUTHFUL_BLOCK_ONLY_EXECUTION_PROFILE,
    normalize_scenario_truth_alignment,
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


def test_resolve_cards_runtime_comment_profile_uses_empty_artifact_contract_by_default() -> None:
    issue = SimpleNamespace(
        seat="reviewer",
        params={
            "execution_profile": REVIEW_COMMENT_EXECUTION_PROFILE,
        },
    )

    runtime = resolve_cards_runtime(issue=issue)

    assert runtime["execution_profile"] == REVIEW_COMMENT_EXECUTION_PROFILE
    assert runtime["profile_traits"]["intent"] == "review_comment"
    assert runtime["artifact_contract"]["kind"] == "none"
    assert runtime["artifact_contract"]["required_write_paths"] == []


def test_resolve_cards_runtime_block_profile_rejects_declared_artifact_outputs() -> None:
    issue = SimpleNamespace(
        seat="market_researcher",
        params={
            "execution_profile": TRUTHFUL_BLOCK_ONLY_EXECUTION_PROFILE,
            "artifact_contract": {
                "kind": "artifact",
                "primary_output": "agent_output/out.txt",
                "required_write_paths": ["agent_output/out.txt"],
            },
        },
    )

    runtime = resolve_cards_runtime(issue=issue)

    assert runtime["invalid_profile_reason"] == "comment_or_block_profile_selected_for_artifact_contract"


def test_resolve_cards_runtime_preserves_artifact_semantic_checks() -> None:
    issue = SimpleNamespace(
        seat="coder",
        params={
            "execution_profile": "build_app_v1",
            "artifact_contract": {
                "kind": "app",
                "primary_output": "agent_output/main.py",
                "entrypoint_path": "agent_output/main.py",
                "required_write_paths": ["agent_output/main.py"],
                "semantic_checks": [
                    {
                        "path": "agent_output/main.py",
                        "label": "script-safe proof entrypoint",
                        "must_contain": ["from challenge_runtime", "json.dumps"],
                        "must_not_contain": ["from .challenge_runtime"],
                    }
                ],
            },
        },
    )

    runtime = resolve_cards_runtime(issue=issue)

    assert runtime["artifact_contract"]["semantic_checks"] == [
        {
            "path": "agent_output/main.py",
            "label": "script-safe proof entrypoint",
            "must_contain": ["from challenge_runtime", "json.dumps"],
            "must_not_contain": ["from .challenge_runtime"],
        }
    ]


def test_summarize_cards_runtime_issues_carries_shared_scenario_truth() -> None:
    summary = summarize_cards_runtime_issues(
        [
            {
                "issue_id": "RMS-20",
                "execution_profile": CRITIQUE_COMMENT_EXECUTION_PROFILE,
                "scenario_truth": {
                    "scenario_id": "role_matrix_soak_v1",
                    "blocked_issue_policy": {
                        "allowed_issue_ids": ["RMS-22"],
                        "blocked_implies_run_failure": True,
                    },
                    "expected_terminal_status": "terminal_failure",
                },
            },
            {
                "issue_id": "RMS-21",
                "execution_profile": "write_artifact_v1",
                "scenario_truth": {
                    "scenario_id": "role_matrix_soak_v1",
                    "blocked_issue_policy": {
                        "allowed_issue_ids": ["RMS-22"],
                        "blocked_implies_run_failure": True,
                    },
                    "expected_terminal_status": "terminal_failure",
                },
            },
        ]
    )

    assert summary["execution_profile"] == "mixed"
    assert summary["scenario_truth"]["scenario_id"] == "role_matrix_soak_v1"
    assert summary["scenario_truth"]["blocked_issue_policy"]["allowed_issue_ids"] == ["RMS-22"]


def test_normalize_scenario_truth_alignment_reports_expected_terminal_status_match() -> None:
    alignment = normalize_scenario_truth_alignment(
        scenario_truth={
            "scenario_id": "role_matrix_soak_v1",
            "blocked_issue_policy": {
                "allowed_issue_ids": ["RMS-22"],
                "blocked_implies_run_failure": True,
            },
            "expected_terminal_status": "terminal_failure",
        },
        observed_terminal_status="terminal_failure",
    )

    assert alignment["scenario_id"] == "role_matrix_soak_v1"
    assert alignment["expected_terminal_status_match"] is True
