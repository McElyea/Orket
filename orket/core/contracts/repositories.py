from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from orket.core.contracts.control_plane_effect_journal_models import (
    CheckpointAcceptanceRecord,
    EffectJournalEntryRecord,
)
from orket.core.contracts.control_plane_models import (
    FinalTruthRecord,
    LeaseRecord,
    ReconciliationRecord,
    RecoveryDecisionRecord,
)
from orket.schema import CardStatus


class CardRepository(ABC):
    """Port for managing Issue and Card state in persistence."""

    @abstractmethod
    async def get_by_id(self, card_id: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    async def get_by_build(self, build_id: str) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def save(self, card_data: Dict[str, Any]): ...

    @abstractmethod
    async def update_status(self, card_id: str, status: CardStatus, assignee: str = None): ...


class SessionRepository(ABC):
    """Port for managing orchestration session audit trails."""

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    async def start_session(self, session_id: str, data: Dict[str, Any]): ...

    @abstractmethod
    async def complete_session(self, session_id: str, status: str, transcript: List[Dict]): ...


class SnapshotRepository(ABC):
    """Port for high-fidelity session snapshots."""

    @abstractmethod
    async def record(self, session_id: str, config: Dict, logs: List[Dict]): ...

    @abstractmethod
    async def get(self, session_id: str) -> Optional[Dict]: ...


class ControlPlaneRecordRepository(ABC):
    """Port for durable ControlPlane record publication and lookup."""

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
    async def save_final_truth(self, *, record: FinalTruthRecord) -> FinalTruthRecord: ...

    @abstractmethod
    async def get_final_truth(self, *, run_id: str) -> FinalTruthRecord | None: ...
