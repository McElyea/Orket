from __future__ import annotations

import pytest

from orket.kernel.v1.odr.core import ReactorConfig, ReactorState, run_round
from orket.kernel.v1.odr.leak_policy import detect_code_leak


def _architect_valid(requirement: str) -> str:
    return (
        "### REQUIREMENT\n"
        f"{requirement}\n\n"
        "### CHANGELOG\n"
        "- c\n\n"
        "### ASSUMPTIONS\n"
        "- a\n\n"
        "### OPEN_QUESTIONS\n"
        "- q\n"
    )


def _auditor_valid(text: str) -> str:
    return (
        "### CRITIQUE\n"
        f"- {text}\n\n"
        "### PATCHES\n"
        "- p\n\n"
        "### EDGE_CASES\n"
        "- e\n\n"
        "### TEST_GAPS\n"
        "- t\n"
    )


def test_balanced_mode_does_not_hard_fail_on_weak_tokens_only() -> None:
    result = detect_code_leak(
        architect_raw=_architect_valid("Store data locally."),
        auditor_raw=_auditor_valid("Define type-sensitive interface behavior in plain prose."),
        mode="balanced_v1",
    )
    assert result.hard_leak is False
    assert any(item["token"] in {"type", "interface"} for item in result.matches_weak)
    assert any(warn.startswith("WARN_LEAK_WEAK_TOKEN:") for warn in result.warnings)


def test_strict_mode_keeps_legacy_keyword_hard_fail() -> None:
    result = detect_code_leak(
        architect_raw=_architect_valid("Store data locally."),
        auditor_raw=_auditor_valid("Define type-sensitive interface behavior in plain prose."),
        mode="strict",
    )
    assert result.hard_leak is True
    assert result.matches_hard


def test_balanced_mode_hard_fails_on_anchored_python_def() -> None:
    result = detect_code_leak(
        architect_raw=_architect_valid("Store data locally."),
        auditor_raw=_auditor_valid("def tighten_policy(value):\n    return value"),
        mode="balanced_v1",
    )
    assert result.hard_leak is True
    assert "CODE" in result.classes


def test_balanced_mode_tooling_without_cli_context_is_warning_only() -> None:
    result = detect_code_leak(
        architect_raw=_architect_valid("Store data locally."),
        auditor_raw=_auditor_valid("Avoid docker dependencies in this local requirement."),
        mode="balanced_v1",
    )
    assert result.hard_leak is False
    assert any(item["detector"] == "tooling_without_context" for item in result.matches_weak)


def test_balanced_mode_tooling_with_cli_context_is_hard_fail() -> None:
    result = detect_code_leak(
        architect_raw=_architect_valid("Store data locally."),
        auditor_raw=_auditor_valid("Run docker --rm alpine && echo done."),
        mode="balanced_v1",
    )
    assert result.hard_leak is True
    assert "TOOLING" in result.classes


def test_balanced_mode_fallback_requires_structural_signal() -> None:
    result = detect_code_leak(
        architect_raw=_architect_valid("Store data locally."),
        auditor_raw=_auditor_valid("Let f(x)=y and a->b and g(z) describe the relation."),
        mode="balanced_v1",
    )
    assert result.hard_leak is False


def test_balanced_mode_fallback_triggers_with_structural_combo() -> None:
    pseudo = (
        "{\n"
        "    value = compute(x);\n"
        "    next = call(y);\n"
        "}\n"
    )
    result = detect_code_leak(
        architect_raw=_architect_valid("Store data locally."),
        auditor_raw=_auditor_valid(pseudo),
        mode="balanced_v1",
    )
    assert result.hard_leak is True
    assert "CODE" in result.classes


def test_balanced_mode_fence_detection_requires_exact_three_backtick_close() -> None:
    bad_close = "```python\nprint('x')\n````"
    result = detect_code_leak(
        architect_raw=_architect_valid("Store data locally."),
        auditor_raw=_auditor_valid(bad_close),
        mode="balanced_v1",
    )
    assert result.hard_leak is False

    good_close = "```python\nprint('x')\n```"
    result2 = detect_code_leak(
        architect_raw=_architect_valid("Store data locally."),
        auditor_raw=_auditor_valid(good_close),
        mode="balanced_v1",
    )
    assert result2.hard_leak is True
    assert "FENCE" in result2.classes


def test_context_snippet_is_bounded_and_normalized() -> None:
    long_text = ("x" * 150) + "\n interface " + ("y" * 150)
    result = detect_code_leak(
        architect_raw=_architect_valid("Store data locally."),
        auditor_raw=_auditor_valid(long_text),
        mode="balanced_v1",
    )
    assert result.matches_weak
    snippet = str(result.matches_weak[0].get("context_snippet") or "")
    assert len(snippet) <= 120
    assert "\n" not in snippet
    assert snippet == snippet.strip()


def test_run_round_propagates_hard_leak_fields() -> None:
    cfg = ReactorConfig(leak_gate_mode="balanced_v1")
    state = ReactorState()
    state = run_round(state, _architect_valid("Store data locally."), _auditor_valid("def x(y): return y"), cfg)
    assert state.stop_reason == "CODE_LEAK"
    row = state.history_rounds[-1]
    assert row["metrics"]["code_leak_hit"] is True
    assert row["stop_reason"] == "CODE_LEAK"
    assert isinstance(row.get("code_leak_matches_hard"), list) and row["code_leak_matches_hard"]


def test_run_round_code_leak_precedence_over_shape_violation() -> None:
    cfg = ReactorConfig(leak_gate_mode="balanced_v1")
    state = ReactorState()
    broken_architect = (
        "### REQUIREMENT\nStore data locally.\n\n"
        "### CHANGELOG\n- c\n\n"
        "### OPEN_QUESTIONS\n- q\n"
    )
    state = run_round(state, broken_architect, _auditor_valid("def x(y): return y"), cfg)
    assert state.stop_reason == "CODE_LEAK"


@pytest.mark.parametrize(
    "snippet,expected_class",
    [
        ("```python\nprint('x')\n```", "FENCE"),
        ("def compute(v):\n    return v", "CODE"),
        ("class Policy:\n    pass", "CODE"),
        ("from pkg.module import value", "CODE"),
        ("import json", "CODE"),
        ("interface PolicyContract {}", "CODE"),
        ("type Policy = { id: string }", "CODE"),
        ("const policy = {}", "CODE"),
        ("let policy = {}", "CODE"),
        ("var policy = {}", "CODE"),
        ("function policy() { return 1; }", "CODE"),
        ("Run docker --rm alpine", "TOOLING"),
        ("pip install x --quiet", "TOOLING"),
        ("cargo run --release", "TOOLING"),
        ("npm install pkg && npm run test", "TOOLING"),
        ("python -m pip install x", "TOOLING"),
        ("bash -lc \"echo hi\"", "TOOLING"),
        ("sh -c \"echo hi\"", "TOOLING"),
        ("node --version", "TOOLING"),
        ("{\n    a = f(x);\n    b = g(y);\n}", "CODE"),
    ],
)
def test_curated_hard_leak_fixture_gate(snippet: str, expected_class: str) -> None:
    cfg = ReactorConfig(leak_gate_mode="balanced_v1")
    state = ReactorState()
    state = run_round(state, _architect_valid("Store data locally."), _auditor_valid(snippet), cfg)
    row = state.history_rounds[-1]
    assert row["metrics"]["code_leak_hit"] is True
    assert row["stop_reason"] == "CODE_LEAK"
    assert row.get("code_leak_matches_hard")
    assert expected_class in set(row.get("code_leak_classes") or [])
