"""Deterministic compliance disposition over captured model-selection values."""
from __future__ import annotations

from dataclasses import replace

from orket.core.contracts.model_selection import ModelCompliancePolicy, ModelSelectionDecision


def apply_model_compliance(
    role: str, selected_model: str, policy: ModelCompliancePolicy, *, explicit_override: bool = False,
) -> ModelSelectionDecision:
    decision = ModelSelectionDecision(role, selected_model, selected_model, False, "policy_missing",
                                      score_source=policy.observation)
    if explicit_override:
        return replace(decision, reason="override")
    if not policy.present:
        return decision
    if not policy.enabled:
        return replace(decision, reason="policy_disabled")
    if selected_model in policy.blocked_models:
        return replace(decision, final_model=policy.fallback_model, demoted=True, reason="blocked_model")
    if policy.min_score is None:
        return replace(decision, reason="min_score_missing")
    score = dict(policy.scores).get(selected_model)
    if score is None:
        return replace(decision, reason="score_missing")
    decision = replace(decision, score=score, min_score=policy.min_score)
    if score < policy.min_score:
        return replace(decision, final_model=policy.fallback_model, demoted=True, reason="score_below_threshold")
    return replace(decision, reason="score_ok")
