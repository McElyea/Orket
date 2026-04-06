from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifacts import write_artifact_bundle
from .deterministic import analyze_plan, digest_plan_bytes, parse_plan_json
from .models import (
    AuditPublisher,
    DeterministicAnalysisArtifact,
    ExecutionStatus,
    FinalReviewArtifact,
    FinalVerdictSource,
    GovernanceArtifact,
    InputArtifact,
    ModelSummarizer,
    ObservedPathClassification,
    ObservedResultClassification,
    ModelSummaryArtifact,
    PlanObjectReader,
    PolicyBlockedError,
    PublishDecision,
    SummaryStatus,
    TerraformPlanReviewRequest,
    TerraformPlanReviewResult,
)


class TerraformPlanReviewService:
    def __init__(
        self,
        *,
        workspace: Path,
        s3_reader: PlanObjectReader,
        model_summarizer: ModelSummarizer,
        audit_publisher: AuditPublisher,
        audit_table_name: str = "TerraformReviews",
    ) -> None:
        self.workspace = workspace
        self.s3_reader = s3_reader
        self.model_summarizer = model_summarizer
        self.audit_publisher = audit_publisher
        self.audit_table_name = audit_table_name

    async def run(self, request: TerraformPlanReviewRequest) -> TerraformPlanReviewResult:
        input_artifact = InputArtifact(
            plan_s3_uri=request.plan_s3_uri,
            plan_hash="",
            size_bytes=0,
            content_type="application/json",
            parse_mode="terraform_json_plan",
        )
        deterministic = DeterministicAnalysisArtifact(
            analysis_complete=False,
            resource_changes=[],
            action_counts={"create": 0, "update": 0, "destroy": 0, "replace": 0, "no-op": 0},
            forbidden_operation_hits=[],
            warnings=[],
            analysis_confidence="incomplete",
        )
        model_summary = ModelSummaryArtifact(
            model_id=request.model_id,
            summary="",
            review_focus_areas=[],
            summary_status="summary_not_attempted",
        )
        final_review = FinalReviewArtifact(
            plan_hash="",
            plan_s3_uri=request.plan_s3_uri,
            risk_verdict="",
            forbidden_operation_hits=[],
            resource_change_summary={"total_changes": 0, "action_counts": dict(deterministic.action_counts)},
            model_id=request.model_id,
            summary="",
            summary_status="summary_not_attempted",
            policy_bundle_id=request.policy_bundle_id,
            execution_trace_ref=self._trace_ref(request),
            created_at=request.created_at,
            stored_in_dynamodb=False,
        )
        governance = self._governance(
            request=request,
            execution_status="failure",
            publish_decision="no_publish",
            summary_status="summary_not_attempted",
            final_verdict_source="none",
            deterministic_analysis_complete=False,
        )
        raw_bytes = b""

        try:
            governance.adapter_calls_attempted.append("read_s3_object")
            raw_bytes = await self.s3_reader.read_object(request.plan_s3_uri)
            input_artifact.plan_hash = digest_plan_bytes(raw_bytes)
            input_artifact.size_bytes = len(raw_bytes)
            final_review.plan_hash = input_artifact.plan_hash
            plan_payload, parse_error = parse_plan_json(raw_bytes)
            if plan_payload is None:
                deterministic.warnings = [parse_error]
                input_artifact.fetch_error = ""
                governance = self._finalize_governance(
                    governance=governance,
                    execution_status="failure",
                    publish_decision="no_publish",
                    summary_status="summary_not_attempted",
                    final_verdict_source="none",
                    deterministic_analysis_complete=False,
                )
                return await self._finish(
                    input_artifact=input_artifact,
                    deterministic=deterministic,
                    model_summary=model_summary,
                    final_review=final_review,
                    governance=governance,
                )

            deterministic = analyze_plan(plan_payload=plan_payload, forbidden_operations=request.forbidden_operations)
            final_review.resource_change_summary = {
                "total_changes": len(deterministic.resource_changes),
                "action_counts": dict(deterministic.action_counts),
            }
            governance.deterministic_analysis_complete = deterministic.analysis_complete
            if not deterministic.analysis_complete:
                governance = self._finalize_governance(
                    governance=governance,
                    execution_status="failure",
                    publish_decision="no_publish",
                    summary_status="summary_not_attempted",
                    final_verdict_source="none",
                    deterministic_analysis_complete=False,
                )
                return await self._finish(
                    input_artifact=input_artifact,
                    deterministic=deterministic,
                    model_summary=model_summary,
                    final_review=final_review,
                    governance=governance,
                )

            risk_verdict = (
                "risky_for_v1_policy" if deterministic.forbidden_operation_hits else "safe_for_v1_policy"
            )
            final_review.risk_verdict = risk_verdict
            final_review.forbidden_operation_hits = list(deterministic.forbidden_operation_hits)

            self._enforce_prohibited_capability(request, governance)

            try:
                governance.adapter_calls_attempted.append("invoke_bedrock_model")
                raw_summary = await self.model_summarizer.summarize(
                    {
                        "plan_hash": input_artifact.plan_hash,
                        "risk_verdict": risk_verdict,
                        "forbidden_operation_hits": [item.to_dict() for item in deterministic.forbidden_operation_hits],
                        "action_counts": dict(deterministic.action_counts),
                        "resource_changes": [item.to_dict() for item in deterministic.resource_changes],
                        "request_metadata": dict(request.request_metadata),
                    }
                )
                model_summary = self._model_summary_from_payload(
                    request=request,
                    raw_payload=raw_summary,
                    deterministic_verdict=risk_verdict,
                )
                final_review.summary = model_summary.summary
                final_review.summary_status = model_summary.summary_status
                governance = self._finalize_governance(
                    governance=governance,
                    execution_status="success",
                    publish_decision="normal_publish",
                    summary_status=model_summary.summary_status,
                    final_verdict_source="deterministic_analysis",
                    deterministic_analysis_complete=True,
                )
            except (RuntimeError, ValueError, TypeError, OSError) as exc:
                model_summary = ModelSummaryArtifact(
                    model_id=request.model_id,
                    summary="",
                    review_focus_areas=[],
                    summary_status="summary_unavailable",
                    advisory_errors=[f"model_provider_error:{exc}"],
                )
                final_review.summary = ""
                final_review.summary_status = "summary_unavailable"
                governance = self._finalize_governance(
                    governance=governance,
                    execution_status="degraded",
                    publish_decision="degraded_publish",
                    summary_status="summary_unavailable",
                    final_verdict_source="deterministic_analysis",
                    deterministic_analysis_complete=True,
                )

            governance.durable_mutations_attempted.append("dynamodb:TerraformReviews")
            governance.adapter_calls_attempted.append("put_dynamodb_item")
            await self.audit_publisher.put_item(self.audit_table_name, final_review.to_dict())
            final_review.stored_in_dynamodb = True
            return await self._finish(
                input_artifact=input_artifact,
                deterministic=deterministic,
                model_summary=model_summary,
                final_review=final_review,
                governance=governance,
            )

        except PolicyBlockedError as exc:
            governance.policy_violation_type = exc.violation_type
            governance.blocked_capability = exc.capability
            governance.adapter_calls_blocked.append(f"capability:{exc.capability}")
            if exc.capability in {"local_file_mutation", "aws_infrastructure_mutation", "prohibited_mutation"}:
                governance.durable_mutations_attempted.append(exc.capability)
            governance = self._finalize_governance(
                governance=governance,
                execution_status="blocked_by_policy",
                publish_decision="no_publish",
                summary_status="summary_not_attempted",
                final_verdict_source="deterministic_analysis" if deterministic.analysis_complete else "none",
                deterministic_analysis_complete=deterministic.analysis_complete,
            )
            final_review.risk_verdict = (
                "risky_for_v1_policy" if deterministic.forbidden_operation_hits else final_review.risk_verdict
            )
            final_review.forbidden_operation_hits = list(deterministic.forbidden_operation_hits)
            final_review.resource_change_summary = {
                "total_changes": len(deterministic.resource_changes),
                "action_counts": dict(deterministic.action_counts),
            }
            return await self._finish(
                input_artifact=input_artifact,
                deterministic=deterministic,
                model_summary=model_summary,
                final_review=final_review,
                governance=governance,
            )
        except (FileNotFoundError, PermissionError, RuntimeError, ValueError, TypeError, OSError) as exc:
            input_artifact.fetch_error = str(exc)
            governance = self._finalize_governance(
                governance=governance,
                execution_status="failure",
                publish_decision="no_publish",
                summary_status="summary_not_attempted",
                final_verdict_source="none",
                deterministic_analysis_complete=False,
            )
            return await self._finish(
                input_artifact=input_artifact,
                deterministic=deterministic,
                model_summary=model_summary,
                final_review=final_review,
                governance=governance,
            )

    def _trace_ref(self, request: TerraformPlanReviewRequest) -> str:
        return request.execution_trace_ref.strip() or "terraform-plan-review"

    def _governance(
        self,
        *,
        request: TerraformPlanReviewRequest,
        execution_status: ExecutionStatus,
        publish_decision: PublishDecision,
        summary_status: SummaryStatus,
        final_verdict_source: FinalVerdictSource,
        deterministic_analysis_complete: bool,
    ) -> GovernanceArtifact:
        path_classification, result_classification = self._classification_map(
            publish_decision=publish_decision,
            execution_status=execution_status,
        )
        return GovernanceArtifact(
            execution_status=execution_status,
            publish_decision=publish_decision,
            policy_violation_type="",
            blocked_capability="",
            durable_mutations_attempted=[],
            durable_mutations_allowed=["dynamodb:TerraformReviews"],
            adapter_calls_attempted=[],
            adapter_calls_blocked=[],
            deterministic_analysis_complete=deterministic_analysis_complete,
            summary_status=summary_status,
            final_verdict_source=final_verdict_source,
            policy_bundle_id=request.policy_bundle_id,
            execution_trace_ref=self._trace_ref(request),
            observed_path_classification=path_classification,
            observed_result_classification=result_classification,
        )

    def _finalize_governance(
        self,
        *,
        governance: GovernanceArtifact,
        execution_status: ExecutionStatus,
        publish_decision: PublishDecision,
        summary_status: SummaryStatus,
        final_verdict_source: FinalVerdictSource,
        deterministic_analysis_complete: bool,
    ) -> GovernanceArtifact:
        governance.execution_status = execution_status
        governance.publish_decision = publish_decision
        governance.summary_status = summary_status
        governance.final_verdict_source = final_verdict_source
        governance.deterministic_analysis_complete = deterministic_analysis_complete
        path_classification, result_classification = self._classification_map(
            publish_decision=publish_decision,
            execution_status=execution_status,
        )
        governance.observed_path_classification = path_classification
        governance.observed_result_classification = result_classification
        return governance

    def _classification_map(
        self,
        *,
        publish_decision: PublishDecision,
        execution_status: ExecutionStatus,
    ) -> tuple[ObservedPathClassification, ObservedResultClassification]:
        if publish_decision == "normal_publish":
            return "primary", "success"
        if publish_decision == "degraded_publish":
            return "degraded", "partial success"
        if execution_status == "environment_blocker":
            return "blocked", "environment blocker"
        return "blocked", "failure"

    def _enforce_prohibited_capability(
        self,
        request: TerraformPlanReviewRequest,
        governance: GovernanceArtifact,
    ) -> None:
        capability = request.prohibited_capability_attempt.strip()
        if not capability:
            return
        raise PolicyBlockedError(capability=capability)

    def _model_summary_from_payload(
        self,
        *,
        request: TerraformPlanReviewRequest,
        raw_payload: dict[str, Any],
        deterministic_verdict: str,
    ) -> ModelSummaryArtifact:
        summary = str(raw_payload.get("summary") or "").strip()
        focus = [str(item).strip() for item in list(raw_payload.get("review_focus_areas") or []) if str(item).strip()]
        advisory_errors: list[str] = []
        suggested_verdict = str(raw_payload.get("suggested_verdict") or "").strip()
        if suggested_verdict and suggested_verdict != deterministic_verdict:
            advisory_errors.append("model_verdict_conflict")
        return ModelSummaryArtifact(
            model_id=request.model_id,
            summary=summary,
            review_focus_areas=focus,
            summary_status="summary_available",
            advisory_errors=advisory_errors,
            raw_completion_ref=str(raw_payload.get("raw_completion_ref") or ""),
        )

    async def _finish(
        self,
        *,
        input_artifact: InputArtifact,
        deterministic: DeterministicAnalysisArtifact,
        model_summary: ModelSummaryArtifact,
        final_review: FinalReviewArtifact,
        governance: GovernanceArtifact,
    ) -> TerraformPlanReviewResult:
        artifact_bundle = await write_artifact_bundle(
            workspace=self.workspace,
            execution_trace_ref=governance.execution_trace_ref,
            payloads={
                "input_artifact": input_artifact.to_dict(),
                "deterministic_analysis": deterministic.to_dict(),
                "model_summary": model_summary.to_dict(),
                "final_review": final_review.to_dict(),
                "governance_artifact": governance.to_dict(),
            },
        )
        return TerraformPlanReviewResult(
            ok=governance.publish_decision != "no_publish" or governance.execution_status == "blocked_by_policy",
            artifact_bundle=artifact_bundle,
            input_artifact=input_artifact,
            deterministic_analysis=deterministic,
            model_summary=model_summary,
            final_review=final_review,
            governance_artifact=governance,
        )
