# LIFECYCLE: live
from __future__ import annotations

from scripts.companion.companion_matrix_scoring import (
    build_recommendation_matrix,
    measured,
    not_measured,
    parse_model_size_b,
    rig_fit_score,
    score_footprint,
    weighted_profile_score,
)


def _base_scores() -> dict[str, dict[str, object]]:
    return {
        "reasoning": measured(0.9),
        "conversational_quality": measured(0.8),
        "memory_usefulness": measured(0.7),
        "latency": measured(0.75),
        "footprint": measured(0.8),
        "voice_suitability": measured(0.6),
        "stability": measured(0.95),
        "mode_adherence": measured(0.85),
    }


def test_parse_model_size_b_extracts_billion_suffix() -> None:
    """Layer: unit. Verifies model-size parser extracts known billion-size suffixes."""
    assert parse_model_size_b("qwen2.5-coder:7b") == 7.0
    assert parse_model_size_b("model-40B") == 40.0


def test_parse_model_size_b_returns_none_when_unavailable() -> None:
    """Layer: unit. Verifies model-size parser reports unknown size when suffix is absent."""
    assert parse_model_size_b("mystery-model") is None
    assert parse_model_size_b("") is None


def test_score_footprint_marks_unknown_models_not_measured() -> None:
    """Layer: unit. Verifies footprint scoring emits not-measured status when model size cannot be parsed."""
    payload = score_footprint("mystery-model")
    assert payload["status"] == "not_measured"
    assert payload["value"] is None


def test_weighted_profile_score_reduces_score_on_missing_dimension_coverage() -> None:
    """Layer: unit. Verifies profile scoring penalizes missing measured dimensions via coverage reduction."""
    scores = _base_scores()
    full = weighted_profile_score(scores=scores, usage_profile="chat-first")
    scores["reasoning"] = not_measured(detail="missing")
    reduced = weighted_profile_score(scores=scores, usage_profile="chat-first")
    assert full["coverage"] == 1.0
    assert reduced["coverage"] < 1.0
    assert reduced["score"] < full["score"]


def test_rig_fit_score_prefers_small_models_for_class_a() -> None:
    """Layer: unit. Verifies rig-fit scoring gives Class A higher fit for smaller models."""
    small = rig_fit_score(rig_class="A", model="qwen2.5-coder:7b")
    large = rig_fit_score(rig_class="A", model="qwen2.5-coder:40b")
    assert small["score"] > large["score"]


def test_rig_fit_score_prefers_large_models_for_class_d() -> None:
    """Layer: unit. Verifies rig-fit scoring gives Class D higher fit for larger models."""
    small = rig_fit_score(rig_class="D", model="qwen2.5-coder:7b")
    large = rig_fit_score(rig_class="D", model="qwen2.5-coder:40b")
    assert large["score"] > small["score"]


def test_build_recommendation_matrix_blocks_when_no_successful_cases() -> None:
    """Layer: unit. Verifies recommendation matrix returns blocked rows when all cases fail."""
    matrix = build_recommendation_matrix(
        cases=[
            {
                "provider": "ollama",
                "model": "qwen2.5-coder:7b",
                "result": "failure",
                "observed_path": "blocked",
                "scores": _base_scores(),
            }
        ],
        rig_classes=["A", "B"],
        usage_profiles=["chat-first"],
    )
    assert matrix["by_rig_class"]["A"]["chat-first"]["status"] == "blocked"
    assert matrix["by_rig_class"]["B"]["chat-first"]["status"] == "blocked"


def test_build_recommendation_matrix_selects_rig_specific_winner() -> None:
    """Layer: unit. Verifies recommendation matrix picks different winners by rig fit when quality is similar."""
    small_case = {
        "provider": "ollama",
        "model": "qwen2.5-coder:7b",
        "result": "success",
        "observed_path": "primary",
        "scores": _base_scores(),
    }
    large_case = {
        "provider": "lmstudio",
        "model": "qwen2.5-coder:40b",
        "result": "success",
        "observed_path": "primary",
        "scores": _base_scores(),
    }
    matrix = build_recommendation_matrix(
        cases=[small_case, large_case],
        rig_classes=["A", "D"],
        usage_profiles=["chat-first"],
    )
    assert matrix["by_rig_class"]["A"]["chat-first"]["model"] == "qwen2.5-coder:7b"
    assert matrix["by_rig_class"]["D"]["chat-first"]["model"] == "qwen2.5-coder:40b"
