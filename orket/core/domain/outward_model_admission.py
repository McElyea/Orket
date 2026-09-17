from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from orket.core.domain.outward_authorization import canonical_json


def admission_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def model_attempt_id(run_id: str, generation: int, turn: int, step_index: int, fence: int) -> str:
    scope = canonical_json({"run_id": run_id, "execution_generation": generation,
                            "turn": turn, "step_index": step_index, "fence": fence})
    return f"outward-model-attempt:{admission_digest(scope)}"


@dataclass(frozen=True)
class OutwardModelAdmission:
    run_id: str
    execution_generation: int
    turn: int
    step_index: int
    inputs_json: str
    inputs_digest: str
    state: str
    created_at: str
    owner_id: str | None = None
    claimed_at: str | None = None
    result_json: str | None = None
    result_digest: str | None = None
    observed_at: str | None = None
    published_at: str | None = None
    fencing_generation: int = 1
    evidence_layout_version: int = 2
    recovery_decision_id: str | None = None
    recovery_records_digest: str | None = None

    def __post_init__(self) -> None:
        if self.execution_generation < 1 or self.turn < 1 or self.step_index < 0:
            raise ValueError("E_OUTWARD_MODEL_ADMISSION_SCOPE")
        if self.fencing_generation < 1 or self.evidence_layout_version not in {1, 2}:
            raise ValueError("E_OUTWARD_MODEL_ADMISSION_VERSION")
        if bool(self.recovery_decision_id) != (self.fencing_generation > 1):
            raise ValueError("E_OUTWARD_MODEL_RECOVERY_REFERENCE")
        if bool(self.recovery_records_digest) != (self.fencing_generation > 1):
            raise ValueError("E_OUTWARD_MODEL_RECOVERY_COMMITMENT")
        if self.fencing_generation > 1 and self.evidence_layout_version != 2:
            raise ValueError("E_OUTWARD_MODEL_EVIDENCE_SCOPE_REQUIRED")
        if self.state not in {"ready", "claimed", "observed", "published"}:
            raise ValueError("E_OUTWARD_MODEL_ADMISSION_STATE")
        _validate_json(self.inputs_json, self.inputs_digest)
        owned = self.state != "ready"
        if bool(self.owner_id) != owned or bool(self.claimed_at) != owned:
            raise ValueError("E_OUTWARD_MODEL_ADMISSION_OWNER")
        observed = self.state in {"observed", "published"}
        if any((value is not None) != observed for value in (self.result_json, self.result_digest, self.observed_at)):
            raise ValueError("E_OUTWARD_MODEL_ADMISSION_RESULT")
        if observed:
            _validate_json(self.result_json, self.result_digest)
        if (self.published_at is not None) != (self.state == "published"):
            raise ValueError("E_OUTWARD_MODEL_ADMISSION_PUBLICATION")

    @property
    def attempt_id(self) -> str:
        return model_attempt_id(self.run_id, self.execution_generation, self.turn, self.step_index, self.fencing_generation)

    @property
    def evidence_scope(self) -> str | None:
        return self.attempt_id.split(":", 1)[1] if self.evidence_layout_version == 2 else None

    @property
    def result(self) -> dict[str, Any]:
        if self.result_json is None:
            raise ValueError("E_OUTWARD_MODEL_ADMISSION_RESULT_REQUIRED")
        return json.loads(self.result_json)


def _validate_json(value: str, digest: str) -> None:
    parsed = json.loads(value)
    if not isinstance(parsed, dict) or canonical_json(parsed) != value or admission_digest(value) != digest:
        raise ValueError("E_OUTWARD_MODEL_ADMISSION_DIGEST")
