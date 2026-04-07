from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _normalize_timeout_seconds(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("controller.child_timeout_invalid")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("controller.child_timeout_invalid") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError("controller.child_timeout_invalid")
    return int(math.ceil(parsed))


def _normalize_for_canonical_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _normalize_for_canonical_json(item_value)
            for key, item_value in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_for_canonical_json(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("controller.envelope_invalid")
        return value
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TypeError(f"Unsupported canonical payload type: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    normalized = _normalize_for_canonical_json(value)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_digest_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class ControllerPolicyCaps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_depth: int | None = Field(default=None, ge=0)
    max_fanout: int | None = Field(default=None, ge=1)
    child_timeout_seconds: int | None = None

    @field_validator("child_timeout_seconds", mode="before")
    @classmethod
    def _normalize_child_timeout(cls, value: Any) -> int | None:
        return _normalize_timeout_seconds(value)


class ControllerChildCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_workload: str = Field(min_length=1)
    contract_style: Literal["sdk_v0"] = "sdk_v0"
    payload: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timeout_seconds", mode="before")
    @classmethod
    def _normalize_timeout(cls, value: Any) -> int | None:
        return _normalize_timeout_seconds(value)


ControllerChildStatus = Literal["success", "failed", "not_attempted"]


class ControllerChildResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_workload: str = Field(min_length=1)
    status: ControllerChildStatus
    requested_timeout: int | None = None
    enforced_timeout: int | None = None
    requested_caps: ControllerPolicyCaps | None = None
    enforced_caps: ControllerPolicyCaps | None = None
    artifact_refs: list[dict[str, Any]] = Field(default_factory=list)
    normalized_error: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)


class ControllerRunEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    controller_contract_version: Literal["controller.workload.v1"] = "controller.workload.v1"
    controller_workload_id: str = Field(min_length=1)
    parent_depth: int = Field(default=0, ge=0)
    ancestry: list[str] = Field(default_factory=list)
    requested_caps: ControllerPolicyCaps | None = None
    children: list[ControllerChildCall] = Field(default_factory=list, min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def canonical_payload(self) -> dict[str, Any]:
        payload = self.model_dump(exclude_none=True)
        return cast(dict[str, Any], _normalize_for_canonical_json(payload))

    def canonical_json(self) -> str:
        return canonical_json(self.canonical_payload())


ControllerRunStatus = Literal["success", "failed", "blocked"]


class ControllerRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    controller_contract_version: Literal["controller.workload.v1"] = "controller.workload.v1"
    controller_workload_id: str = Field(min_length=1)
    status: ControllerRunStatus
    requested_caps: ControllerPolicyCaps | None = None
    enforced_caps: ControllerPolicyCaps | None = None
    child_results: list[ControllerChildResult] = Field(default_factory=list)
    error_code: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_result_error_invariants(self) -> ControllerRunSummary:
        if self.status == "success" and self.error_code is not None:
            raise ValueError("controller.run_result_invariant_invalid")
        if self.status == "success" and any(item.status == "failed" for item in self.child_results):
            raise ValueError("controller.run_result_invariant_invalid")
        if self.status in {"failed", "blocked"} and not self.error_code:
            raise ValueError("controller.run_result_invariant_invalid")
        if self.status == "blocked" and any(item.status == "success" for item in self.child_results):
            raise ValueError("controller.run_result_invariant_invalid")
        return self

    def canonical_payload(self) -> dict[str, Any]:
        payload = self.model_dump(exclude_none=True)
        return cast(dict[str, Any], _normalize_for_canonical_json(payload))

    def canonical_json(self) -> str:
        return canonical_json(self.canonical_payload())

    def summary_digest_sha256(self) -> str:
        return canonical_digest_sha256(self.canonical_payload())


__all__ = [
    "ControllerChildCall",
    "ControllerChildResult",
    "ControllerChildStatus",
    "ControllerPolicyCaps",
    "ControllerRunEnvelope",
    "ControllerRunStatus",
    "ControllerRunSummary",
    "canonical_digest_sha256",
    "canonical_json",
]
