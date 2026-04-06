from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from orket.application.review.models import digest_sha256_prefixed, to_canonical_json_bytes

RiskVerdict = Literal["safe_for_v1_policy", "risky_for_v1_policy"]
PublishDecision = Literal["normal_publish", "degraded_publish", "no_publish"]
SummaryStatus = Literal["summary_available", "summary_unavailable", "summary_not_attempted"]
FinalVerdictSource = Literal["deterministic_analysis", "none"]
ExecutionStatus = Literal["success", "degraded", "blocked_by_policy", "failure", "environment_blocker"]
ObservedPathClassification = Literal["primary", "fallback", "degraded", "blocked"]
ObservedResultClassification = Literal["success", "failure", "partial success", "environment blocker"]


def canonical_digest(payload: dict[str, Any]) -> str:
    return digest_sha256_prefixed(to_canonical_json_bytes(payload))


class PlanObjectReader(Protocol):
    async def read_object(self, uri: str) -> bytes: ...


class ModelSummarizer(Protocol):
    async def summarize(self, request: dict[str, Any]) -> dict[str, Any]: ...


class AuditPublisher(Protocol):
    async def put_item(self, table_name: str, item: dict[str, Any]) -> None: ...


class PolicyBlockedError(RuntimeError):
    def __init__(self, *, capability: str, violation_type: str = "capability_blocked") -> None:
        super().__init__(f"policy_blocked:{capability}")
        self.capability = str(capability)
        self.violation_type = str(violation_type)


@dataclass(slots=True)
class TerraformPlanReviewRequest:
    plan_s3_uri: str
    forbidden_operations: list[str]
    request_metadata: dict[str, Any] = field(default_factory=dict)
    policy_bundle_id: str = "terraform_plan_reviewer_v1"
    execution_trace_ref: str = ""
    created_at: str = ""
    model_id: str = "bedrock.fake"
    prohibited_capability_attempt: str = ""


@dataclass(slots=True)
class ResourceChangeRecord:
    address: str
    provider_name: str
    resource_type: str
    action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "provider_name": self.provider_name,
            "resource_type": self.resource_type,
            "action": self.action,
        }


@dataclass(slots=True)
class ForbiddenOperationHit:
    operation: str
    address: str
    provider_name: str
    resource_type: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "address": self.address,
            "provider_name": self.provider_name,
            "resource_type": self.resource_type,
        }


@dataclass(slots=True)
class InputArtifact:
    plan_s3_uri: str
    plan_hash: str
    size_bytes: int
    content_type: str
    parse_mode: str
    fetch_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_s3_uri": self.plan_s3_uri,
            "plan_hash": self.plan_hash,
            "size_bytes": self.size_bytes,
            "content_type": self.content_type,
            "parse_mode": self.parse_mode,
            "fetch_error": self.fetch_error,
        }


@dataclass(slots=True)
class DeterministicAnalysisArtifact:
    analysis_complete: bool
    resource_changes: list[ResourceChangeRecord]
    action_counts: dict[str, int]
    forbidden_operation_hits: list[ForbiddenOperationHit]
    warnings: list[str]
    analysis_confidence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_complete": self.analysis_complete,
            "resource_changes": [item.to_dict() for item in self.resource_changes],
            "action_counts": dict(self.action_counts),
            "forbidden_operation_hits": [item.to_dict() for item in self.forbidden_operation_hits],
            "warnings": list(self.warnings),
            "analysis_confidence": self.analysis_confidence,
        }


@dataclass(slots=True)
class ModelSummaryArtifact:
    model_id: str
    summary: str
    review_focus_areas: list[str]
    summary_status: SummaryStatus
    advisory_errors: list[str] = field(default_factory=list)
    raw_completion_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "summary": self.summary,
            "review_focus_areas": list(self.review_focus_areas),
            "summary_status": self.summary_status,
            "advisory_errors": list(self.advisory_errors),
            "raw_completion_ref": self.raw_completion_ref,
        }


@dataclass(slots=True)
class FinalReviewArtifact:
    plan_hash: str
    plan_s3_uri: str
    risk_verdict: str
    forbidden_operation_hits: list[ForbiddenOperationHit]
    resource_change_summary: dict[str, Any]
    model_id: str
    summary: str
    summary_status: SummaryStatus
    policy_bundle_id: str
    execution_trace_ref: str
    created_at: str
    stored_in_dynamodb: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_hash": self.plan_hash,
            "plan_s3_uri": self.plan_s3_uri,
            "risk_verdict": self.risk_verdict,
            "forbidden_operation_hits": [item.to_dict() for item in self.forbidden_operation_hits],
            "resource_change_summary": dict(self.resource_change_summary),
            "model_id": self.model_id,
            "summary": self.summary,
            "summary_status": self.summary_status,
            "policy_bundle_id": self.policy_bundle_id,
            "execution_trace_ref": self.execution_trace_ref,
            "created_at": self.created_at,
            "stored_in_dynamodb": self.stored_in_dynamodb,
        }


@dataclass(slots=True)
class GovernanceArtifact:
    execution_status: ExecutionStatus
    publish_decision: PublishDecision
    policy_violation_type: str
    blocked_capability: str
    durable_mutations_attempted: list[str]
    durable_mutations_allowed: list[str]
    adapter_calls_attempted: list[str]
    adapter_calls_blocked: list[str]
    deterministic_analysis_complete: bool
    summary_status: SummaryStatus
    final_verdict_source: FinalVerdictSource
    policy_bundle_id: str
    execution_trace_ref: str
    observed_path_classification: ObservedPathClassification
    observed_result_classification: ObservedResultClassification

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_status": self.execution_status,
            "publish_decision": self.publish_decision,
            "policy_violation_type": self.policy_violation_type,
            "blocked_capability": self.blocked_capability,
            "durable_mutations_attempted": list(self.durable_mutations_attempted),
            "durable_mutations_allowed": list(self.durable_mutations_allowed),
            "adapter_calls_attempted": list(self.adapter_calls_attempted),
            "adapter_calls_blocked": list(self.adapter_calls_blocked),
            "deterministic_analysis_complete": self.deterministic_analysis_complete,
            "summary_status": self.summary_status,
            "final_verdict_source": self.final_verdict_source,
            "policy_bundle_id": self.policy_bundle_id,
            "execution_trace_ref": self.execution_trace_ref,
            "observed_path_classification": self.observed_path_classification,
            "observed_result_classification": self.observed_result_classification,
        }


@dataclass(slots=True)
class ArtifactBundle:
    artifact_dir: str
    artifact_paths: dict[str, str]
    artifact_hashes: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_dir": self.artifact_dir,
            "artifact_paths": dict(self.artifact_paths),
            "artifact_hashes": dict(self.artifact_hashes),
        }


@dataclass(slots=True)
class TerraformPlanReviewResult:
    ok: bool
    artifact_bundle: ArtifactBundle
    input_artifact: InputArtifact
    deterministic_analysis: DeterministicAnalysisArtifact
    model_summary: ModelSummaryArtifact
    final_review: FinalReviewArtifact
    governance_artifact: GovernanceArtifact

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "artifact_bundle": self.artifact_bundle.to_dict(),
            "input_artifact": self.input_artifact.to_dict(),
            "deterministic_analysis": self.deterministic_analysis.to_dict(),
            "model_summary": self.model_summary.to_dict(),
            "final_review": self.final_review.to_dict(),
            "governance_artifact": self.governance_artifact.to_dict(),
        }
