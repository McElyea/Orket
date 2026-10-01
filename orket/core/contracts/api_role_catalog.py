"""Pure role names and filter ordering shared by API catalog observations."""
from typing import Any


def normalize_role_name(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def parse_roles_filter(roles: str | None) -> list[str]:
    if not roles:
        return []
    parsed: list[str] = []
    for token in roles.split(","):
        role = normalize_role_name(token)
        if role and role not in parsed:
            parsed.append(role)
    return parsed
