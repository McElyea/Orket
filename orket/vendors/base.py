from abc import ABC, abstractmethod

from pydantic import BaseModel


class VendorRock(BaseModel):
    id: str
    name: str
    description: str | None = None
    status: str


class VendorEpic(BaseModel):
    id: str
    rock_id: str | None = None
    name: str
    description: str | None = None


class VendorCard(BaseModel):
    id: str
    epic_id: str | None = None
    summary: str
    description: str | None = None
    status: str
    assignee: str | None = None
    priority: str


class VendorInterface(ABC):
    """
    Abstract interface for all Project Management Vendors (Gitea, ADO, Jira).
    """

    @abstractmethod
    async def get_rocks(self) -> list[VendorRock]:
        pass

    @abstractmethod
    async def get_epics(self, rock_id: str | None = None) -> list[VendorEpic]:
        pass

    @abstractmethod
    async def get_cards(self, epic_id: str | None = None) -> list[VendorCard]:
        pass

    @abstractmethod
    async def update_card_status(self, card_id: str, status: str) -> bool:
        pass

    @abstractmethod
    async def add_card(self, epic_id: str, summary: str, description: str) -> VendorCard:
        pass

    @abstractmethod
    async def get_card_details(self, card_id: str) -> VendorCard:
        pass
