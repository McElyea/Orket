"""Application resource command policy, run synchronously inside an owned worker."""
import json
from pathlib import Path

from orket.adapters.storage.driver_resource_store import DriverResourceStore
from orket.application.services.driver_resource_values import (
    _environment_template,
    _epic_template,
    _rock_template,
    _slug_name,
    _team_template,
    normalize_epic,
)


class DriverResourceCommands:
    def __init__(self, store: DriverResourceStore):
        self.store = store

    def execute(self, verb: str, args: list[str]) -> str:
        handlers = {"list": self._cli_handle_list, "show": self._cli_handle_show,
                    "create": self._cli_handle_create, "add-card": self._cli_handle_add_card,
                    "add_card": self._cli_handle_add_card, "list-cards": self._cli_handle_list_cards,
                    "list_cards": self._cli_handle_list_cards}
        if verb in {"create", "add-card", "add_card"}:
            with self.store.guard():
                return handlers[verb](args)
        return handlers[verb](args)

    def _cli_handle_list(self, args: list[str]) -> str:
        if not args:
            return "Usage: /list <resource> [department]"
        resource = args[0].strip().lower()
        if resource == "departments":
            departments = self.store.departments()
            return f"Departments ({len(departments)}): " + ", ".join(departments)
        if resource == "cards":
            if len(args) < 2:
                return "Usage: /list cards <epic> [department]"
            epic_name = _slug_name(args[1])
            department = args[2] if len(args) > 2 else "core"
            return self._list_cards_for_epic(epic_name, department)
        department = args[1] if len(args) > 1 else "core"
        resource_dir = self._resource_dir(resource, department)
        if resource_dir is None:
            return f"Unknown list resource '{resource}'. Use /help."
        if not resource_dir.exists():
            return f"No '{resource}' directory found in department '{department}'."
        names = sorted([f.stem for f in resource_dir.glob("*.json")])
        return f"{resource.title()} in {department} ({len(names)}): " + ", ".join(names)

    def _cli_handle_show(self, args: list[str]) -> str:
        if len(args) < 2:
            return "Usage: /show <team|environment|epic|rock> <name> [department]"
        resource = args[0].strip().lower()
        name = _slug_name(args[1])
        department = args[2] if len(args) > 2 else None
        path = self._find_asset_path(resource, name, department)
        if path is None or not path.exists():
            return f"{resource} '{name}' not found."
        data = self.store.read(path)
        return json.dumps(data, indent=2)

    def _cli_handle_create(self, args: list[str]) -> str:
        if len(args) < 2:
            return "Usage: /create <team|environment|epic|rock> <name> [department]"
        resource = args[0].strip().lower()
        name = _slug_name(args[1])
        department = args[2] if len(args) > 2 else "core"
        resource_dir = self._resource_dir(f"{resource}s" if not resource.endswith("s") else resource, department)
        if resource_dir is None:
            resource_dir = self._resource_dir(resource, department)
        if resource_dir is None:
            return f"Unknown create resource '{resource}'. Use /help."
        target = resource_dir / f"{name}.json"
        if target.exists():
            return f"{resource} '{name}' already exists in {department}."

        if resource in {"team", "teams"}:
            payload = _team_template(name)
        elif resource in {"environment", "environments"}:
            payload = _environment_template(name)
        elif resource in {"epic", "epics"}:
            payload = _epic_template(name)
        elif resource in {"rock", "rocks"}:
            payload = _rock_template(name, department)
        else:
            return f"Create for '{resource}' is not supported."

        self.store.write(target, payload)
        return f"Created {resource.rstrip('s')} '{name}' at {target.as_posix()}."

    def _cli_handle_list_cards(self, args: list[str]) -> str:
        if not args:
            return "Usage: /list-cards <epic> [department]"
        epic_name = _slug_name(args[0])
        department = args[1] if len(args) > 1 else "core"
        return self._list_cards_for_epic(epic_name, department)

    def _cli_handle_add_card(self, args: list[str]) -> str:
        if len(args) < 4:
            return "Usage: /add-card <epic> <seat> <priority> <summary...> [--department <department>]"
        department = "core"
        filtered: list[str] = []
        i = 0
        while i < len(args):
            token = args[i]
            if token == "--department" and i + 1 < len(args):
                department = args[i + 1]
                i += 2
                continue
            filtered.append(token)
            i += 1
        if len(filtered) < 4:
            return "Usage: /add-card <epic> <seat> <priority> <summary...> [--department <department>]"
        epic_name = _slug_name(filtered[0])
        seat = filtered[1]
        try:
            priority = float(filtered[2])
        except ValueError:
            return f"Invalid priority '{filtered[2]}'. Use a numeric value."
        summary = " ".join(filtered[3:]).strip()
        if not summary:
            return "Card summary is required."

        path = self._find_asset_path("epic", epic_name, department)
        if path is None or not path.exists():
            return f"Epic '{epic_name}' not found in {department}."
        epic_data, migrated = normalize_epic(self.store.read(path))
        epic_data["issues"].append({"summary": summary, "seat": seat, "priority": priority})
        self.store.write(path, epic_data)
        migration_note = " Legacy epic child key was normalized to 'issues'." if migrated else ""
        return f"Added card to epic '{epic_name}' in {department}: [{seat}] p={priority} {summary}{migration_note}"

    def _resource_dir(self, resource: str, department: str) -> Path | None:
        normalized = resource.strip().lower()
        aliases = {
            "team": "teams",
            "teams": "teams",
            "environment": "environments",
            "environments": "environments",
            "epic": "epics",
            "epics": "epics",
            "rock": "rocks",
            "rocks": "rocks",
            "role": "roles",
            "roles": "roles",
            "dialect": "dialects",
            "dialects": "dialects",
            "skill": "skills",
            "skills": "skills",
            "contract": "contracts",
            "contracts": "contracts",
            "artifact": "artifacts",
            "artifacts": "artifacts",
        }
        folder = aliases.get(normalized)
        if not folder:
            return None
        return self.store.path(department, folder)

    def _find_asset_path(self, resource: str, name: str, department: str | None = None) -> Path | None:
        search_departments = (
            [department] if department else self.store.departments()
        )
        for dept in search_departments:
            resource_dir = self._resource_dir(resource, dept)
            if resource_dir is None:
                continue
            candidate = self.store.path(str(resource_dir / f"{name}.json"))
            if candidate.exists():
                return candidate
        return None

    def _list_cards_for_epic(self, epic_name: str, department: str) -> str:
        path = self._find_asset_path("epic", epic_name, department)
        if path is None or not path.exists():
            return f"Epic '{epic_name}' not found in {department}."
        epic_data = self.store.read(path)
        if not isinstance(epic_data.get("issues"), list):
            if isinstance(epic_data.get("cards"), list):
                return (
                    f"Epic '{epic_name}' still uses the legacy child key 'cards'. "
                    "Migrate it to 'issues' before using list/add card operations."
                )
            return f"Epic '{epic_name}' has no issues."
        cards = list(epic_data.get("issues") or [])
        if not cards:
            return f"Epic '{epic_name}' has no cards."
        lines = [f"Cards in {epic_name} ({len(cards)}):"]
        for idx, card in enumerate(cards, start=1):
            summary = str(card.get("summary") or card.get("name") or "Untitled")
            seat = str(card.get("seat") or "unspecified")
            priority = str(card.get("priority") or "n/a")
            lines.append(f"{idx}. [{seat}] p={priority} {summary}")
        return "\n".join(lines)
