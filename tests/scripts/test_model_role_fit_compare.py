# LIFECYCLE: live
from pathlib import Path

import pytest

from scripts.odr.model_role_fit_compare import (
    build_closeout_payload,
    build_pair_compare_payload,
    build_pair_verdict_payload,
    build_triple_compare_payload,
    build_triple_verdict_payload,
)
from scripts.odr.model_role_fit_lane import load_lane_config, load_matrix_registry

REPO_ROOT = Path(__file__).resolve().parents[2]
LANE_CONFIG_PATH = (
    REPO_ROOT / "docs" / "projects" / "archive" / "ODRModelRoleFit" / "MRF03212026" / "odr_model_role_fit_lane_config.json"
)


def _pair_row(
    pair_id: str,
    scenario_id: str,
    locked_budget: int,
    *,
    converged: bool,
    stop_reason: str,
    contradictions: int = 0,
    reopened: int = 0,
    regressions: int = 0,
    carry_forward: float = 1.0,
    latency_ms: int = 100,
    context_bytes: int = 1000,
) -> dict[str, object]:
    return {
        "entity_id": pair_id,
        "scenario_id": scenario_id,
        "locked_budget": locked_budget,
        "converged": converged,
        "stop_reason": stop_reason,
        "rounds_consumed": locked_budget,
        "reopened_decision_count": reopened,
        "contradiction_count": contradictions,
        "regression_count": regressions,
        "carry_forward_integrity": carry_forward,
        "round_latency_ms": [latency_ms],
        "round_active_context_size_bytes": [context_bytes],
        "round_active_context_size_tokens": [256],
    }


def test_build_pair_compare_and_verdict_rank_and_disqualify_pairs() -> None:
    """Layer: contract. Verifies pair compare/verdict ranking follows the frozen convergence-first order and structural disqualification threshold."""
    config = load_lane_config(LANE_CONFIG_PATH)
    registry = load_matrix_registry(config)
    rows = [
        _pair_row("llama_3_3_70b_instruct__gemma3_27b", "missing_constraint_resolved", 5, converged=True, stop_reason="STABLE_DIFF_FLOOR", latency_ms=90),
        _pair_row("llama_3_3_70b_instruct__gemma3_27b", "overfitting", 5, converged=True, stop_reason="STABLE_DIFF_FLOOR", latency_ms=95),
        _pair_row("llama_3_3_70b_instruct__gemma3_27b", "missing_constraint_resolved", 9, converged=True, stop_reason="STABLE_DIFF_FLOOR", latency_ms=110),
        _pair_row("llama_3_3_70b_instruct__gemma3_27b", "overfitting", 9, converged=False, stop_reason="MAX_ROUNDS", contradictions=1, latency_ms=120),
        _pair_row("llama_3_3_70b_instruct__magistral_small_2509", "missing_constraint_resolved", 5, converged=False, stop_reason="MAX_ROUNDS", latency_ms=115),
        _pair_row("llama_3_3_70b_instruct__magistral_small_2509", "overfitting", 5, converged=True, stop_reason="STABLE_DIFF_FLOOR", contradictions=1, latency_ms=125),
        _pair_row("llama_3_3_70b_instruct__magistral_small_2509", "missing_constraint_resolved", 9, converged=False, stop_reason="MAX_ROUNDS", reopened=1, latency_ms=130),
        _pair_row("llama_3_3_70b_instruct__magistral_small_2509", "overfitting", 9, converged=False, stop_reason="MAX_ROUNDS", latency_ms=135),
        _pair_row("gemma3_27b__qwen3_5_27b", "missing_constraint_resolved", 5, converged=False, stop_reason="CODE_LEAK", latency_ms=80),
        _pair_row("gemma3_27b__qwen3_5_27b", "overfitting", 5, converged=False, stop_reason="CODE_LEAK", latency_ms=80),
        _pair_row("gemma3_27b__qwen3_5_27b", "missing_constraint_resolved", 9, converged=False, stop_reason="FORMAT_VIOLATION", latency_ms=85),
        _pair_row("gemma3_27b__qwen3_5_27b", "overfitting", 9, converged=False, stop_reason="MAX_ROUNDS", latency_ms=90),
    ]

    pair_compare = build_pair_compare_payload(config=config, registry=registry, raw_rows=rows)
    pair_verdict = build_pair_verdict_payload(
        config=config,
        registry=registry,
        pair_compare_payload=pair_compare,
    )

    assert pair_compare["continuity_mode"] == "v1_compiled_shared_state"
    assert pair_compare["scenario_set"]["scenario_ids"] == ["missing_constraint_resolved", "overfitting"]
    rankings = {row["entity_id"]: row for row in pair_compare["pair_rankings"]}
    assert rankings["llama_3_3_70b_instruct__gemma3_27b"]["rank"] == 1
    assert rankings["llama_3_3_70b_instruct__magistral_small_2509"]["rank"] == 2
    assert rankings["gemma3_27b__qwen3_5_27b"]["selection_status"] == "structurally_disqualified"
    assert rankings["gemma3_27b__qwen3_5_27b"]["structural_failure_rate"] == pytest.approx(0.75)
    assert pair_compare["top_pairs_for_triples"] == [
        "llama_3_3_70b_instruct__gemma3_27b",
        "llama_3_3_70b_instruct__magistral_small_2509",
    ]
    assert pair_verdict["best_observed_pair"] == "llama_3_3_70b_instruct__gemma3_27b"
    assert pair_verdict["triple_phase_status"] == "admitted"

    closeout = build_closeout_payload(
        config=config,
        registry=registry,
        pair_compare_payload=pair_compare,
        pair_verdict_payload=pair_verdict,
        triple_compare_payload=None,
        triple_verdict_payload=None,
        skipped_triples=[],
    )
    assert closeout["best_observed_pair"] == "llama_3_3_70b_instruct__gemma3_27b"
    assert closeout["best_architect_model"] == "llama-3.3-70b-instruct"
    assert closeout["best_reviewer_model"] is None
    assert closeout["evidence_scope"] == "serial_pair_matrix_only"


