from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class VendorRock(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: str

class VendorEpic(BaseModel):
    id: str
    rock_id: Optional[str] = None
    name: str
    description: Optional[str] = None

class VendorCard(BaseModel):
    id: str
    epic_id: Optional[str] = None
    summary: str
    description: Optional[str] = None
    status: str
    assignee: Optional[str] = None
    priority: str

class VendorInterface(ABC):
    """
    Abstract interface for all Project Management Vendors (Gitea, ADO, Jira).
    """
    
    @abstractmethod
    async def get_rocks(self) -> List[VendorRock]:
        pass

    @abstractmethod
    async def get_epics(self, rock_id: Optional[str] = None) -> List[VendorEpic]:
        pass

    @abstractmethod
    async def get_cards(self, epic_id: Optional[str] = None) -> List[VendorCard]:
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
