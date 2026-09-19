"""Application-owned catalog reads and verified runtime card mutations."""
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.application.services.project_vendor_catalog import ProjectCatalogLocation, ProjectVendorCatalog
from orket.core.contracts.repositories import CardRepository
from orket.schema import CardStatus
from orket.vendors.base import VendorCard, VendorEpic, VendorInterface, VendorRock


@dataclass(frozen=True)
class LocalProjectVendor(VendorInterface):
    location: ProjectCatalogLocation
    runtime_db: Path
    _cards: CardRepository = field(init=False, repr=False)

    def __post_init__(self) -> None:
        database = Path(self.runtime_db)
        if not database.is_absolute():
            raise ValueError("E_VENDOR_DATABASE_ABSOLUTE_REQUIRED")
        object.__setattr__(self, "runtime_db", database)
        object.__setattr__(self, "_cards", AsyncCardRepository(database))

    async def _prepare_database(self) -> None:
        await run_owned_thread(partial(self.runtime_db.parent.mkdir, parents=True, exist_ok=True),
                               label="vendor-database-directory")

    async def get_rocks(self) -> list[VendorRock]:
        return await run_owned_thread(ProjectVendorCatalog(self.location).rocks, label="vendor-rock-catalog")

    async def get_epics(self, rock_id: str | None = None) -> list[VendorEpic]:
        return await run_owned_thread(partial(ProjectVendorCatalog(self.location).epics, rock_id), label="vendor-epic-catalog")

    async def get_cards(self, epic_id: str | None = None) -> list[VendorCard]:
        return await run_owned_thread(partial(ProjectVendorCatalog(self.location).cards, epic_id), label="vendor-card-catalog")

    async def update_card_status(self, card_id: str, status: str) -> bool:
        requested = CardStatus(status)

        async def apply_and_verify() -> bool:
            await self._prepare_database()
            await self._cards.update_status(card_id, requested)
            observed = await self._cards.get_by_id(card_id)
            if observed is None or observed.status != requested:
                raise ValueError("E_VENDOR_CARD_STATUS_UNVERIFIED")
            return True

        return await run_owned_io(apply_and_verify, label="vendor-card-status", preserve_failure=True)

    async def add_card(self, epic_id: str, summary: str, description: str) -> VendorCard:
        raise NotImplementedError("Use runtime DB to add cards to local sessions.")

    async def get_card_details(self, card_id: str) -> VendorCard:
        async def read() -> VendorCard:
            await self._prepare_database()
            record = await self._cards.get_by_id(card_id)
            if record is None:
                raise ValueError(f"Card not found: {card_id}")
            return VendorCard(id=record.id, summary=record.summary, description=record.note,
                              status=record.status.value, priority=str(record.priority), assignee=record.assignee)

        return await run_owned_io(read, label="vendor-card-read", preserve_failure=True)
