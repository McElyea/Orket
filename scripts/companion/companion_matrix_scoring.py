from __future__ import annotations

import re
from typing import Any

DIMENSIONS: tuple[str, ...] = (
    "reasoning",
    "conversational_quality",
    "memory_usefulness",
    "latency",
    "footprint",
    "voice_suitability",
    "stability",
    "mode_adherence",
)

USAGE_PROFILES: tuple[str, ...] = ("chat-first", "memory-heavy", "voice-heavy")
RIG_CLASSES: tuple[str, ...] = ("A", "B", "C", "D")

PROFILE_DIMENSION_WEIGHTS: dict[str, dict[str, float]] = {
    "chat-first": {
        "reasoning": 0.26,
        "conversational_quality": 0.24,
        "latency": 0.20,
        "stability": 0.15,
        "mode_adherence": 0.15,
    },
    "memory-heavy": {
        "memory_usefulness": 0.34,
        "reasoning": 0.16,
        "conversational_quality": 0.10,
        "latency": 0.10,
        "stability": 0.15,
        "mode_adherence": 0.15,
    },
    "voice-heavy": {
        "voice_suitability": 0.36,
        "latency": 0.16,
        "stability": 0.20,
        "mode_adherence": 0.12,
        "conversational_quality": 0.16,
    },
}

_MODEL_SIZE_PATTERN = re.compile(r"(?P<size>\d+(?:\.\d+)?)\s*b", re.IGNORECASE)


def measured(value: float, *, detail: str = "") -> dict[str, Any]:
    bounded = max(0.0, min(1.0, float(value)))
    payload: dict[str, Any] = {"status": "measured", "value": round(bounded, 4)}
    if detail:
        payload["detail"] = str(detail)
    return payload


def not_measured(*, detail: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "not_measured", "value": None}
    if detail:
        payload["detail"] = str(detail)
    return payload


def parse_model_size_b(model: str) -> float | None:
    token = str(model or "").strip().lower()
    if not token:
        return None
    match = _MODEL_SIZE_PATTERN.search(token)
    if not match:
        return None
    try:
        return float(match.group("size"))
    except ValueError:
        return None


def score_latency(latency_ms: float) -> float:
    latency = max(0.0, float(latency_ms))
    if latency <= 700:
        return 1.0
    if latency <= 1200:
        return 0.9
    if latency <= 1800:
        return 0.75
    if latency <= 2600:
        return 0.6
    if latency <= 4000:
        return 0.4
    return 0.2


def score_reasoning(message: str) -> float:
    normalized = str(message or "").strip().lower()
    if not normalized:
        return 0.0
    if "323" in normalized:
        return 1.0
    if "three hundred" in normalized and "twenty" in normalized and "three" in normalized:
        return 0.9
    numeric_hits = re.findall(r"\d+", normalized)
    if numeric_hits:
        return 0.4
    return 0.1


def score_mode_adherence(message: str) -> float:
    normalized = str(message or "").strip()
    if not normalized:
        return 0.0
    lower = normalized.lower()
    has_token = "mode_ok" in lower
    starts_tutor = lower.startswith("tutor:")
    if has_token and starts_tutor:
        return 1.0
    if has_token or starts_tutor:
        return 0.6
    return 0.2


def score_conversational_quality(message: str) -> float:
    text = str(message or "").strip()
    if not text:
        return 0.0
    lower = text.lower()
    empathy_markers = ("understand", "sounds", "feel", "overwhelm", "step", "try")
    hits = sum(1 for marker in empathy_markers if marker in lower)
    sentence_count = max(1, text.count(".") + text.count("!") + text.count("?"))
    if hits >= 3 and sentence_count <= 4:
        return 1.0
    if hits >= 2:
        return 0.8
    if hits >= 1:
        return 0.6
    return 0.3


def score_memory_usefulness(message: str, *, expected_token: str) -> float:
    normalized = str(message or "").strip().lower()
    token = str(expected_token or "").strip().lower()
    if not normalized:
        return 0.0
    if token and token in normalized:
        return 1.0
    if "teal" in normalized or "favorite color" in normalized:
        return 0.6
    return 0.2


