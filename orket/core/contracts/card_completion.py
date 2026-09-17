"""Typed inputs for card acceptance; these records are not authorization tokens."""
from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Reference = Annotated[str, Field(strict=True, min_length=1, pattern=r"^\S(?:.*\S)?$")]
Sha256 = Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")]


class CompletionRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AcceptanceEvidenceClass(StrEnum):
    NOT_EVALUATED = "not_evaluated"
    SYNTAX_ONLY = "syntax_only"
    COMMAND_EXECUTION = "command_execution"
    ARTIFACT_VERIFICATION = "artifact_verification"
    BEHAVIORAL_VERIFICATION = "behavioral_verification"


class AcceptanceObservation(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_EVALUATED = "not_evaluated"


class CompletionState(StrEnum):
    NOT_EVALUATED = "not_evaluated"
    INSUFFICIENT = "insufficient_evidence"
    FAILED = "acceptance_failed"
    SATISFIED = "acceptance_satisfied"


class CompletionScope(CompletionRecord):
    card_id: Reference
    run_id: Reference
    attempt_id: Reference
    workload_id: Reference
    input_digest: Sha256
    artifact_manifest_digest: Sha256


class AcceptanceRequirement(CompletionRecord):
    criterion_id: Reference
    description: Reference
    verifier_ref: Reference
    verifier_digest: Sha256
    evidence_class: AcceptanceEvidenceClass

    @model_validator(mode="after")
    def require_evaluation(self) -> Self:
        if self.evidence_class == AcceptanceEvidenceClass.NOT_EVALUATED:
            raise ValueError("An acceptance requirement must require an evaluated check.")
        return self


class CardAcceptancePlan(CompletionRecord):
    schema_version: Literal["card_acceptance_plan.v1"] = "card_acceptance_plan.v1"
    acceptance_ref: Reference
    policy_ref: Reference
    policy_digest: Sha256
    workload_id: Reference
    requirements: tuple[AcceptanceRequirement, ...] = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def unique_criteria(self) -> Self:
        ids = [row.criterion_id for row in self.requirements]
        if len(ids) != len(set(ids)):
            raise ValueError("Acceptance criterion identities must be unique.")
        return self

    @property
    def digest(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CardAcceptanceEvidence(CompletionRecord):
    schema_version: Literal["card_acceptance_evidence.v1"] = "card_acceptance_evidence.v1"
    evidence_ref: Reference
    evidence_digest: Sha256
    plan_digest: Sha256
    scope: CompletionScope
    criterion_id: Reference
    verifier_ref: Reference
    verifier_digest: Sha256
    evidence_class: AcceptanceEvidenceClass
    observation: AcceptanceObservation
    source: Literal["runtime_verifier", "model_self_report"]


class CompletionEvidenceSnapshot(CompletionRecord):
    """Application-validated snapshot; parsing a model response cannot establish it.

    The application must verify retained bodies, manifests, source provenance and
    inventory before setting inventory_complete. Diagnostics deny completion.
    This type and the pure evaluator do not perform that I/O or verify authenticity.
    """

    records: tuple[CardAcceptanceEvidence, ...] = Field(default=(), max_length=1024)
    inventory_complete: Annotated[bool, Field(strict=True)] = False
    diagnostics: tuple[Reference, ...] = ()


class CardCompletionDecision(CompletionRecord):
    schema_version: Literal["card_completion_decision.v1"] = "card_completion_decision.v1"
    state: CompletionState
    scope: CompletionScope | None
    acceptance_ref: Reference | None
    plan_digest: Sha256 | None
    policy_ref: Reference | None
    missing_criteria: tuple[Reference, ...]
    diagnostics: tuple[Reference, ...]
    evidence_refs: tuple[Reference, ...]

    @property
    def sufficient(self) -> bool:
        """Sufficiency for the declared criteria only, never a storage permission."""
        return self.state == CompletionState.SATISFIED
