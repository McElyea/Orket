from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

SERVICE_MODE_BASELINE = "baseline_evaluate"
SERVICE_MODE_ADAPT = "bounded_adapt"
ALLOWED_SERVICE_MODES = (SERVICE_MODE_BASELINE, SERVICE_MODE_ADAPT)

RESULT_CLASS_CERTIFIED = "certified"
RESULT_CLASS_CERTIFIED_WITH_LIMITS = "certified_with_limits"
RESULT_CLASS_UNSUPPORTED = "unsupported"
ALLOWED_RESULT_CLASSES = (
    RESULT_CLASS_CERTIFIED,
    RESULT_CLASS_CERTIFIED_WITH_LIMITS,
    RESULT_CLASS_UNSUPPORTED,
)

ALLOWED_OBSERVED_PATHS = ("primary", "fallback", "degraded", "blocked")
ALLOWED_OBSERVED_RESULTS = ("success", "failure", "partial success", "environment blocker")
ALLOWED_VERDICT_SOURCES = ("service_adopted", "harness_derived")


def _coerce_float(value: Any, *, field_name: str) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        token = value.strip()
        if token:
            try:
                return float(token)
            except ValueError:
                pass
    raise ValueError(f"{field_name} must be numeric")


def _coerce_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        token = value.strip()
        if token:
            try:
                return int(token)
            except ValueError:
                pass
    raise ValueError(f"{field_name} must be an integer")


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _require_non_empty(value: str, *, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def _optional_non_empty(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _sanitize_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    token = token.strip("-")
    return token or "service-run"


@dataclass(frozen=True)
class AcceptanceThresholds:
    certified_min_score: float
    certified_with_limits_min_score: float

    def __post_init__(self) -> None:
        certified = float(self.certified_min_score)
        with_limits = float(self.certified_with_limits_min_score)
        if certified < 0.0 or certified > 1.0:
            raise ValueError("certified_min_score must be within [0.0, 1.0]")
        if with_limits < 0.0 or with_limits > 1.0:
            raise ValueError("certified_with_limits_min_score must be within [0.0, 1.0]")
        if with_limits > certified:
            raise ValueError("certified_with_limits_min_score must not exceed certified_min_score")

    def to_payload(self) -> dict[str, float]:
        return {
            "certified_min_score": float(self.certified_min_score),
            "certified_with_limits_min_score": float(self.certified_with_limits_min_score),
        }


@dataclass(frozen=True)
class RuntimeContext:
    provider: str
    model_id: str
    adapter: str
    runtime_version: str | None = None
    endpoint_id: str | None = None
    quantization: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.provider, field_name="runtime_context.provider")
        _require_non_empty(self.model_id, field_name="runtime_context.model_id")
        _require_non_empty(self.adapter, field_name="runtime_context.adapter")

    def to_payload(self) -> dict[str, str]:
        payload = {
            "provider": self.provider,
            "model_id": self.model_id,
            "adapter": self.adapter,
        }
        if self.runtime_version:
            payload["runtime_version"] = self.runtime_version
        if self.endpoint_id:
            payload["endpoint_id"] = self.endpoint_id
        if self.quantization:
            payload["quantization"] = self.quantization
        return payload


@dataclass(frozen=True)
class PromptReforgerServiceRequest:
    request_id: str
    service_mode: str
    bridge_contract_ref: str
    eval_slice_ref: str
    runtime_context: RuntimeContext
    acceptance_thresholds: AcceptanceThresholds
    consumer_id: str | None = None
    baseline_bundle_ref: str | None = None
    baseline_prompt_ref: str | None = None
    candidate_budget: int | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.request_id, field_name="request_id")
        if self.service_mode not in ALLOWED_SERVICE_MODES:
            raise ValueError(f"service_mode must be one of {ALLOWED_SERVICE_MODES}")
        _require_non_empty(self.bridge_contract_ref, field_name="bridge_contract_ref")
        _require_non_empty(self.eval_slice_ref, field_name="eval_slice_ref")
        if bool(self.baseline_bundle_ref) == bool(self.baseline_prompt_ref):
            raise ValueError("exactly one of baseline_bundle_ref or baseline_prompt_ref must be set")
        if self.service_mode == SERVICE_MODE_ADAPT:
            if self.candidate_budget is None:
                raise ValueError("candidate_budget is required for bounded_adapt")
            if int(self.candidate_budget) <= 0:
                raise ValueError("candidate_budget must be greater than zero")
        elif self.candidate_budget is not None and int(self.candidate_budget) < 0:
            raise ValueError("candidate_budget must be non-negative when provided")

    @property
    def artifact_token(self) -> str:
        return _sanitize_token(self.request_id)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "request_id": self.request_id,
            "service_mode": self.service_mode,
            "bridge_contract_ref": self.bridge_contract_ref,
            "eval_slice_ref": self.eval_slice_ref,
            "runtime_context": self.runtime_context.to_payload(),
            "acceptance_thresholds": self.acceptance_thresholds.to_payload(),
        }
        if self.consumer_id:
            payload["consumer_id"] = self.consumer_id
        if self.baseline_bundle_ref:
            payload["baseline_bundle_ref"] = self.baseline_bundle_ref
        if self.baseline_prompt_ref:
            payload["baseline_prompt_ref"] = self.baseline_prompt_ref
        if self.candidate_budget is not None:
            payload["candidate_budget"] = int(self.candidate_budget)
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> PromptReforgerServiceRequest:
        if not isinstance(payload, dict):
            raise ValueError("service request payload must be an object")
        runtime_payload = payload.get("runtime_context")
        threshold_payload = payload.get("acceptance_thresholds")
        if not isinstance(runtime_payload, dict):
            raise ValueError("runtime_context must be an object")
        if not isinstance(threshold_payload, dict):
            raise ValueError("acceptance_thresholds must be an object")
        return cls(
            request_id=_require_non_empty(str(payload.get("request_id") or ""), field_name="request_id"),
            service_mode=_require_non_empty(str(payload.get("service_mode") or ""), field_name="service_mode"),
            consumer_id=_optional_non_empty(payload.get("consumer_id")),
            bridge_contract_ref=_require_non_empty(
                str(payload.get("bridge_contract_ref") or ""),
                field_name="bridge_contract_ref",
            ),
            eval_slice_ref=_require_non_empty(str(payload.get("eval_slice_ref") or ""), field_name="eval_slice_ref"),
            runtime_context=RuntimeContext(
                provider=str(runtime_payload.get("provider") or ""),
                model_id=str(runtime_payload.get("model_id") or ""),
                adapter=str(runtime_payload.get("adapter") or ""),
                runtime_version=_optional_non_empty(runtime_payload.get("runtime_version")),
                endpoint_id=_optional_non_empty(runtime_payload.get("endpoint_id")),
                quantization=_optional_non_empty(runtime_payload.get("quantization")),
            ),
            baseline_bundle_ref=_optional_non_empty(payload.get("baseline_bundle_ref")),
            baseline_prompt_ref=_optional_non_empty(payload.get("baseline_prompt_ref")),
            acceptance_thresholds=AcceptanceThresholds(
                certified_min_score=_coerce_float(
                    threshold_payload.get("certified_min_score"),
                    field_name="acceptance_thresholds.certified_min_score",
                ),
                certified_with_limits_min_score=_coerce_float(
                    threshold_payload.get("certified_with_limits_min_score"),
                    field_name="acceptance_thresholds.certified_with_limits_min_score",
                ),
            ),
            candidate_budget=(
                None
                if payload.get("candidate_budget") is None
                else _coerce_int(payload.get("candidate_budget"), field_name="candidate_budget")
            ),
        )


