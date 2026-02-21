from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field, model_validator


VisibilityMode = Literal["off", "read_only", "buffered_write", "live_read_write"]


class TraceToolCall(BaseModel):
    tool_name: str = Field(min_length=1)
    tool_profile_version: str = Field(min_length=1)
    normalized_args: Dict[str, Any] = Field(default_factory=dict)
    normalization_version: str = Field(min_length=1)
    tool_result_fingerprint: str = Field(min_length=1)
    side_effect_fingerprint: str | None = None


class TraceEvent(BaseModel):
    event_id: str = Field(min_length=1)
    index: int = Field(ge=0)
    role: str = Field(min_length=1)
    interceptor: str = Field(min_length=1)
    decision_type: str = Field(min_length=1)
    tool_calls: List[TraceToolCall] = Field(default_factory=list)
    guardrails_triggered: List[str] = Field(default_factory=list)
    retrieval_event_ids: List[str] = Field(default_factory=list)


class OutputDescriptor(BaseModel):
    output_type: str = Field(min_length=1)
    output_shape_hash: str = Field(min_length=1)
    normalization_version: str = Field(min_length=1)


class DeterminismTraceContract(BaseModel):
    run_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    memory_snapshot_id: str = Field(min_length=1)
    visibility_mode: VisibilityMode
    model_config_id: str = Field(min_length=1)
    policy_set_id: str = Field(min_length=1)
    determinism_trace_schema_version: str = Field(min_length=1)
    events: List[TraceEvent] = Field(default_factory=list)
    output: OutputDescriptor

    @model_validator(mode="after")
    def _validate_event_indexes(self) -> "DeterminismTraceContract":
        indexes = [event.index for event in self.events]
        if indexes != list(range(len(self.events))):
            raise ValueError("events must be contiguous and ordered by index starting at 0")
        return self

    def enforce_non_live_visibility(self) -> None:
        if self.visibility_mode == "live_read_write":
            raise ValueError("deterministic runs may not use live_read_write visibility mode")


class RetrievalSelectedRecord(BaseModel):
    record_id: str = Field(min_length=1)
    record_type: str = Field(min_length=1)
    score: float
    rank: int = Field(ge=1)


class RetrievalTraceEventContract(BaseModel):
    retrieval_event_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    query_normalization_version: str = Field(min_length=1)
    query_fingerprint: str = Field(min_length=1)
    retrieval_mode: str = Field(min_length=1)
    candidate_count: int = Field(ge=0)
    selected_records: List[RetrievalSelectedRecord] = Field(default_factory=list)
    applied_filters: Dict[str, Any] = Field(default_factory=dict)
    retrieval_trace_schema_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_rank_order(self) -> "RetrievalTraceEventContract":
        ranks = [row.rank for row in self.selected_records]
        if ranks and ranks != list(range(1, len(self.selected_records) + 1)):
            raise ValueError("selected_records ranks must be contiguous and ordered starting at 1")
        return self
