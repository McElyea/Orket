"""Unit-only execution port; shared rules, without durability or isolation claims."""
from orket.adapters.storage.async_control_plane_execution_repository import ControlPlaneExecutionConflictError
from orket.core.contracts import AttemptRecord, RunRecord, StepRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain.control_plane_run_authority import same_run_admission
from orket.core.domain.control_plane_state_revision import (
    next_execution_record,
    same_attempt_admission,
    same_step_admission,
)


class InMemoryControlPlaneExecutionRepository(ControlPlaneExecutionRepository):
    def __init__(self):
        self.run_by_id = {}
        self.attempt_by_id = {}
        self.step_by_id = {}

    @staticmethod
    def _save(records, key, record, same_admission):
        incoming = type(record).model_validate(record.model_dump(warnings=False))
        existing = records.get(key)
        if existing is not None and not same_admission(existing, incoming):
            raise ControlPlaneExecutionConflictError('immutable execution admission changed')
        saved = next_execution_record(existing, incoming, ControlPlaneExecutionConflictError)
        records[key] = saved.model_copy(deep=True)
        return saved

    async def save_run_record(self, *, record: RunRecord) -> RunRecord:
        return self._save(self.run_by_id, record.run_id, record, same_run_admission)

    async def get_run_record(self, *, run_id: str) -> RunRecord | None:
        record = self.run_by_id.get(run_id)
        return record.model_copy(deep=True) if record else None

    async def save_attempt_record(self, *, record: AttemptRecord) -> AttemptRecord:
        return self._save(self.attempt_by_id, record.attempt_id, record, same_attempt_admission)

    async def get_attempt_record(self, *, attempt_id: str) -> AttemptRecord | None:
        record = self.attempt_by_id.get(attempt_id)
        return record.model_copy(deep=True) if record else None

    async def list_attempt_records(self, *, run_id: str) -> list[AttemptRecord]:
        return sorted([r.model_copy(deep=True) for r in self.attempt_by_id.values() if r.run_id == run_id],
                      key=lambda r: r.attempt_ordinal)

    async def save_step_record(self, *, record: StepRecord) -> StepRecord:
        return self._save(self.step_by_id, record.step_id, record, same_step_admission)

    async def get_step_record(self, *, step_id: str) -> StepRecord | None:
        record = self.step_by_id.get(step_id)
        return record.model_copy(deep=True) if record else None

    async def list_step_records(self, *, attempt_id: str) -> list[StepRecord]:
        return sorted([r.model_copy(deep=True) for r in self.step_by_id.values() if r.attempt_id == attempt_id],
                      key=lambda r: r.step_id)
