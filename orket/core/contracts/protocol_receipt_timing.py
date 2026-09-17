"""Validator durations are reported inputs, never inferred measurements."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from orket.core.contracts.invocation_timing import optional_duration_ms


class ValidatorTimingProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["reported", "unavailable"]
    source: Literal["runtime_context"] | None
    reason: Literal["missing", "invalid"] | None


class ProtocolReceiptTiming(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["protocol_receipt.v2"] = "protocol_receipt.v2"
    validator_duration_ms: float | None = Field(strict=True, ge=0, allow_inf_nan=False)
    validator_timing: ValidatorTimingProvenance

    @model_validator(mode="after")
    def validate_provenance(self) -> ProtocolReceiptTiming:
        provenance = self.validator_timing
        if provenance.status == "reported":
            if self.validator_duration_ms is None or provenance.source is None or provenance.reason is not None:
                raise ValueError("E_VALIDATOR_TIMING_REPORTED_VALUE_REQUIRED")
        elif self.validator_duration_ms is not None or provenance.source is not None or provenance.reason is None:
            raise ValueError("E_VALIDATOR_TIMING_UNAVAILABLE_REASON_REQUIRED")
        return self


def protocol_receipt_timing(value: Any) -> ProtocolReceiptTiming:
    duration = optional_duration_ms(value)
    return ProtocolReceiptTiming(
        validator_duration_ms=duration,
        validator_timing=ValidatorTimingProvenance(
            status="reported" if duration is not None else "unavailable",
            source="runtime_context" if duration is not None else None,
            reason=None if duration is not None else ("missing" if value is None else "invalid"),
        ),
    )
