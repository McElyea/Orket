from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


WORKLOAD_CONTRACT_VERSION_V1 = "workload.contract.v1"
WorkloadType = Literal["odr", "cards"]
REQUIRED_WORKLOAD_KEYS = (
    "workload_contract_version",
    "workload_type",
    "units",
    "required_materials",
    "expected_artifacts",
    "validators",
    "summary_targets",
    "provenance_targets",
)


def missing_required_workload_keys(payload: dict[str, Any]) -> list[str]:
    return sorted(key for key in REQUIRED_WORKLOAD_KEYS if key not in payload)


class WorkloadContractV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workload_contract_version: str = Field(min_length=1)
    workload_type: WorkloadType
    units: list[dict[str, Any]] = Field(min_length=1)
    required_materials: list[dict[str, Any]] = Field(default_factory=list)
    expected_artifacts: list[str] = Field(default_factory=list)
    validators: list[str] = Field(default_factory=list)
    summary_targets: list[str] = Field(default_factory=list)
    provenance_targets: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_version_and_strings(self) -> "WorkloadContractV1":
        if self.workload_contract_version != WORKLOAD_CONTRACT_VERSION_V1:
            raise ValueError(
                f"unsupported workload_contract_version={self.workload_contract_version!r}; "
                f"expected {WORKLOAD_CONTRACT_VERSION_V1!r}"
            )
        for key in ("expected_artifacts", "validators", "summary_targets", "provenance_targets"):
            values = getattr(self, key)
            if any(not isinstance(item, str) or not item.strip() for item in values):
                raise ValueError(f"{key} entries must be non-empty strings")
        return self


def parse_workload_contract(payload: dict[str, Any]) -> WorkloadContractV1:
    missing = missing_required_workload_keys(payload)
    if missing:
        raise ValueError(f"missing required workload contract keys: {missing}")
    return WorkloadContractV1.model_validate(payload)
