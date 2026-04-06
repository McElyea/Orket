from __future__ import annotations

import pytest

from orket.kernel.v1.odr.core import ReactorConfig, ReactorState, check_code_leak, run_round
from orket.kernel.v1.odr.leak_policy import DEFAULT_LEAK_GATE_MODE, detect_code_leak
from orket.kernel.v1.odr.live_runner import run_live_refinement
from orket.kernel.v1.odr.metrics import diff_ratio
from orket.kernel.v1.odr.semantic_validity import (
    _contradiction_hits,
    _unresolved_alternative_hits,
    evaluate_semantic_validity,
)

pytestmark = pytest.mark.unit


def _architect(requirement: str) -> str:
    return (
        "### REQUIREMENT\n"
        f"{requirement}\n\n"
        "### CHANGELOG\n"
        "- changed\n\n"
        "### ASSUMPTIONS\n"
        "- a1\n\n"
        "### OPEN_QUESTIONS\n"
        "- none\n"
    )


def _auditor() -> str:
    return (
        "### CRITIQUE\n"
        "- c1\n\n"
        "### PATCHES\n"
        "- [ADD] p1\n\n"
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
    assert state.stop_reason == "STABLE_DIFF_FLOOR"


def test_must_not_alone_does_not_fire_contradiction() -> None:
    text = "The system must not store data outside the jurisdiction."
    assert _contradiction_hits(text) == []


def test_genuine_contradiction_fires() -> None:
    text = "The system must retain user data. The system must delete user data after 30 days."
    assert "retain|delete" in _contradiction_hits(text)


def test_or_in_requirement_does_not_fire_unresolved() -> None:
    assert _unresolved_alternative_hits("The system must encrypt or hash all stored passwords.") == []


def test_may_in_requirement_does_not_fire_unresolved() -> None:
    assert _unresolved_alternative_hits("The cache layer may store results for up to 10 seconds.") == []


def test_either_or_fires_unresolved() -> None:
    hits = _unresolved_alternative_hits("The system must use either AES-128 or AES-256 for encryption.")
    assert len(hits) >= 1


def test_depending_on_fires_unresolved() -> None:
    hits = _unresolved_alternative_hits("Retention must be 30 or 90 days depending on account tier.")
    assert len(hits) >= 1


def test_diff_ratio_same_length_different_content_is_nonzero() -> None:
    ratio = diff_ratio("must store data locally on device here", "must upload data remotely to cloud now")
    assert ratio > 0.3


def test_diff_ratio_identical_content_is_zero() -> None:
    text = "The system must encrypt all stored credentials at rest."
    assert diff_ratio(text, text) == 0.0


def test_circularity_triggers_and_metrics_present() -> None:
    cfg = ReactorConfig(diff_floor_pct=0.0001, stable_rounds=99, margin=0.02, min_loop_sim=0.4)
    state = ReactorState()
    state = run_round(
        state,
        _architect("Keep all user data on the device and never transmit it."),
        _auditor(),
        cfg,
    )
    state = run_round(
        state,
        _architect("Transmit user data to remote servers for analysis and sharing."),
        _auditor(),
        cfg,
    )
    state = run_round(
        state,
        _architect("Keep all user data on the device and do not transmit it."),
        _auditor(),
        cfg,
    )
    assert state.stop_reason == "LOOP_DETECTED"
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
    assert state.stop_reason == "FORMAT_VIOLATION"
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
    assert state.history_rounds[-1]["max_hit"] is True


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


def test_pending_decisions_stop_as_unresolved_decisions() -> None:
    cfg = ReactorConfig(max_rounds=1, diff_floor_pct=0.05, stable_rounds=1)
    state = ReactorState()
    architect = (
        "### REQUIREMENT\n"
        "The tool must rename files. DECISION_REQUIRED(naming_template): "
        "no fallback template specified.\n\n"
        "### CHANGELOG\n"
        "- changed\n\n"
        "### ASSUMPTIONS\n"
        "- a1\n\n"
        "### OPEN_QUESTIONS\n"
        "- none\n"
    )
    state = run_round(state, architect, _auditor(), cfg)
    assert state.stop_reason == "MAX_ROUNDS"
    record = state.history_rounds[-1]
    assert record["validity_verdict"] == "invalid"
    assert record["pending_decision_count"] >= 1
    assert any("naming_template" in str(item).lower() for item in record["pending_decisions"])


def test_stable_count_resets_when_invalid_round_interrupts_valid_sequence() -> None:
    cfg = ReactorConfig(max_rounds=5, diff_floor_pct=0.99, stable_rounds=2)
    state = ReactorState()
    state = run_round(
        state,
        _architect("The system must encrypt all backups at rest."),
        _auditor(),
        cfg,
    )
    state = run_round(
        state,
        _architect("The system must encrypt all backups at rest!"),
        _auditor(),
        cfg,
    )
    assert state.stop_reason is None
    assert state.stable_count == 1

    invalid_architect = (
        "### REQUIREMENT\n"
        "DECISION_REQUIRED(retention_days): retention period not yet specified.\n\n"
        "### CHANGELOG\n"
        "- changed\n\n"
        "### ASSUMPTIONS\n"
        "- a1\n\n"
        "### OPEN_QUESTIONS\n"
        "- none\n"
    )
    state = run_round(state, invalid_architect, _auditor(), cfg)
    assert state.stop_reason is None
    assert state.stable_count == 0
    assert state.history_rounds[-1]["metrics"]["stable_count"] == 0

    state = run_round(
        state,
        _architect("The system must encrypt all backups at rest."),
        _auditor(),
        cfg,
    )
    assert state.stop_reason is None
    assert state.stable_count == 1


def test_remove_patch_suppresses_demotion_violation() -> None:
    previous_data = {
        "requirement": "The system must encrypt all backups at rest.",
        "changelog": [],
        "assumptions": [],
        "open_questions": [],
    }
    current_data = {
        "requirement": "The system handles backups.",
        "changelog": ["removed encryption clause per auditor"],
        "assumptions": [],
        "open_questions": [],
    }
    auditor_data = {
        "critique": ["Encryption clause incorrect and should be removed."],
        "patches": ["[REMOVE] The encryption at rest requirement is not applicable here."],
        "edge_cases": [],
        "test_gaps": [],
    }

    result = evaluate_semantic_validity(
        architect_data=current_data,
        auditor_data=auditor_data,
        previous_architect_data=previous_data,
    )

    assert result["validity_verdict"] == "valid"
    assert result["semantic_failures"] == []
    assert result["constraint_demotion_violations"] == []
    assert result["required_constraint_regressions"] == []


def test_constraint_demotion_stops_as_invalid_convergence_via_diff_floor() -> None:
    cfg = ReactorConfig(max_rounds=8, diff_floor_pct=0.99, stable_rounds=1)
    state = ReactorState()
    state = run_round(
        state,
        _architect("The system must encrypt all backups at rest."),
        _auditor(),
        cfg,
    )
    demoted = (
        "### REQUIREMENT\n"
        "The system handles backups.\n\n"
        "### CHANGELOG\n"
        "- changed\n\n"
        "### ASSUMPTIONS\n"
        "- All backups remain encrypted at rest.\n\n"
        "### OPEN_QUESTIONS\n"
        "- none\n"
    )
    state = run_round(state, demoted, _auditor(), cfg)
    state = run_round(state, demoted, _auditor(), cfg)
    assert state.stop_reason == "INVALID_CONVERGENCE"
    record = state.history_rounds[-1]
    assert record["validity_verdict"] == "invalid"
    assert record["constraint_demotion_violations"]
    assert record["metrics"]["stable_count"] == 0
    assert int(record["metrics"]["invalid_stable_count"]) >= 1


class _FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    async def complete(self, _messages):
        return {"content": self._responses.pop(0)}


class _RecordingClient(_FakeClient):
    def __init__(self, responses: list[str]) -> None:
        super().__init__(responses)
        self.messages: list[list[dict[str, str]]] = []

    async def complete(self, messages):
        self.messages.append(list(messages))
        return await super().complete(messages)


@pytest.mark.asyncio
async def test_run_live_refinement_exposes_valid_history_trace() -> None:
    architect_client = _FakeClient(
        [
            _architect("The system must encrypt all backups at rest."),
            (
                "### REQUIREMENT\n"
                "DECISION_REQUIRED(retention_days): retention period not yet specified.\n\n"
                "### CHANGELOG\n"
                "- changed\n\n"
                "### ASSUMPTIONS\n"
                "- a1\n\n"
                "### OPEN_QUESTIONS\n"
                "- none\n"
            ),
            (
                "### REQUIREMENT\n"
                "DECISION_REQUIRED(retention_days): retention period not yet specified.\n\n"
                "### CHANGELOG\n"
                "- changed\n\n"
                "### ASSUMPTIONS\n"
                "- a1\n\n"
                "### OPEN_QUESTIONS\n"
                "- none\n"
            ),
        ]
    )
    auditor_client = _FakeClient([_auditor(), _auditor(), _auditor()])

    result = await run_live_refinement(
        task="Refine retention requirements.",
        architect_client=architect_client,
        auditor_client=auditor_client,
        max_rounds=3,
    )

    assert result["stop_reason"] == "MAX_ROUNDS"
    assert result["history_v"] == [
        "The system must encrypt all backups at rest.",
        "DECISION_REQUIRED(retention_days): retention period not yet specified.",
        "DECISION_REQUIRED(retention_days): retention period not yet specified.",
    ]
    assert result["valid_history_v"] == ["The system must encrypt all backups at rest."]
    assert result["odr_failure_mode"] == "semantic_invalid"


@pytest.mark.asyncio
async def test_run_live_refinement_prompts_from_last_valid_requirement_after_invalid_round() -> None:
    architect_client = _RecordingClient(
        [
            _architect("The system must encrypt all backups at rest."),
            (
                "### REQUIREMENT\n"
                "DECISION_REQUIRED(retention_days): retention period not yet specified.\n\n"
                "### CHANGELOG\n"
                "- changed\n\n"
                "### ASSUMPTIONS\n"
                "- a1\n\n"
                "### OPEN_QUESTIONS\n"
                "- none\n"
            ),
            (
                "### REQUIREMENT\n"
                "DECISION_REQUIRED(retention_days): retention period not yet specified.\n\n"
                "### CHANGELOG\n"
                "- changed\n\n"
                "### ASSUMPTIONS\n"
                "- a1\n\n"
                "### OPEN_QUESTIONS\n"
                "- none\n"
            ),
            (
                "### REQUIREMENT\n"
                "DECISION_REQUIRED(retention_days): retention period not yet specified.\n\n"
                "### CHANGELOG\n"
                "- changed\n\n"
                "### ASSUMPTIONS\n"
                "- a1\n\n"
                "### OPEN_QUESTIONS\n"
                "- none\n"
            ),
        ]
    )
    auditor_client = _FakeClient([_auditor(), _auditor(), _auditor(), _auditor()])

    await run_live_refinement(
        task="Refine retention requirements.",
        architect_client=architect_client,
        auditor_client=auditor_client,
        max_rounds=4,
    )

    third_round_prompt = architect_client.messages[2][1]["content"]
    assert "Current requirement draft:\nThe system must encrypt all backups at rest." in third_round_prompt
    assert "Current requirement draft:\nDECISION_REQUIRED(retention_days): retention period not yet specified." not in third_round_prompt


@pytest.mark.asyncio
async def test_run_live_refinement_sets_code_leak_failure_mode() -> None:
    architect_client = _FakeClient([_architect("The system must encrypt all backups at rest.")])
    auditor_client = _FakeClient(["```python\nprint('x')\n```"])

    result = await run_live_refinement(
        task="Refine backup requirements.",
        architect_client=architect_client,
        auditor_client=auditor_client,
        max_rounds=1,
    )

    assert result["stop_reason"] == "CODE_LEAK"
    assert result["odr_valid"] is False
    assert result["odr_failure_mode"] == "code_leak"
    assert result["odr_pending_decisions"] == 0


@pytest.mark.asyncio
async def test_run_live_refinement_sets_format_violation_failure_mode() -> None:
    architect_client = _FakeClient(["### REQUIREMENT\nbroken\n"])
    auditor_client = _FakeClient([_auditor()])

    result = await run_live_refinement(
        task="Refine backup requirements.",
        architect_client=architect_client,
        auditor_client=auditor_client,
        max_rounds=1,
    )

    assert result["stop_reason"] == "FORMAT_VIOLATION"
    assert result["odr_valid"] is False
    assert result["odr_failure_mode"] == "format_violation"


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
    assert state.stop_reason == "FORMAT_VIOLATION"
    record = state.history_rounds[-1]
    assert record["auditor_parsed"] is None
    assert any(
        err["source"] == "auditor"
        and err["code"] in {"HEADER_OUT_OF_ORDER", "MISSING_HEADER"}
        and "out of order" in str(err["message"]).lower()
        for err in record["parse_errors"]
    )


def test_run_round_does_not_mutate_input_state() -> None:
    cfg = ReactorConfig()
    state_before = ReactorState()

    state_after = run_round(state_before, _architect("snapshot"), _auditor(), cfg)

    assert state_after is not state_before
    assert state_before.history_v == []
    assert state_before.history_rounds == []
    assert state_before.stable_count == 0
    assert state_before.stop_reason is None
    assert state_after.history_v == ["snapshot"]


def test_check_code_leak_matches_authoritative_detector() -> None:
    pseudo_code = "{\n    value = compute(x);\n    next = call(y);\n}\n"
    patterns = ReactorConfig().code_leak_patterns

    delegated = check_code_leak(pseudo_code, patterns)
    authoritative = detect_code_leak(
        architect_raw=pseudo_code,
        auditor_raw="",
        mode=DEFAULT_LEAK_GATE_MODE,
        patterns=patterns,
    ).hard_leak

    assert delegated is authoritative


def test_invalid_terminal_round_uses_max_rounds_not_invalid_convergence() -> None:
    cfg = ReactorConfig(max_rounds=2)
    state = ReactorState()
    invalid_architect = (
        "### REQUIREMENT\n"
        "DECISION_REQUIRED(retention_days): retention period not yet specified.\n\n"
        "### CHANGELOG\n"
        "- changed\n\n"
        "### ASSUMPTIONS\n"
        "- a1\n\n"
        "### OPEN_QUESTIONS\n"
        "- none\n"
    )

    state = run_round(state, invalid_architect, _auditor(), cfg)
    assert state.stop_reason is None
    state = run_round(state, invalid_architect, _auditor(), cfg)

    assert state.stop_reason == "MAX_ROUNDS"


def test_reactor_config_accepts_deprecated_max_rounds_alias() -> None:
    cfg = ReactorConfig(max_rounds=3)

    assert cfg.max_attempts == 3
    assert cfg.as_dict()["max_rounds"] == 3
