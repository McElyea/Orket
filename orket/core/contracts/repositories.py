from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from orket.core.contracts.control_plane_effect_journal_models import (
    CheckpointAcceptanceRecord,
    EffectJournalEntryRecord,
)
from orket.core.contracts.control_plane_models import (
    AttemptRecord,
    CheckpointRecord,
    FinalTruthRecord,
    LeaseRecord,
    OperatorActionRecord,
    ReconciliationRecord,
    RecoveryDecisionRecord,
    ReservationRecord,
    ResolvedConfigurationSnapshot,
    ResolvedPolicySnapshot,
    ResourceRecord,
    RunRecord,
    StepRecord,
)
from orket.core.domain.records import IssueRecord
from orket.schema import CardStatus


class CardRepository(ABC):
    """Port for managing Issue and Card state in persistence."""

    @abstractmethod
    async def get_by_id(self, card_id: str) -> IssueRecord | None: ...

    @abstractmethod
    async def get_by_build(self, build_id: str) -> list[IssueRecord]: ...

    @abstractmethod
    async def save(self, card_data: IssueRecord | dict[str, Any]) -> None: ...

    @abstractmethod
    async def update_status(self, card_id: str, status: CardStatus, assignee: str | None = None) -> None: ...


class SessionRepository(ABC):
    """Port for managing orchestration session audit trails."""

    @abstractmethod
    async def get_session(self, session_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def start_session(self, session_id: str, data: dict[str, Any]) -> None: ...

    @abstractmethod
    async def complete_session(self, session_id: str, status: str, transcript: list[dict[str, Any]]) -> None: ...


class SnapshotRepository(ABC):
    """Port for high-fidelity session snapshots."""

    @abstractmethod
    async def record(self, session_id: str, config: dict[str, Any], logs: list[dict[str, Any]]) -> None: ...

    @abstractmethod
    async def get(self, session_id: str) -> dict[str, Any] | None: ...


class ControlPlaneRecordRepository(ABC):
    """Port for durable ControlPlane record publication and lookup."""

    async def save_resolved_policy_snapshot(
        self,
        *,
        snapshot: ResolvedPolicySnapshot,
    ) -> ResolvedPolicySnapshot:
        raise NotImplementedError

    async def get_resolved_policy_snapshot(
        self,
        *,
        snapshot_id: str,
    ) -> ResolvedPolicySnapshot | None:
        raise NotImplementedError

    async def save_resolved_configuration_snapshot(
        self,
        *,
        snapshot: ResolvedConfigurationSnapshot,
    ) -> ResolvedConfigurationSnapshot:
        raise NotImplementedError

    async def get_resolved_configuration_snapshot(
        self,
        *,
        snapshot_id: str,
    ) -> ResolvedConfigurationSnapshot | None:
        raise NotImplementedError

    @abstractmethod
    async def save_reservation_record(
        self,
        *,
        record: ReservationRecord,
    ) -> ReservationRecord: ...

    @abstractmethod
    async def list_reservation_records(self, *, reservation_id: str) -> list[ReservationRecord]: ...

    @abstractmethod
    async def get_latest_reservation_record(self, *, reservation_id: str) -> ReservationRecord | None: ...

    @abstractmethod
    async def list_reservation_records_for_holder_ref(self, *, holder_ref: str) -> list[ReservationRecord]: ...

    @abstractmethod
    async def get_latest_reservation_record_for_holder_ref(self, *, holder_ref: str) -> ReservationRecord | None: ...

    @abstractmethod
    async def save_resource_record(
        self,
        *,
        record: ResourceRecord,
    ) -> ResourceRecord: ...

    @abstractmethod
    async def list_resource_records(self, *, resource_id: str) -> list[ResourceRecord]: ...

    @abstractmethod
    async def get_latest_resource_record(self, *, resource_id: str) -> ResourceRecord | None: ...

    @abstractmethod
    async def append_effect_journal_entry(
        self,
        *,
        run_id: str,
        entry: EffectJournalEntryRecord,
    ) -> EffectJournalEntryRecord: ...

    @abstractmethod
    async def list_effect_journal_entries(self, *, run_id: str) -> list[EffectJournalEntryRecord]: ...

    @abstractmethod
    async def save_checkpoint(
        self,
        *,
        record: CheckpointRecord,
    ) -> CheckpointRecord: ...

    @abstractmethod
    async def get_checkpoint(
        self,
        *,
        checkpoint_id: str,
    ) -> CheckpointRecord | None: ...

    @abstractmethod
    async def list_checkpoints(self, *, parent_ref: str) -> list[CheckpointRecord]: ...

    @abstractmethod
    async def save_checkpoint_acceptance(
        self,
        *,
        acceptance: CheckpointAcceptanceRecord,
    ) -> CheckpointAcceptanceRecord: ...

    @abstractmethod
    async def get_checkpoint_acceptance(
        self,
        *,
        checkpoint_id: str,
    ) -> CheckpointAcceptanceRecord | None: ...

    @abstractmethod
    async def save_recovery_decision(
        self,
        *,
        decision: RecoveryDecisionRecord,
    ) -> RecoveryDecisionRecord: ...

    @abstractmethod
    async def get_recovery_decision(self, *, decision_id: str) -> RecoveryDecisionRecord | None: ...

    @abstractmethod
    async def append_lease_record(
        self,
        *,
        record: LeaseRecord,
    ) -> LeaseRecord: ...

    @abstractmethod
    async def list_lease_records(self, *, lease_id: str) -> list[LeaseRecord]: ...

    @abstractmethod
    async def get_latest_lease_record(self, *, lease_id: str) -> LeaseRecord | None: ...

    @abstractmethod
    async def save_reconciliation_record(
        self,
        *,
        record: ReconciliationRecord,
    ) -> ReconciliationRecord: ...

    @abstractmethod
    async def get_reconciliation_record(self, *, reconciliation_id: str) -> ReconciliationRecord | None: ...

    @abstractmethod
    async def list_reconciliation_records(self, *, target_ref: str) -> list[ReconciliationRecord]: ...

    @abstractmethod
    async def get_latest_reconciliation_record(self, *, target_ref: str) -> ReconciliationRecord | None: ...

    @abstractmethod
    async def save_operator_action(
        self,
        *,
        record: OperatorActionRecord,
    ) -> OperatorActionRecord: ...

    @abstractmethod
    async def get_operator_action(self, *, action_id: str) -> OperatorActionRecord | None: ...

    @abstractmethod
    async def list_operator_actions(self, *, target_ref: str) -> list[OperatorActionRecord]: ...

    @abstractmethod
    async def save_final_truth(self, *, record: FinalTruthRecord) -> FinalTruthRecord: ...

    @abstractmethod
    async def get_final_truth(self, *, run_id: str) -> FinalTruthRecord | None: ...


class ControlPlaneExecutionRepository(ABC):
    """Port for durable ControlPlane run and attempt authority."""

    @abstractmethod
    async def save_run_record(
        self,
        *,
        record: RunRecord,
    ) -> RunRecord: ...

    @abstractmethod
    async def get_run_record(self, *, run_id: str) -> RunRecord | None: ...

    @abstractmethod
    async def save_attempt_record(
        self,
        *,
        record: AttemptRecord,
    ) -> AttemptRecord: ...

    @abstractmethod
    async def get_attempt_record(self, *, attempt_id: str) -> AttemptRecord | None: ...

    @abstractmethod
    async def list_attempt_records(self, *, run_id: str) -> list[AttemptRecord]: ...

    @abstractmethod
    async def save_step_record(
        self,
        *,
        record: StepRecord,
    ) -> StepRecord: ...

    @abstractmethod
    async def get_step_record(self, *, step_id: str) -> StepRecord | None: ...

    @abstractmethod
    async def list_step_records(self, *, attempt_id: str) -> list[StepRecord]: ...
