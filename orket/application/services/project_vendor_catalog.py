"""Application interpretation of project catalog files, used only in an owned worker."""
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, RootModel

from orket.application.services.decision_node_registry import DecisionNodeRegistry
from orket.runtime.config.config_loader import ConfigLoader
from orket.schema import BaseCardConfig, EpicConfig
from orket.vendors.base import VendorCard, VendorEpic, VendorRock


def _component(value: str) -> str:
    if not isinstance(value, str) or not value or value in {".", ".."} or any(c in value for c in "/\\:"):
        raise ValueError("E_VENDOR_CATALOG_COMPONENT_INVALID")
    return value


@dataclass(frozen=True)
class ProjectCatalogLocation:
    project_root: Path
    department: str = "core"

    def __post_init__(self) -> None:
        root = Path(self.project_root)
        if not root.is_absolute():
            raise ValueError("E_VENDOR_PROJECT_ROOT_ABSOLUTE_REQUIRED")
        object.__setattr__(self, "project_root", root)
        _component(self.department)


@dataclass(frozen=True)
class ProjectVendorCatalog:
    location: ProjectCatalogLocation

    def _reference(self, identifier: str) -> tuple[str, str]:
        if not isinstance(identifier, str):
            raise ValueError("E_VENDOR_CATALOG_COMPONENT_INVALID")
        parts = identifier.split("/")
        if len(parts) == 1:
            return self.location.department, _component(parts[0])
        if len(parts) == 2:
            return _component(parts[0]), _component(parts[1])
        raise ValueError("E_VENDOR_CATALOG_COMPONENT_INVALID")

    def _identifier(self, department: str, name: str) -> str:
        return name if department == self.location.department else f"{department}/{name}"

    def _loader(self, department: str) -> ConfigLoader:
        return ConfigLoader(self.location.project_root, _component(department),
                            decision_nodes=DecisionNodeRegistry(settings={}))

    def _load(self, category: str, department: str, name: str) -> dict[str, Any]:
        return self._loader(department).load_asset(category, _component(name), RootModel[dict[str, Any]]).root

    @staticmethod
    def _metadata(payload: dict[str, Any], identifier: str) -> BaseCardConfig:
        # Catalog projection validates displayed metadata, not execution admission.
        # Supplying identity prevents a read from invoking the schema's UUID default.
        return BaseCardConfig.model_validate({**payload, "id": identifier})

    def rocks(self) -> list[VendorRock]:
        department = self.location.department
        result = []
        for name in self._loader(department).list_assets("rocks"):
            payload = self._load("rocks", department, name)
            card = self._metadata({**payload, "status": "ready"}, name)
            result.append(VendorRock(id=name, name=card.name or "", description=card.description,
                                     status=payload.get("status", "ready")))
        return result

    def epics(self, rock_id: str | None) -> list[VendorEpic]:
        if rock_id is None:
            entries = [(self.location.department, name) for name in self._loader(self.location.department).list_assets("epics")]
        else:
            department, name = self._reference(rock_id)
            rock = self._load("rocks", department, name)
            references = rock.get("epics")
            if not isinstance(references, list) or any(not isinstance(row, dict) for row in references):
                raise ValueError("E_VENDOR_ROCK_EPICS_INVALID")
            entries = [(_component(row.get("department", department)), _component(row.get("epic"))) for row in references]
        result = []
        for department, name in entries:
            identifier = self._identifier(department, name)
            card = self._metadata(self._load("epics", department, name), identifier)
            result.append(VendorEpic(id=identifier, rock_id=rock_id, name=card.name or "", description=card.description))
        return result

    def cards(self, epic_id: str | None) -> list[VendorCard]:
        if epic_id is None:
            return []
        department, name = self._reference(epic_id)
        payload = self._load("epics", department, name)
        aliases = EpicConfig.model_fields["issues"].validation_alias
        assert isinstance(aliases, AliasChoices)
        rows = next((payload[key] for key in aliases.choices if key in payload), [])
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("E_VENDOR_EPIC_CARDS_INVALID")
        result = []
        seen = set()
        for row in rows:
            identifier = row.get("id")
            if not isinstance(identifier, str) or not identifier.strip():
                raise ValueError("E_VENDOR_CARD_ID_REQUIRED")
            if identifier in seen:
                raise ValueError("E_VENDOR_CARD_ID_DUPLICATE")
            seen.add(identifier)
            card = self._metadata(row, identifier)
            result.append(VendorCard(id=card.id, epic_id=epic_id, summary=card.name or "",
                                     description=card.description or card.note, status=card.status.value,
                                     priority=str(card.priority), assignee=row.get("assignee")))
        return result
