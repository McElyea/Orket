from pathlib import Path
from typing import List, Optional, Dict, Any
from orket.vendors.base import VendorInterface, VendorRock, VendorEpic, VendorCard
from orket.orket import ConfigLoader
from orket.schema import RockConfig, EpicConfig, CardConfig

class LocalVendor(VendorInterface):
    """
    Default vendor that uses the local model/*.json files.
    Ensures backward compatibility with zero-config setup.
    """
    def __init__(self, department: str = "core"):
        self.loader = ConfigLoader(Path("model"), department)
        self.dept = department

    async def get_rocks(self) -> List[VendorRock]:
        rocks = []
        for name in self.loader.list_assets("rocks"):
            r = self.loader.load_asset("rocks", name, RockConfig)
            rocks.append(VendorRock(id=name, name=r.name, description=r.description, status="active"))
        return rocks

    async def get_epics(self, rock_id: Optional[str] = None) -> List[VendorEpic]:
        epics = []
        # If rock_id is provided, only return epics linked to that rock
        if rock_id:
            rock = self.loader.load_asset("rocks", rock_id, RockConfig)
            for entry in rock.epics:
                ename = entry["epic"]
                try:
                    e = self.loader.load_asset("epics", ename, EpicConfig)
                    epics.append(VendorEpic(id=ename, rock_id=rock_id, name=e.name, description=e.description))
                except: pass
        else:
            # Return all standalone epics
            for name in self.loader.list_assets("epics"):
                e = self.loader.load_asset("epics", name, EpicConfig)
                epics.append(VendorEpic(id=name, name=e.name, description=e.description))
        return epics

    async def get_cards(self, epic_id: Optional[str] = None) -> List[VendorCard]:
        cards = []
        if epic_id:
            e = self.loader.load_asset("epics", epic_id, EpicConfig)
            for c in e.cards:
                cards.append(VendorCard(
                    id=c.id, 
                    epic_id=epic_id, 
                    summary=c.summary, 
                    description=c.note, 
                    status=c.status, 
                    priority=c.priority,
                    assignee=c.assignee
                ))
        return cards

    async def update_card_status(self, card_id: str, status: str) -> bool:
        from orket.persistence import PersistenceManager
        db = PersistenceManager()
        db.update_card_status(card_id, status)
        return True

    async def add_card(self, epic_id: str, summary: str, description: str) -> VendorCard:
        raise NotImplementedError("Use runtime DB to add cards to local sessions.")

    async def get_card_details(self, card_id: str) -> VendorCard:
        from orket.persistence import PersistenceManager
        db = PersistenceManager()
        return VendorCard(id=card_id, summary="Local Card", status="ready", priority="Medium")
