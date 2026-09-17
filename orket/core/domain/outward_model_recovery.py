from __future__ import annotations

from dataclasses import asdict, dataclass

from orket.core.domain.outward_authorization import args_hash


@dataclass(frozen=True)
class OutwardModelRecoveryRequest:
    run_id: str
    request_id: str
    execution_generation: int
    turn: int
    step_index: int
    expected_owner_id: str
    expected_fencing_generation: int
    operator_ref: str

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (self.run_id, self.request_id, self.expected_owner_id, self.operator_ref)):
            raise ValueError("E_OUTWARD_MODEL_RECOVERY_REQUEST_INCOMPLETE")
        values = (self.execution_generation, self.turn, self.expected_fencing_generation)
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in values):
            raise ValueError("E_OUTWARD_MODEL_RECOVERY_SCOPE")
        if isinstance(self.step_index, bool) or not isinstance(self.step_index, int) or self.step_index < 0:
            raise ValueError("E_OUTWARD_MODEL_RECOVERY_SCOPE")

    @property
    def decision_id(self) -> str:
        return f"outward-model-recovery:{args_hash({'run_id': self.run_id, 'request_id': self.request_id})}"

    @property
    def digest_ref(self) -> str:
        return f"request:sha256:{args_hash(asdict(self))}"
