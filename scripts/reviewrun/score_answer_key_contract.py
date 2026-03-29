from __future__ import annotations

from typing import Any

from orket.application.review.control_plane_projection import validate_review_required_identifier


REPORT_CONTRACT_VERSION = "reviewrun_answer_key_score_v1"


def _require_non_negative_int(value: Any, *, error: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(error)
    return value


def _require_positive_int(value: Any, *, error: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(error)
    return value


def _require_non_empty_string(value: Any, *, error: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(error)
    return text


def _require_sha256_digest(value: Any, *, error: str) -> str:
    digest = _require_non_empty_string(value, error=error)
    if not digest.startswith("sha256:") or len(digest) <= len("sha256:"):
        raise ValueError(error)
    return digest


def _require_ratio(value: Any, *, error: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(error)
    ratio = float(value)
    if ratio < 0.0 or ratio > 1.0:
        raise ValueError(error)
    return ratio


def _require_string_list(value: Any, *, error: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(error)
    items: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if not text:
            raise ValueError(error)
        items.append(text)
    return items


def _validate_deterministic_block(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("reviewrun_answer_key_score_deterministic_invalid")
    _require_non_negative_int(
        payload.get("score"),
        error="reviewrun_answer_key_score_deterministic_score_invalid",
    )
    _require_non_negative_int(
        payload.get("max_score"),
        error="reviewrun_answer_key_score_deterministic_max_score_invalid",
    )
    _require_ratio(
        payload.get("coverage"),
        error="reviewrun_answer_key_score_deterministic_coverage_invalid",
    )
    _require_non_negative_int(
        payload.get("present_issue_count"),
        error="reviewrun_answer_key_score_deterministic_present_issue_count_invalid",
    )
    _require_string_list(
        payload.get("missed_must_catch"),
        error="reviewrun_answer_key_score_deterministic_missed_must_catch_invalid",
    )
    _require_string_list(
        payload.get("unexpected_hits"),
        error="reviewrun_answer_key_score_deterministic_unexpected_hits_invalid",
    )
    return dict(payload)


def _validate_model_assisted_block(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("reviewrun_answer_key_score_model_assisted_invalid")
    if not isinstance(payload.get("enabled"), bool):
        raise ValueError("reviewrun_answer_key_score_model_assisted_enabled_invalid")
    _require_non_negative_int(
        payload.get("score"),
        error="reviewrun_answer_key_score_model_assisted_score_invalid",
    )
    _require_non_negative_int(
        payload.get("max_score"),
        error="reviewrun_answer_key_score_model_assisted_max_score_invalid",
    )
    _require_ratio(
        payload.get("coverage"),
        error="reviewrun_answer_key_score_model_assisted_coverage_invalid",
    )
    _require_non_negative_int(
        payload.get("reasoning_score"),
        error="reviewrun_answer_key_score_model_assisted_reasoning_score_invalid",
    )
    _require_non_negative_int(
        payload.get("reasoning_max_score"),
        error="reviewrun_answer_key_score_model_assisted_reasoning_max_score_invalid",
    )
    _require_non_negative_int(
        payload.get("fix_score"),
        error="reviewrun_answer_key_score_model_assisted_fix_score_invalid",
    )
    _require_non_negative_int(
        payload.get("fix_max_score"),
        error="reviewrun_answer_key_score_model_assisted_fix_max_score_invalid",
    )
    _require_positive_int(
        payload.get("reasoning_weight"),
        error="reviewrun_answer_key_score_model_assisted_reasoning_weight_invalid",
    )
    _require_positive_int(
        payload.get("fix_weight"),
        error="reviewrun_answer_key_score_model_assisted_fix_weight_invalid",
    )
    return dict(payload)


def _validate_issue_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("reviewrun_answer_key_score_issues_invalid")
    rows: list[dict[str, Any]] = []
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError("reviewrun_answer_key_score_issue_row_invalid")
        if not str(row.get("issue_id") or "").strip():
            raise ValueError("reviewrun_answer_key_score_issue_id_invalid")
        if not isinstance(row.get("severity"), str):
            raise ValueError("reviewrun_answer_key_score_issue_severity_invalid")
        if not isinstance(row.get("must_catch"), bool):
            raise ValueError("reviewrun_answer_key_score_issue_must_catch_invalid")
        if not isinstance(row.get("present"), bool):
            raise ValueError("reviewrun_answer_key_score_issue_present_invalid")
        if not isinstance(row.get("deterministic_hit"), bool):
            raise ValueError("reviewrun_answer_key_score_issue_deterministic_hit_invalid")
        if not isinstance(row.get("model_hit"), bool):
            raise ValueError("reviewrun_answer_key_score_issue_model_hit_invalid")
        _require_non_negative_int(
            row.get("reasoning_hits"),
            error="reviewrun_answer_key_score_issue_reasoning_hits_invalid",
        )
        _require_non_negative_int(
            row.get("fix_hits"),
            error="reviewrun_answer_key_score_issue_fix_hits_invalid",
        )
        _require_non_negative_int(
            row.get("weight"),
            error="reviewrun_answer_key_score_issue_weight_invalid",
        )
        rows.append(dict(row))
    return rows


def _expected_coverage(score: int, max_score: int) -> float:
    if max_score == 0:
        return 0.0
    return round(score / float(max_score), 6)


def _require_exact_coverage(value: Any, *, expected: float, error: str) -> None:
    actual = _require_ratio(value, error=error)
    if abs(actual - expected) > 1e-9:
        raise ValueError(error)


def _validate_aggregate_consistency(
    *,
    deterministic: dict[str, Any],
    model_assisted: dict[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    present_rows = [row for row in issues if bool(row["present"])]
    deterministic_max = sum(int(row["weight"]) for row in present_rows)
    deterministic_score = sum(
        int(row["weight"]) for row in present_rows if bool(row["deterministic_hit"])
    )
    deterministic_missed = [
        str(row["issue_id"])
        for row in present_rows
        if bool(row["must_catch"]) and not bool(row["deterministic_hit"])
    ]
    deterministic_unexpected = [
        str(row["issue_id"])
        for row in issues
        if not bool(row["present"]) and bool(row["deterministic_hit"])
    ]

    if int(deterministic.get("present_issue_count") or 0) != len(present_rows):
        raise ValueError("reviewrun_answer_key_score_deterministic_present_issue_count_mismatch")
    if int(deterministic.get("score") or 0) != deterministic_score:
        raise ValueError("reviewrun_answer_key_score_deterministic_score_mismatch")
    if int(deterministic.get("max_score") or 0) != deterministic_max:
        raise ValueError("reviewrun_answer_key_score_deterministic_max_score_mismatch")
    _require_exact_coverage(
        deterministic.get("coverage"),
        expected=_expected_coverage(deterministic_score, deterministic_max),
        error="reviewrun_answer_key_score_deterministic_coverage_mismatch",
    )
    if list(deterministic.get("missed_must_catch") or []) != deterministic_missed:
        raise ValueError("reviewrun_answer_key_score_deterministic_missed_must_catch_mismatch")
    if list(deterministic.get("unexpected_hits") or []) != deterministic_unexpected:
        raise ValueError("reviewrun_answer_key_score_deterministic_unexpected_hits_mismatch")

    model_enabled = bool(model_assisted.get("enabled"))
    model_score = int(model_assisted.get("score") or 0)
    model_max = int(model_assisted.get("max_score") or 0)
    reasoning_weight = int(model_assisted.get("reasoning_weight") or 0)
    fix_weight = int(model_assisted.get("fix_weight") or 0)
    expected_model_score = sum(
        int(row["weight"]) for row in present_rows if bool(row["model_hit"])
    )
    expected_model_max = sum(int(row["weight"]) for row in present_rows)
    expected_reasoning_score = sum(
        reasoning_weight for row in present_rows if int(row["reasoning_hits"]) > 0
    )
    expected_reasoning_max = reasoning_weight * len(present_rows)
    expected_fix_score = sum(
        fix_weight for row in present_rows if int(row["fix_hits"]) > 0
    )
    expected_fix_max = fix_weight * len(present_rows)
    issue_model_activity = any(
        bool(row["model_hit"])
        or int(row["reasoning_hits"]) > 0
        or int(row["fix_hits"]) > 0
        for row in issues
    )

    if not model_enabled:
        if model_score != 0:
            raise ValueError("reviewrun_answer_key_score_model_assisted_score_mismatch")
        if model_max != 0:
            raise ValueError("reviewrun_answer_key_score_model_assisted_max_score_mismatch")
        _require_exact_coverage(
            model_assisted.get("coverage"),
            expected=0.0,
            error="reviewrun_answer_key_score_model_assisted_coverage_mismatch",
        )
        if int(model_assisted.get("reasoning_score") or 0) != 0:
            raise ValueError("reviewrun_answer_key_score_model_assisted_reasoning_score_disabled_invalid")
        if int(model_assisted.get("reasoning_max_score") or 0) != 0:
            raise ValueError("reviewrun_answer_key_score_model_assisted_reasoning_max_score_disabled_invalid")
        if int(model_assisted.get("fix_score") or 0) != 0:
            raise ValueError("reviewrun_answer_key_score_model_assisted_fix_score_disabled_invalid")
        if int(model_assisted.get("fix_max_score") or 0) != 0:
            raise ValueError("reviewrun_answer_key_score_model_assisted_fix_max_score_disabled_invalid")
        if issue_model_activity:
            raise ValueError("reviewrun_answer_key_score_model_assisted_disabled_issue_activity_invalid")
        return

    if model_score != expected_model_score:
        raise ValueError("reviewrun_answer_key_score_model_assisted_score_mismatch")
    if model_max != expected_model_max:
        raise ValueError("reviewrun_answer_key_score_model_assisted_max_score_mismatch")
    _require_exact_coverage(
        model_assisted.get("coverage"),
        expected=_expected_coverage(expected_model_score, expected_model_max),
        error="reviewrun_answer_key_score_model_assisted_coverage_mismatch",
    )
    if int(model_assisted.get("reasoning_score") or 0) != expected_reasoning_score:
        raise ValueError("reviewrun_answer_key_score_model_assisted_reasoning_score_mismatch")
    if int(model_assisted.get("reasoning_max_score") or 0) != expected_reasoning_max:
        raise ValueError("reviewrun_answer_key_score_model_assisted_reasoning_max_score_mismatch")
    if int(model_assisted.get("fix_score") or 0) != expected_fix_score:
        raise ValueError("reviewrun_answer_key_score_model_assisted_fix_score_mismatch")
    if int(model_assisted.get("fix_max_score") or 0) != expected_fix_max:
        raise ValueError("reviewrun_answer_key_score_model_assisted_fix_max_score_mismatch")


def validate_answer_key_score_report(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("reviewrun_answer_key_score_report_invalid")
    if str(payload.get("contract_version") or "").strip() != REPORT_CONTRACT_VERSION:
        raise ValueError("reviewrun_answer_key_score_contract_version_invalid")
    _require_non_empty_string(
        payload.get("fixture_id"),
        error="reviewrun_answer_key_score_fixture_id_required",
    )
    validate_review_required_identifier(
        payload.get("run_id"),
        error="reviewrun_answer_key_score_run_id_required",
    )
    _require_sha256_digest(
        payload.get("snapshot_digest"),
        error="reviewrun_answer_key_score_snapshot_digest_invalid",
    )
    _require_sha256_digest(
        payload.get("policy_digest"),
        error="reviewrun_answer_key_score_policy_digest_invalid",
    )
    deterministic = _validate_deterministic_block(payload.get("deterministic"))
    model_assisted = _validate_model_assisted_block(payload.get("model_assisted"))
    issues = _validate_issue_rows(payload.get("issues"))
    _validate_aggregate_consistency(
        deterministic=deterministic,
        model_assisted=model_assisted,
        issues=issues,
    )
    return dict(payload)