@dataclass(frozen=True)
class CandidateSummary:
    evaluated_candidate_count: int
    winning_candidate_id: str | None = None
    winning_score: float | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"evaluated_candidate_count": int(self.evaluated_candidate_count)}
        if self.winning_candidate_id:
            payload["winning_candidate_id"] = self.winning_candidate_id
        if self.winning_score is not None:
            payload["winning_score"] = round(float(self.winning_score), 6)
        return payload


@dataclass(frozen=True)
class BaselineMetrics:
    score: float
    hard_fail_count: int
    soft_fail_count: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "score": round(float(self.score), 6),
            "hard_fail_count": int(self.hard_fail_count),
            "soft_fail_count": int(self.soft_fail_count),
        }


@dataclass(frozen=True)
class PromptReforgerServiceResult:
    request_id: str
    service_run_id: str
    result_class: str
    observed_path: str
    observed_result: str
    runtime_context: RuntimeContext
    bridge_contract_ref: str
    eval_slice_ref: str
    baseline_metrics: BaselineMetrics
    candidate_summary: CandidateSummary
    acceptance_reason: str
    bundle_ref: str | None
    known_limits: tuple[str, ...]
    requalification_triggers: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty(self.request_id, field_name="request_id")
        _require_non_empty(self.service_run_id, field_name="service_run_id")
        if self.result_class not in ALLOWED_RESULT_CLASSES:
            raise ValueError(f"result_class must be one of {ALLOWED_RESULT_CLASSES}")
        if self.observed_path not in ALLOWED_OBSERVED_PATHS:
            raise ValueError(f"observed_path must be one of {ALLOWED_OBSERVED_PATHS}")
        if self.observed_result not in ALLOWED_OBSERVED_RESULTS:
            raise ValueError(f"observed_result must be one of {ALLOWED_OBSERVED_RESULTS}")
        _require_non_empty(self.acceptance_reason, field_name="acceptance_reason")
        if self.result_class == RESULT_CLASS_UNSUPPORTED and self.bundle_ref:
            raise ValueError("unsupported results must not carry bundle_ref")

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "request_id": self.request_id,
            "service_run_id": self.service_run_id,
            "result_class": self.result_class,
            "observed_path": self.observed_path,
            "observed_result": self.observed_result,
            "runtime_context": self.runtime_context.to_payload(),
            "bridge_contract_ref": self.bridge_contract_ref,
            "eval_slice_ref": self.eval_slice_ref,
            "baseline_metrics": self.baseline_metrics.to_payload(),
            "candidate_summary": self.candidate_summary.to_payload(),
            "acceptance_reason": self.acceptance_reason,
            "known_limits": list(self.known_limits),
            "requalification_triggers": list(self.requalification_triggers),
        }
        if self.bundle_ref:
            payload["bundle_ref"] = self.bundle_ref
        return payload


@dataclass(frozen=True)
class ExternalConsumerVerdict:
    consumer_id: str
    verdict_class: str
    verdict_source: str
    service_result_ref: str

    def __post_init__(self) -> None:
        _require_non_empty(self.consumer_id, field_name="consumer_id")
        if self.verdict_class not in ALLOWED_RESULT_CLASSES:
            raise ValueError(f"verdict_class must be one of {ALLOWED_RESULT_CLASSES}")
        if self.verdict_source not in ALLOWED_VERDICT_SOURCES:
            raise ValueError(f"verdict_source must be one of {ALLOWED_VERDICT_SOURCES}")
        _require_non_empty(self.service_result_ref, field_name="service_result_ref")

    def to_payload(self) -> dict[str, str]:
        return {
            "consumer_id": self.consumer_id,
            "verdict_class": self.verdict_class,
            "verdict_source": self.verdict_source,
            "service_result_ref": self.service_result_ref,
        }
