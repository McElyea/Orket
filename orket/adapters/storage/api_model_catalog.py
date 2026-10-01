"""Native model catalog observations retained by the existing API workspace reader."""
import json
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import require_sync_context
from orket.core.contracts.api_role_catalog import normalize_role_name

side_effecting = True


def read_active_roles(model_root: Path) -> list[str]:
    require_sync_context(code="E_API_CATALOG_REQUIRES_ASYNC_OWNER")
    team_roles: set[str] = set()
    for team_file in sorted(model_root.glob("*/teams/*.json")):
        try:
            payload = json.loads(team_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue

        declared_roles = payload.get("roles")
        if isinstance(declared_roles, dict):
            for role_name in declared_roles:
                role = normalize_role_name(role_name)
                if role:
                    team_roles.add(role)

        seats = payload.get("seats")
        if not isinstance(seats, dict):
            continue
        for seat in seats.values():
            if not isinstance(seat, dict):
                continue
            for role_name in seat.get("roles", []) or []:
                role = normalize_role_name(role_name)
                if role:
                    team_roles.add(role)

    if team_roles:
        return sorted(team_roles)

    fallback_roles: list[str] = []
    for role_file in sorted((model_root / "core" / "roles").glob("*.json")):
        role = normalize_role_name(role_file.stem)
        if role:
            fallback_roles.append(role)
    return fallback_roles


def _load_role_catalog(model_root: Path) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for role_file in sorted(model_root.glob("*/roles/*.json")):
        try:
            payload = json.loads(role_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        role_name = normalize_role_name(payload.get("name") or role_file.stem)
        if not role_name:
            continue
        catalog[role_name] = {
            "name": str(payload.get("name") or role_name),
            "description": payload.get("description"),
            "tools": list(payload.get("tools") or []),
        }
    return catalog


def read_team_topology(model_root: Path) -> list[dict[str, Any]]:
    require_sync_context(code="E_API_CATALOG_REQUIRES_ASYNC_OWNER")
    role_catalog = _load_role_catalog(model_root)
    teams: list[dict[str, Any]] = []
    for team_file in sorted(model_root.glob("*/teams/*.json")):
        department = team_file.parent.parent.name
        team_id = team_file.stem
        try:
            payload = json.loads(team_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue

        seats_payload = payload.get("seats")
        seats: list[dict[str, Any]] = []
        referenced_roles: set[str] = set()
        if isinstance(seats_payload, dict):
            for seat_id, seat_value in seats_payload.items():
                seat = seat_value if isinstance(seat_value, dict) else {}
                raw_roles = list(seat.get("roles") or [])
                normalized_roles = [normalize_role_name(role) for role in raw_roles if normalize_role_name(role)]
                for role in normalized_roles:
                    referenced_roles.add(role)
                seats.append(
                    {
                        "seat_id": str(seat_id),
                        "name": seat.get("name"),
                        "roles": normalized_roles,
                    }
                )

        raw_declared_roles = payload.get("roles")
        declared_roles: dict[str, Any] = dict(raw_declared_roles) if isinstance(raw_declared_roles, dict) else {}
        role_items: list[dict[str, Any]] = []
        all_roles = sorted(
            set(referenced_roles)
            | {normalize_role_name(role) for role in declared_roles if normalize_role_name(role)}
        )
        for role_name in all_roles:
            declared = declared_roles.get(role_name)
            declared = declared if isinstance(declared, dict) else {}
            catalog_entry = role_catalog.get(role_name, {})
            role_items.append(
                {
                    "role": role_name,
                    "name": declared.get("name") or catalog_entry.get("name") or role_name,
                    "description": declared.get("description") or catalog_entry.get("description"),
                    "tools": list(declared.get("tools") or catalog_entry.get("tools") or []),
                    "source": ("team" if bool(declared) else ("catalog" if bool(catalog_entry) else "seat_reference")),
                }
            )

        teams.append(
            {
                "department": department,
                "team_id": team_id,
                "name": payload.get("name") or team_id,
                "description": payload.get("description"),
                "seats": sorted(seats, key=lambda item: item["seat_id"]),
                "roles": role_items,
            }
        )
    return teams