def score_voice_suitability(
    *,
    transitions_total: int,
    transitions_ok: int,
    stt_available: bool,
) -> float:
    total = max(1, int(transitions_total))
    ok_ratio = max(0.0, min(1.0, float(transitions_ok) / float(total)))
    stt_bonus = 0.1 if stt_available else -0.05
    return max(0.0, min(1.0, ok_ratio + stt_bonus))


def score_stability(*, successes: int, attempts: int) -> float:
    total = max(1, int(attempts))
    return max(0.0, min(1.0, float(max(0, successes)) / float(total)))


def score_footprint(model: str) -> dict[str, Any]:
    size_b = parse_model_size_b(model)
    if size_b is None:
        return not_measured(detail="model-size-unavailable")
    if size_b <= 7:
        return measured(1.0, detail=f"size_b={size_b}")
    if size_b <= 13:
        return measured(0.85, detail=f"size_b={size_b}")
    if size_b <= 24:
        return measured(0.65, detail=f"size_b={size_b}")
    if size_b <= 40:
        return measured(0.45, detail=f"size_b={size_b}")
    return measured(0.25, detail=f"size_b={size_b}")


def _score_value(score_payload: dict[str, Any] | None) -> float | None:
    if not isinstance(score_payload, dict):
        return None
    if str(score_payload.get("status") or "") != "measured":
        return None
    value = score_payload.get("value")
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return None
    return max(0.0, min(1.0, float(value)))


def weighted_profile_score(
    *,
    scores: dict[str, dict[str, Any]],
    usage_profile: str,
) -> dict[str, Any]:
    weights = PROFILE_DIMENSION_WEIGHTS.get(str(usage_profile or "").strip())
    if not weights:
        return {"usage_profile": usage_profile, "score": 0.0, "coverage": 0.0, "missing_dimensions": []}

    numerator = 0.0
    measured_weight = 0.0
    total_weight = 0.0
    missing: list[str] = []
    for dimension, weight in weights.items():
        total_weight += float(weight)
        value = _score_value(scores.get(dimension))
        if value is None:
            missing.append(dimension)
            continue
        numerator += value * float(weight)
        measured_weight += float(weight)

    coverage = measured_weight / total_weight if total_weight > 0.0 else 0.0
    raw = numerator / measured_weight if measured_weight > 0.0 else 0.0
    return {
        "usage_profile": usage_profile,
        "score": round(raw * coverage, 4),
        "coverage": round(coverage, 4),
        "missing_dimensions": missing,
    }


def rig_fit_score(*, rig_class: str, model: str) -> dict[str, Any]:
    normalized_class = str(rig_class or "").strip().upper()
    size_b = parse_model_size_b(model)
    if size_b is None:
        return {"rig_class": normalized_class, "score": 0.5, "detail": "model-size-unavailable"}

    if normalized_class == "A":
        if size_b <= 7:
            return {"rig_class": "A", "score": 1.0, "detail": f"size_b={size_b}"}
        if size_b <= 13:
            return {"rig_class": "A", "score": 0.7, "detail": f"size_b={size_b}"}
        if size_b <= 24:
            return {"rig_class": "A", "score": 0.35, "detail": f"size_b={size_b}"}
        return {"rig_class": "A", "score": 0.1, "detail": f"size_b={size_b}"}
    if normalized_class == "B":
        if size_b <= 7:
            return {"rig_class": "B", "score": 0.9, "detail": f"size_b={size_b}"}
        if size_b <= 13:
            return {"rig_class": "B", "score": 1.0, "detail": f"size_b={size_b}"}
        if size_b <= 24:
            return {"rig_class": "B", "score": 0.55, "detail": f"size_b={size_b}"}
        return {"rig_class": "B", "score": 0.2, "detail": f"size_b={size_b}"}
    if normalized_class == "C":
        if size_b <= 13:
            return {"rig_class": "C", "score": 0.8, "detail": f"size_b={size_b}"}
        if size_b <= 24:
            return {"rig_class": "C", "score": 1.0, "detail": f"size_b={size_b}"}
        if size_b <= 40:
            return {"rig_class": "C", "score": 0.7, "detail": f"size_b={size_b}"}
        return {"rig_class": "C", "score": 0.35, "detail": f"size_b={size_b}"}
    if size_b <= 24:
        return {"rig_class": "D", "score": 0.75, "detail": f"size_b={size_b}"}
    if size_b <= 40:
        return {"rig_class": "D", "score": 0.95, "detail": f"size_b={size_b}"}
    return {"rig_class": "D", "score": 1.0, "detail": f"size_b={size_b}"}


