from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, Field, ValidationError

from orket.application.review.models import ModelAssistedCritiquePayload, ModelRiskIssue, ReviewSnapshot


class _ModelRiskIssueModel(BaseModel):
    why: str
    where: str
    impact: str
    confidence: float
    suggested_fix: str


class _ModelCritiqueContract(BaseModel):
    summary: list[str] = Field(default_factory=list)
    high_risk_issues: list[_ModelRiskIssueModel] = Field(default_factory=list)
    missing_tests: list[str] = Field(default_factory=list)
    questions_for_author: list[str] = Field(default_factory=list)
    nits: list[str] = Field(default_factory=list)
    refs: list[str] = Field(default_factory=list)


ModelProvider = Callable[[Dict[str, Any]], Dict[str, Any]]


def run_model_assisted_lane(
    *,
    snapshot: ReviewSnapshot,
    resolved_policy: Dict[str, Any],
    run_id: str,
    policy_digest: str,
    provider: Optional[ModelProvider] = None,
) -> ModelAssistedCritiquePayload:
    config = dict(resolved_policy.get("model_assisted") or {})
    model_id = str(config.get("model_id") or "")
    prompt_profile = str(config.get("prompt_profile") or "review_critique_v0")
    contract_version = str(config.get("contract_version") or "review_critique_v0")
    max_input_bytes = int(config.get("max_input_bytes") or 100_000)

    advisory_errors: list[str] = []
    if provider is None:
        advisory_errors.append("model_provider_not_configured")
        return ModelAssistedCritiquePayload(
            summary=["Model-assisted lane enabled, but no provider is configured."],
            high_risk_issues=[],
            missing_tests=[],
            questions_for_author=[],
            nits=[],
            refs=[],
            model_id=model_id,
            prompt_profile=prompt_profile,
            contract_version=contract_version,
            snapshot_digest=snapshot.snapshot_digest,
            policy_digest=policy_digest,
            run_id=run_id,
            advisory_errors=advisory_errors,
        )

    bounded_input = snapshot.diff_unified.encode("utf-8")[:max_input_bytes].decode("utf-8", errors="ignore")
    request = {
        "prompt_profile": prompt_profile,
        "contract_version": contract_version,
        "snapshot_digest": snapshot.snapshot_digest,
        "policy_digest": policy_digest,
        "diff_unified": bounded_input,
        "changed_files": [item.to_dict() for item in snapshot.changed_files],
        "metadata": snapshot.metadata,
    }
    try:
        raw_payload = provider(request)
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        advisory_errors.append(f"model_provider_error:{exc}")
        return ModelAssistedCritiquePayload(
            summary=[],
            high_risk_issues=[],
            missing_tests=[],
            questions_for_author=[],
            nits=[],
            refs=[],
            model_id=model_id,
            prompt_profile=prompt_profile,
            contract_version=contract_version,
            snapshot_digest=snapshot.snapshot_digest,
            policy_digest=policy_digest,
            run_id=run_id,
            advisory_errors=advisory_errors,
        )

    try:
        validated = _ModelCritiqueContract.model_validate(raw_payload or {})
    except ValidationError as exc:
        advisory_errors.append(f"contract_validation_error:{exc}")
        validated = _ModelCritiqueContract()

    return ModelAssistedCritiquePayload(
        summary=list(validated.summary),
        high_risk_issues=[
            ModelRiskIssue(
                why=item.why,
                where=item.where,
                impact=item.impact,
                confidence=float(item.confidence),
                suggested_fix=item.suggested_fix,
            )
            for item in list(validated.high_risk_issues)
        ],
        missing_tests=list(validated.missing_tests),
        questions_for_author=list(validated.questions_for_author),
        nits=list(validated.nits),
        refs=list(validated.refs),
        model_id=model_id,
        prompt_profile=prompt_profile,
        contract_version=contract_version,
        snapshot_digest=snapshot.snapshot_digest,
        policy_digest=policy_digest,
        run_id=run_id,
        advisory_errors=advisory_errors,
    )

