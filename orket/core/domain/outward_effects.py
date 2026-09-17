from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from orket.core.domain.outward_authorization import args_hash, canonical_json


def effect_journal_entry_id(effect_id: str, state: str, fencing_generation: int) -> str:
    """Retain initial-generation references; replacement owners get distinct append-only entries."""
    scope = effect_id if fencing_generation == 1 else f"{effect_id}:fence:{fencing_generation}"
    return f"{scope}:{state}"


@dataclass(frozen=True)
class OutwardEffectRecoveryRequest:
    proposal_id: str
    request_id: str
    expected_owner_id: str
    expected_fencing_generation: int
    operator_ref: str

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (self.proposal_id, self.request_id, self.expected_owner_id, self.operator_ref)):
            raise ValueError("E_OUTWARD_RECOVERY_REQUEST_INCOMPLETE")
        if isinstance(self.expected_fencing_generation, bool) or self.expected_fencing_generation < 1:
            raise ValueError("E_OUTWARD_RECOVERY_FENCE_INVALID")

    @property
    def decision_id(self) -> str:
        return f"outward-recovery:{self.proposal_id}:{args_hash({'request_id': self.request_id})}"

    @property
    def digest_ref(self) -> str:
        return f"request:sha256:{args_hash(asdict(self))}"


@dataclass(frozen=True)
class OutwardEffectRecord:
    effect_id: str
    proposal_id: str
    binding_digest: str
    owner_id: str
    fencing_generation: int
    state: str
    claimed_at: str
    journal_entry_id: str
    dispatched_at: str | None = None
    receipt_json: str | None = None
    receipt_digest: str | None = None
    published_at: str | None = None
    recovery_decision_id: str | None = None

    def __post_init__(self) -> None:
        if self.state not in {"claimed", "dispatching", "observed", "published"}:
            raise ValueError("E_OUTWARD_EFFECT_STATE")
        if self.fencing_generation < 1 or not self.owner_id or not self.journal_entry_id:
            raise ValueError("E_OUTWARD_EFFECT_OWNER")
        if (self.fencing_generation > 1) != bool(self.recovery_decision_id):
            raise ValueError("E_OUTWARD_EFFECT_RECOVERY_REQUIRED")
        if self.state == "claimed" and self.dispatched_at is not None:
            raise ValueError("E_OUTWARD_EFFECT_CLAIM_WITH_INTENT")
        if self.state in {"claimed", "dispatching"} and (self.receipt_json is not None or self.receipt_digest is not None):
            raise ValueError("E_OUTWARD_EFFECT_UNOBSERVED_RECEIPT")
        if self.state != "published" and self.published_at is not None:
            raise ValueError("E_OUTWARD_EFFECT_PREMATURE_PUBLICATION")
        if self.state != "claimed" and self.dispatched_at is None:
            raise ValueError("E_OUTWARD_EFFECT_INTENT_REQUIRED")
        if self.state in {"observed", "published"} and self.receipt is None:
            raise ValueError("E_OUTWARD_EFFECT_RECEIPT_REQUIRED")
        if self.state == "published" and self.published_at is None:
            raise ValueError("E_OUTWARD_EFFECT_PUBLICATION_REQUIRED")

    @property
    def receipt(self) -> dict[str, Any] | None:
        if self.receipt_json is None and self.receipt_digest is None:
            return None
        if self.receipt_json is None or self.receipt_digest is None:
            raise ValueError("E_OUTWARD_EFFECT_RECEIPT_INCOMPLETE")
        result = json.loads(self.receipt_json)
        if not isinstance(result, dict) or canonical_json(result) != self.receipt_json or args_hash(result) != self.receipt_digest:
            raise ValueError("E_OUTWARD_EFFECT_RECEIPT_DIGEST")
        return result
