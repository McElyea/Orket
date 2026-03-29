from __future__ import annotations

from typing import Any

from orket.application.review.control_plane_projection import (
    REVIEW_EXECUTION_STATE_AUTHORITY,
    validate_review_execution_authority_markers,
    validate_review_required_identifier,
)
from scripts.reviewrun.score_answer_key import score_answer_key
from scripts.reviewrun.score_answer_key_contract import validate_answer_key_score_report
from scripts.workloads.code_review_probe_support import sha256_text


def build_model_assisted_payload(
    *,
    review_payload: dict[str, Any],
    run_id: str,
    model: str,
    source_text: str,
    prompt_profile: str,
    review_method: str,
    policy_digest: str,
) -> dict[str, Any]:
    normalized_run_id = validate_review_required_identifier(
        run_id,
        error="code_review_probe_model_assisted_run_id_required",
    )
    validate_review_execution_authority_markers(
        execution_state_authority=REVIEW_EXECUTION_STATE_AUTHORITY,
        execution_state_authoritative=False,
        field_name="code_review_probe_model_assisted",
    )
    return {
        **review_payload,
        "model_id": str(model),
        "prompt_profile": str(prompt_profile),
        "review_method": str(review_method),
        "contract_version": "review_critique_v0",
        "snapshot_digest": sha256_text(source_text),
        "policy_digest": str(policy_digest),
        "run_id": normalized_run_id,
        "execution_state_authority": REVIEW_EXECUTION_STATE_AUTHORITY,
        "lane_output_execution_state_authoritative": False,
    }


def quality_summary(score: dict[str, Any], *, contract_valid: bool) -> dict[str, Any]:
    model = score.get("model_assisted") if isinstance(score.get("model_assisted"), dict) else {}
    deterministic = score.get("deterministic") if isinstance(score.get("deterministic"), dict) else {}
    missed = [str(item) for item in list(score.get("model_missed_must_catch") or []) if str(item).strip()]
    coverage = float(model.get("coverage") or 0.0)
    if not contract_valid:
        verdict = "contract_invalid"
    elif missed:
        verdict = "missed_must_catch"
    elif coverage > 0.0:
        verdict = "all_must_catch_caught"
    else:
        verdict = "no_useful_hits"
    return {
        "quality_verdict": verdict,
        "model_coverage": coverage,
        "model_score": int(model.get("score") or 0),
        "model_max_score": int(model.get("max_score") or 0),
        "model_reasoning_score": int(model.get("reasoning_score") or 0),
        "model_reasoning_max_score": int(model.get("reasoning_max_score") or 0),
        "model_fix_score": int(model.get("fix_score") or 0),
        "model_fix_max_score": int(model.get("fix_max_score") or 0),
        "model_missed_must_catch": missed,
        "model_hit_issue_ids": [str(item) for item in list(score.get("model_hit_issue_ids") or []) if str(item).strip()],
        "deterministic_coverage": float(deterministic.get("coverage") or 0.0),
        "deterministic_score": int(deterministic.get("score") or 0),
        "deterministic_max_score": int(deterministic.get("max_score") or 0),
        "deterministic_missed_must_catch": [
            str(item) for item in list(score.get("deterministic_missed_must_catch") or []) if str(item).strip()
        ],
        "deterministic_hit_issue_ids": [
            str(item) for item in list(score.get("deterministic_hit_issue_ids") or []) if str(item).strip()
        ],
    }


def score_review_bundle(*, artifact_dir: Any, answer_key_path: Any) -> dict[str, Any]:
    score = validate_answer_key_score_report(
        score_answer_key(run_dir=artifact_dir, answer_key_path=answer_key_path)
    )
    score["model_missed_must_catch"] = [
        str(row.get("issue_id") or "")
        for row in list(score.get("issues") or [])
        if bool(row.get("present")) and bool(row.get("must_catch")) and not bool(row.get("model_hit"))
    ]
    score["model_hit_issue_ids"] = [
        str(row.get("issue_id") or "")
        for row in list(score.get("issues") or [])
        if bool(row.get("present")) and bool(row.get("model_hit"))
    ]
    score["deterministic_missed_must_catch"] = [
        str(row.get("issue_id") or "")
        for row in list(score.get("issues") or [])
        if bool(row.get("present")) and bool(row.get("must_catch")) and not bool(row.get("deterministic_hit"))
    ]
    score["deterministic_hit_issue_ids"] = [
        str(row.get("issue_id") or "")
        for row in list(score.get("issues") or [])
        if bool(row.get("present")) and bool(row.get("deterministic_hit"))
    ]
    return score