def _path_multiplier(observed_path: str) -> float:
    normalized = str(observed_path or "").strip().lower()
    if normalized == "primary":
        return 1.0
    if normalized == "degraded":
        return 0.9
    if normalized == "blocked":
        return 0.5
    return 0.8


def candidate_profile_score(
    *,
    case_payload: dict[str, Any],
    rig_class: str,
    usage_profile: str,
) -> dict[str, Any]:
    scores = dict(case_payload.get("scores") or {})
    profile = weighted_profile_score(scores=scores, usage_profile=usage_profile)
    rig = rig_fit_score(rig_class=rig_class, model=str(case_payload.get("model") or ""))
    combined = (float(profile["score"]) * 0.8 + float(rig["score"]) * 0.2) * _path_multiplier(str(case_payload.get("observed_path") or ""))
    return {
        "provider": str(case_payload.get("provider") or ""),
        "model": str(case_payload.get("model") or ""),
        "usage_profile": usage_profile,
        "rig_class": str(rig_class or "").upper(),
        "case_observed_path": str(case_payload.get("observed_path") or ""),
        "case_result": str(case_payload.get("result") or ""),
        "profile_score": float(profile["score"]),
        "profile_coverage": float(profile["coverage"]),
        "rig_fit_score": float(rig["score"]),
        "composite_score": round(combined, 4),
        "missing_dimensions": list(profile["missing_dimensions"]),
        "rig_fit_detail": str(rig.get("detail") or ""),
    }


def _choose_best(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    ordered = sorted(
        candidates,
        key=lambda row: (
            float(row.get("composite_score") or 0.0),
            float(row.get("profile_score") or 0.0),
            float(row.get("profile_coverage") or 0.0),
            str(row.get("provider") or ""),
            str(row.get("model") or ""),
        ),
        reverse=True,
    )
    return ordered[0]


def build_recommendation_matrix(
    *,
    cases: list[dict[str, Any]],
    rig_classes: list[str],
    usage_profiles: list[str],
) -> dict[str, Any]:
    successful_cases = [row for row in cases if str(row.get("result") or "") == "success"]
    normalized_rig_classes = [str(token or "").strip().upper() for token in rig_classes if str(token or "").strip()]
    normalized_usage_profiles = [str(token or "").strip() for token in usage_profiles if str(token or "").strip()]
    matrix: dict[str, dict[str, Any]] = {}
    candidate_rows: list[dict[str, Any]] = []

    for rig_class in normalized_rig_classes:
        profile_rows: dict[str, Any] = {}
        for usage_profile in normalized_usage_profiles:
            candidates = [
                candidate_profile_score(
                    case_payload=case_payload,
                    rig_class=rig_class,
                    usage_profile=usage_profile,
                )
                for case_payload in successful_cases
            ]
            candidate_rows.extend(candidates)
            best = _choose_best(candidates)
            profile_rows[usage_profile] = (
                {
                    "status": "recommended",
                    "provider": str(best.get("provider") or ""),
                    "model": str(best.get("model") or ""),
                    "composite_score": float(best.get("composite_score") or 0.0),
                    "profile_score": float(best.get("profile_score") or 0.0),
                    "profile_coverage": float(best.get("profile_coverage") or 0.0),
                    "rig_fit_score": float(best.get("rig_fit_score") or 0.0),
                    "missing_dimensions": list(best.get("missing_dimensions") or []),
                }
                if best is not None
                else {"status": "blocked", "reason": "no-successful-cases"}
            )
        matrix[rig_class] = profile_rows

    return {
        "usage_profiles": normalized_usage_profiles,
        "rig_classes": normalized_rig_classes,
        "by_rig_class": matrix,
        "candidate_scores": candidate_rows,
    }
