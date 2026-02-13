from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

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

