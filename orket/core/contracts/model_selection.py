"""Value contracts for model recommendations and observed compliance inputs."""
from __future__ import annotations

from dataclasses import dataclass

from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL


@dataclass(frozen=True)
class ModelSelectionInput:
    role: str
    asset_model: str = ""
    environment_model: str = ""
    preferred_model: str = ""
    organization_model: str = ""
    organization_default: str = ""
    default_model: str = DEFAULT_LOCAL_MODEL


@dataclass(frozen=True)
class ModelScoreObservation:
    path: str = ""
    status: str = "not_requested"
    sha256: str = ""
    error: str = ""
    scores: tuple[tuple[str, float], ...] = ()

    def to_payload(self) -> dict[str, str]:
        return {"path": self.path, "status": self.status, "sha256": self.sha256, "error": self.error}


@dataclass(frozen=True)
class ModelCompliancePolicy:
    present: bool = False
    enabled: bool = True
    blocked_models: frozenset[str] = frozenset()
    fallback_model: str = DEFAULT_LOCAL_MODEL
    min_score: float | None = None
    scores: tuple[tuple[str, float], ...] = ()
    observation: ModelScoreObservation = ModelScoreObservation()


@dataclass(frozen=True)
class ModelSelectionSnapshot:
    environment: tuple[tuple[str, str], ...]
    preferences: tuple[tuple[str, str], ...]
    organization_models: tuple[tuple[str, str], ...]
    organization_default: str
    compliance: ModelCompliancePolicy


@dataclass(frozen=True)
class ModelSelectionDecision:
    role: str
    selected_model: str
    final_model: str
    demoted: bool
    reason: str
    score: float | None = None
    min_score: float | None = None
    score_source: ModelScoreObservation = ModelScoreObservation()

    def to_payload(self) -> dict[str, object]:
        result: dict[str, object] = {
            "role": self.role, "selected_model": self.selected_model, "final_model": self.final_model,
            "demoted": self.demoted, "reason": self.reason,
        }
        if self.score is not None:
            result.update(score=self.score, min_score=self.min_score)
        if self.score_source.path:
            result["score_source"] = self.score_source.to_payload()
        return result


def preference_role(role: str) -> str:
    normalized = str(role or "").strip().lower().replace("-", "_")
    return {"backend_specialist": "coder", "senior_developer": "coder", "lead_architect": "architect",
            "integrity_guard": "reviewer"}.get(normalized, normalized)


def model_dialect(model: str) -> str:
    lowered = model.lower()
    for token, dialect in (("qwen", "qwen"), ("llama", "llama3"), ("deepseek", "deepseek-r1"), ("phi", "phi")):
        if token in lowered:
            return dialect
    return "generic"