def test_build_triple_compare_and_closeout_preserve_skip_reasons() -> None:
    """Layer: contract. Verifies skipped triple reasons survive into verdict and closeout artifacts when the triple phase does not admit runnable variants."""
    config = load_lane_config(LANE_CONFIG_PATH)
    triple_compare = build_triple_compare_payload(config=config, raw_rows=[])
    triple_verdict = build_triple_verdict_payload(
        triple_compare_payload=triple_compare,
        admitted_triples=[],
    )
    triple_verdict["skipped_triples"] = [{"reason": "insufficient_surviving_pairs"}]

    assert triple_compare["scenario_runs"] == []
    assert triple_verdict["best_observed_triple"] is None
    assert triple_verdict["admitted_triples"] == []


def test_build_pair_compare_marks_execution_blocked_pairs_ineligible() -> None:
    """Layer: contract. Verifies runtime-blocked pairs are excluded from ranking and triple admission even when they are not structurally disqualified."""
    config = load_lane_config(LANE_CONFIG_PATH)
    registry = load_matrix_registry(config)
    rows = [
        {
            "entity_id": "magistral_small_2509__gemma3_27b",
            "scenario_id": "missing_constraint_resolved",
            "locked_budget": 5,
            "execution_status": "runtime_blocker",
            "converged": False,
            "stop_reason": "RUNTIME_BLOCKER",
            "rounds_consumed": 0,
            "reopened_decision_count": 0,
            "contradiction_count": 0,
            "regression_count": 0,
            "carry_forward_integrity": 0.0,
            "round_latency_ms": [0],
            "round_active_context_size_bytes": [0],
            "round_active_context_size_tokens": [],
        },
        {
            "entity_id": "magistral_small_2509__gemma3_27b",
            "scenario_id": "missing_constraint_resolved",
            "locked_budget": 5,
            "execution_status": "runtime_blocker",
            "converged": False,
            "stop_reason": "RUNTIME_BLOCKER",
            "rounds_consumed": 0,
            "reopened_decision_count": 0,
            "contradiction_count": 0,
            "regression_count": 0,
            "carry_forward_integrity": 0.0,
            "round_latency_ms": [0],
            "round_active_context_size_bytes": [0],
            "round_active_context_size_tokens": [],
        },
        _pair_row("gemma3_27b__magistral_small_2509", "missing_constraint_resolved", 5, converged=True, stop_reason="STABLE_DIFF_FLOOR"),
    ]

    payload = build_pair_compare_payload(config=config, registry=registry, raw_rows=rows)
    rankings = {row["entity_id"]: row for row in payload["pair_rankings"]}
    verdict = build_pair_verdict_payload(config=config, registry=registry, pair_compare_payload=payload)

    assert len(payload["scenario_runs"]) == 2
    assert rankings["magistral_small_2509__gemma3_27b"]["selection_status"] == "execution_blocked"
    assert rankings["magistral_small_2509__gemma3_27b"]["execution_blocker_rate"] == pytest.approx(1.0)
    assert verdict["best_observed_pair"] == "gemma3_27b__magistral_small_2509"
