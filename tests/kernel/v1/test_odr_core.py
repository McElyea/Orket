from __future__ import annotations

from orket.kernel.v1.odr.core import ReactorConfig, ReactorState, run_round


def _architect(requirement: str) -> str:
    return (
        "### REQUIREMENT\n"
        f"{requirement}\n\n"
        "### CHANGELOG\n"
        "- changed\n\n"
        "### ASSUMPTIONS\n"
        "- a1\n\n"
        "### OPEN_QUESTIONS\n"
        "- q1\n"
    )


def _auditor() -> str:
    return (
        "### CRITIQUE\n"
        "- c1\n\n"
        "### PATCHES\n"
        "- p1\n\n"
        "### EDGE_CASES\n"
        "- e1\n\n"
        "### TEST_GAPS\n"
        "- t1\n"
    )


def test_code_leak_triggers_and_null_parsed_fields() -> None:
    state = ReactorState()
    cfg = ReactorConfig()
    state = run_round(state, "```python\nprint('x')\n```", _auditor(), cfg)
    assert state.stop_reason == "CODE_LEAK"
    record = state.history_rounds[-1]
    assert record["architect_parsed"] is None
    assert record["auditor_parsed"] is None
    assert record["parse_errors"] == []


def test_diff_floor_triggers_with_stable_rounds() -> None:
    cfg = ReactorConfig(diff_floor_pct=0.05, stable_rounds=2)
    state = ReactorState()
    state = run_round(state, _architect("Alpha beta gamma delta epsilon."), _auditor(), cfg)
    assert state.stop_reason is None
    state = run_round(state, _architect("Alpha beta gamma delta epsilon!"), _auditor(), cfg)
    assert state.stop_reason is None
    state = run_round(state, _architect("Alpha beta gamma delta epsilon?"), _auditor(), cfg)
    assert state.stop_reason == "DIFF_FLOOR"


def test_circularity_triggers_and_metrics_present() -> None:
    cfg = ReactorConfig(diff_floor_pct=0.0001, stable_rounds=99, margin=0.02, min_loop_sim=0.5)
    state = ReactorState()
    state = run_round(
        state,
        _architect("Store all user data locally on the device and never upload it."),
        _auditor(),
        cfg,
    )
    state = run_round(
        state,
        _architect("Upload user data to remote servers for analysis and sharing."),
        _auditor(),
        cfg,
    )
    state = run_round(
        state,
        _architect("Store all user data locally on the device and do not upload it."),
        _auditor(),
        cfg,
    )
    assert state.stop_reason == "CIRCULARITY"
    metrics = state.history_rounds[-1]["metrics"]
    assert metrics["sim_prev"] is not None
    assert metrics["sim_loop"] is not None


def test_shape_violation_emits_parse_errors_and_null_parsed_fields() -> None:
    state = ReactorState()
    cfg = ReactorConfig()
    broken_architect = (
        "### REQUIREMENT\nX\n\n"
        "### CHANGELOG\n- c\n\n"
        "### OPEN_QUESTIONS\n- q\n"
    )
    state = run_round(state, broken_architect, _auditor(), cfg)
    assert state.stop_reason == "SHAPE_VIOLATION"
    record = state.history_rounds[-1]
    assert record["architect_parsed"] is None
    assert record["auditor_parsed"] is None
    assert any(err["source"] == "architect" for err in record["parse_errors"])


def test_max_rounds_triggers_when_n_equals_max_rounds() -> None:
    cfg = ReactorConfig(max_rounds=2)
    state = ReactorState()
    state = run_round(state, _architect("r1"), _auditor(), cfg)
    assert state.stop_reason is None
    state = run_round(state, _architect("r2"), _auditor(), cfg)
    assert state.stop_reason == "MAX_ROUNDS"


def test_trace_completeness_and_noop_after_stop() -> None:
    cfg = ReactorConfig(max_rounds=1)
    state = ReactorState()
    state = run_round(state, _architect("only"), _auditor(), cfg)
    assert state.stop_reason == "MAX_ROUNDS"
    assert len(state.history_rounds) == 1
    record = state.history_rounds[0]
    for key in (
        "round",
        "run_config",
        "architect_raw",
        "auditor_raw",
        "architect_parsed",
        "auditor_parsed",
        "parse_errors",
        "metrics",
        "stop_reason",
    ):
        assert key in record
    state2 = run_round(state, _architect("ignored"), _auditor(), cfg)
    assert state2 is state
    assert len(state2.history_rounds) == 1


def test_leading_preface_before_header_is_shape_violation() -> None:
    state = ReactorState()
    cfg = ReactorConfig()
    preface_auditor = (
        "Note: quick preface before sections.\n\n"
        "### CRITIQUE\n"
        "- c1\n\n"
        "### PATCHES\n"
        "- p1\n\n"
        "### EDGE_CASES\n"
        "- e1\n\n"
        "### TEST_GAPS\n"
        "- t1\n"
    )
    state = run_round(state, _architect("v1"), preface_auditor, cfg)
    assert state.stop_reason == "SHAPE_VIOLATION"
    record = state.history_rounds[-1]
    assert record["auditor_parsed"] is None
    assert any(
        err["source"] == "auditor"
        and err["code"] in {"HEADER_OUT_OF_ORDER", "MISSING_HEADER"}
        and "out of order" in str(err["message"]).lower()
        for err in record["parse_errors"]
    )
