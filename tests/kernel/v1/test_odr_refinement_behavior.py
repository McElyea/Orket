from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from orket.kernel.v1.odr.core import ReactorConfig, ReactorState, run_round
from orket.kernel.v1.odr.refinement import (
    auditor_incorporation_gaps,
    carry_forward_gaps,
    extract_constraints_ledger,
    forbidden_pattern_hits,
    missing_required_sections,
    non_increasing,
    reopened_issues,
    unresolved_issue_count,
)

FIXTURE_ROOT = Path(__file__).parent / "vectors" / "odr" / "refinement"


def _load_scenarios() -> List[Dict[str, Any]]:
    return json.loads((FIXTURE_ROOT / "scenarios.json").read_text(encoding="utf-8"))


def _read_markdown(scenario_path: str, name: str) -> str:
    return (FIXTURE_ROOT / scenario_path / name).read_text(encoding="utf-8")


def _read_issues(scenario_path: str, name: str) -> List[Dict[str, Any]]:
    return json.loads((FIXTURE_ROOT / scenario_path / name).read_text(encoding="utf-8"))


def _architect_payload(requirement: str, round_index: int) -> str:
    return (
        "### REQUIREMENT\n"
        f"{requirement}\n\n"
        "### CHANGELOG\n"
        f"- round-{round_index}\n\n"
        "### ASSUMPTIONS\n"
        "- deterministic fixture\n\n"
        "### OPEN_QUESTIONS\n"
        "- none\n"
    )


def _auditor_payload(round_index: int) -> str:
    return (
        "### CRITIQUE\n"
        f"- round-{round_index}\n\n"
        "### PATCHES\n"
        "- none\n\n"
        "### EDGE_CASES\n"
        "- none\n\n"
        "### TEST_GAPS\n"
        "- none\n"
    )


def _run_requirement_rounds(requirements: List[str]) -> ReactorState:
    state = ReactorState()
    cfg = ReactorConfig(max_rounds=8, diff_floor_pct=0.0, stable_rounds=99, code_leak_patterns=[])
    for idx, requirement in enumerate(requirements):
        state = run_round(state, _architect_payload(requirement, idx), _auditor_payload(idx), cfg)
        if state.stop_reason is not None:
            break
    return state


@pytest.mark.parametrize("scenario", _load_scenarios(), ids=lambda row: row["id"])
def test_refinement_constraint_carry_forward(scenario: Dict[str, Any]) -> None:
    r0 = _read_markdown(scenario["path"], "R0.md")
    r1 = _read_markdown(scenario["path"], "R1.md")

    gaps = carry_forward_gaps(extract_constraints_ledger(r0), extract_constraints_ledger(r1))
    assert gaps == [], f"missing carry-forward constraint ids: {gaps}"


@pytest.mark.parametrize("scenario", _load_scenarios(), ids=lambda row: row["id"])
def test_refinement_auditor_incorporation(scenario: Dict[str, Any]) -> None:
    a0 = _read_issues(scenario["path"], "A0.json")
    r1 = _read_markdown(scenario["path"], "R1.md")

    gaps = auditor_incorporation_gaps(a0, extract_constraints_ledger(r1))
    assert gaps == [], f"auditor issues not addressed/declined: {gaps}"


@pytest.mark.parametrize("scenario", _load_scenarios(), ids=lambda row: row["id"])
def test_refinement_forbidden_regressions(scenario: Dict[str, Any]) -> None:
    r1 = _read_markdown(scenario["path"], "R1.md")
    hits = forbidden_pattern_hits(r1, scenario.get("forbidden_patterns", []))
    assert hits == [], f"forbidden patterns found in requirement text: {hits}"


@pytest.mark.parametrize("scenario", _load_scenarios(), ids=lambda row: row["id"])
def test_refinement_structural_checklist(scenario: Dict[str, Any]) -> None:
    r1 = _read_markdown(scenario["path"], "R1.md")
    missing = missing_required_sections(r1)
    assert missing == [], f"missing required sections: {missing}"


@pytest.mark.parametrize("scenario", _load_scenarios(), ids=lambda row: row["id"])
def test_refinement_convergence_monotonic(scenario: Dict[str, Any]) -> None:
    requirements = [
        _read_markdown(scenario["path"], "R0.md"),
        _read_markdown(scenario["path"], "R1.md"),
        _read_markdown(scenario["path"], "R2.md"),
    ]
    issues = [
        _read_issues(scenario["path"], "A0.json"),
        _read_issues(scenario["path"], "A1.json"),
        _read_issues(scenario["path"], "A2.json"),
    ]

    counts = [unresolved_issue_count(rows) for rows in issues]
    assert counts == scenario["expected_unresolved"], (
        f"unexpected unresolved count curve for {scenario['id']}: "
        f"expected={scenario['expected_unresolved']} actual={counts}"
    )
    assert non_increasing(counts), f"unresolved issues increased: {counts}"

    reopened = reopened_issues(issues)
    assert reopened == [], f"resolved issue reopened without explicit reason: {reopened}"

    state = _run_requirement_rounds(requirements)
    assert len(state.history_v) >= 2
    assert state.stop_reason in {None, "DIFF_FLOOR", "CIRCULARITY", "MAX_ROUNDS"}
    assert state.stop_reason != "SHAPE_VIOLATION"
