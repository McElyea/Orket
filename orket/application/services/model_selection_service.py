"""Application capture and owned preparation for immutable model selection."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from functools import partial
from math import isfinite
from types import MappingProxyType
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.model_score_reader import read_model_scores
from orket.core.contracts.model_selection import (
    ModelCompliancePolicy,
    ModelScoreObservation,
    ModelSelectionDecision,
    ModelSelectionInput,
    ModelSelectionSnapshot,
    preference_role,
)
from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL
from orket.core.policies.model_selection import apply_model_compliance
from orket.decision_nodes.builtins import DefaultPromptStrategyNode
from orket.settings import load_user_preferences, load_user_settings

LOGGER = logging.getLogger(__name__)


def _number(value: object) -> float | None:
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def _model_pairs(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, Mapping):
        return ()
    return tuple(sorted((str(key), str(item).strip()) for key, item in value.items()))


def _compliance(settings: dict[str, Any], rules: dict[str, Any]) -> tuple[ModelCompliancePolicy, str]:
    policy = {}
    for source in (settings, rules):
        value = source.get("model_compliance_policy")
        if isinstance(value, dict):
            policy.update(value)
    values = policy.get("model_scores")
    scores = {str(k): number for k, v in values.items() if (number := _number(v)) is not None} if isinstance(values, dict) else {}
    captured = ModelCompliancePolicy(
        present=bool(policy), enabled=policy.get("enabled") is not False,
        blocked_models=frozenset(str(v).strip() for v in (policy.get("blocked_models") or ()) if str(v).strip()),
        fallback_model=str(policy.get("fallback_model") or "").strip() or DEFAULT_LOCAL_MODEL,
        min_score=_number(policy.get("min_score")), scores=tuple(sorted(scores.items())),
    )
    report = str(policy.get("score_source") or "").strip() if captured.enabled and captured.min_score is not None else ""
    return captured, report


@dataclass(frozen=True)
class PreparedModelSelection:
    inputs: ModelSelectionSnapshot
    strategy: Any

    def select(self, role: str, *, asset_model: str = "", override: str | None = None) -> ModelSelectionDecision:
        explicit = str(override or "").strip()
        if explicit:
            return apply_model_compliance(role, explicit, self.inputs.compliance, explicit_override=True)
        environment = dict(self.inputs.environment)
        role_key = str(role or "").strip().upper().replace("-", "_")
        from_environment = environment.get("ORKET_MODEL_" + role_key, "")
        if role == "operations_lead":
            from_environment = environment.get("ORKET_OPERATOR_MODEL", "") or from_environment
        normalized = preference_role(role)
        request = ModelSelectionInput(role, str(asset_model or "").strip(), from_environment,
            dict(self.inputs.preferences).get(normalized, ""), dict(self.inputs.organization_models).get(normalized, ""),
            self.inputs.organization_default)
        selected = self.strategy.select_model(request)
        if not isinstance(selected, str) or not selected.strip():
            raise ValueError("Prompt strategy must recommend a nonempty model name.")
        return apply_model_compliance(role, selected.strip(), self.inputs.compliance)

    def select_dialect(self, model: str) -> str:
        value = self.strategy.select_dialect(model)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Prompt strategy must recommend a nonempty dialect name.")
        return value.strip()


class ModelSelectionService:
    def __init__(self, *, environment: Mapping[str, str]) -> None:
        self.environment = MappingProxyType(dict(environment))

    async def prepare(
        self, organization: Any = None, preferences: dict[str, Any] | None = None,
        user_settings: dict[str, Any] | None = None, *, strategy: Any = None,
    ) -> PreparedModelSelection:
        # Borrowed nested dictionaries are captured before the first await.
        rules = deepcopy(getattr(organization, "process_rules", None) or {})
        captured_preferences = deepcopy(preferences) if preferences is not None else None
        captured_settings = deepcopy(user_settings) if user_settings is not None else None
        # The canonical sync readers preserve runtime settings context; owned workers
        # also keep their filesystem/bootstrap bridges off the event loop.
        if captured_preferences is None:
            captured_preferences = deepcopy(await run_owned_thread(load_user_preferences, label="model-selection-preferences"))
        if captured_settings is None:
            captured_settings = deepcopy(await run_owned_thread(load_user_settings, label="model-selection-settings"))
        policy, report_path = _compliance(captured_settings, rules)
        observation = ModelScoreObservation()
        if report_path:
            observation = await run_owned_thread(partial(read_model_scores, report_path), label="model-selection-scores")
            if observation.status != "observed":
                LOGGER.warning("Model selection score report %s: %s (%s)",
                               observation.status, observation.path, observation.error)
        scores = dict(policy.scores)
        scores.update(observation.scores)
        policy = replace(policy, scores=tuple(sorted(scores.items())), observation=observation)
        snapshot = ModelSelectionSnapshot(
            tuple(sorted((k, str(v).strip()) for k, v in self.environment.items()
                         if k.startswith("ORKET_MODEL_") or k == "ORKET_OPERATOR_MODEL")),
            _model_pairs(captured_preferences.get("models")), _model_pairs(rules.get("models")),
            str(rules.get("default_llm") or "").strip(), policy,
        )
        return PreparedModelSelection(snapshot, strategy if strategy is not None else DefaultPromptStrategyNode())


def prepare_bootstrap_model_selection(
    *, environment: Mapping[str, str], organization: Any = None,
) -> PreparedModelSelection:
    """Explicit synchronous bootstrap; an active event loop must use prepare()."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(ModelSelectionService(environment=environment).prepare(organization))
    raise RuntimeError("Model-selection bootstrap requires a synchronous boundary; await prepare() in an event loop.")
