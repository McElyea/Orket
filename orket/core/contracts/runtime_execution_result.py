"""Typed observations of retained runtime truth, separate from transcript history."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from orket.core.contracts.control_plane_models import FinalTruthRecord, RunRecord
from orket.core.domain.control_plane_enums import (
    CompletionClassification,
    EvidenceSufficiencyClassification,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
)


class RuntimeExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["runtime_execution_result.v1"] = "runtime_execution_result.v1"
    session_id: str = Field(min_length=1)
    build_id: str | None = None
    observation: Literal["published", "approval_pending", "cancelled", "unresolved"]
    run: RunRecord | None = None
    final_truth: FinalTruthRecord | None = None
    publication_ref: str | None = None
    evidence_refs: tuple[str, ...] = ()
    reason: str | None = None
    transcript: tuple[dict[str, Any], ...] = ()

    @model_validator(mode="after")
    def _validate_observation(self) -> RuntimeExecutionResult:
        if self.final_truth is not None and (self.run is None or self.final_truth.run_id != self.run.run_id
                or self.final_truth.final_truth_record_id != self.run.final_truth_record_id):
            raise ValueError("E_RUNTIME_RESULT_TRUTH_IDENTITY_CONFLICT")
        if self.observation != "published":
            return self
        if self.run is None or not self.publication_ref:
            raise ValueError("E_RUNTIME_RESULT_PUBLICATION_EVIDENCE_REQUIRED")
        state = self.run.lifecycle_state
        if state in {RunState.COMPLETED, RunState.FAILED_TERMINAL}:
            expected = ResultClass.SUCCESS if state is RunState.COMPLETED else ResultClass.FAILED
            if self.final_truth is None or self.final_truth.result_class is not expected:
                raise ValueError("E_RUNTIME_RESULT_TERMINAL_TRUTH_CONFLICT")
        elif state is not RunState.WAITING_ON_OBSERVATION or self.final_truth is not None:
            raise ValueError("E_RUNTIME_RESULT_PUBLICATION_LIFECYCLE_CONFLICT")
        return self

    @property
    def run_id(self) -> str | None:
        return self.run.run_id if self.run else None

    @property
    def lifecycle_state(self) -> RunState | None:
        return self.run.lifecycle_state if self.run else None

    @property
    def result_class(self) -> ResultClass:
        return self.final_truth.result_class if self.observation == "published" and self.final_truth else ResultClass.BLOCKED

    @property
    def evidence_sufficiency(self) -> EvidenceSufficiencyClassification:
        if self.observation == "published" and self.final_truth:
            return self.final_truth.evidence_sufficiency_classification
        return EvidenceSufficiencyClassification.INSUFFICIENT

    @property
    def residual_uncertainty(self) -> ResidualUncertaintyClassification:
        if self.observation == "published" and self.final_truth:
            return self.final_truth.residual_uncertainty_classification
        return ResidualUncertaintyClassification.UNRESOLVED

    @property
    def succeeded(self) -> bool:
        return (self.observation == "published" and self.lifecycle_state is RunState.COMPLETED
                and self.result_class is ResultClass.SUCCESS and self.final_truth is not None
                and self.final_truth.completion_classification is CompletionClassification.SATISFIED
                and self.evidence_sufficiency is EvidenceSufficiencyClassification.SUFFICIENT
                and self.residual_uncertainty is ResidualUncertaintyClassification.NONE)


class RuntimeCollectionMember(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    target: str = Field(min_length=1)
    result: RuntimeExecutionResult


class RuntimeCollectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["runtime_collection_result.v1"] = "runtime_collection_result.v1"
    session_id: str = Field(min_length=1)
    build_id: str = Field(min_length=1)
    collection: str = Field(min_length=1)
    expected_members: tuple[str, ...]
    members: tuple[RuntimeCollectionMember, ...] = ()
    reason: str | None = None

    @property
    def succeeded(self) -> bool:
        return (bool(self.expected_members) and self.reason is None
                and tuple(member.target for member in self.members) == self.expected_members
                and all(member.result.succeeded for member in self.members))
