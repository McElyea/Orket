import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class Role:
    name: str
    description: str | None
    tools: List[str]
    policy: Dict[str, Any] | None


@dataclass
class Band:
    name: str
    description: str | None
    roles: Dict[str, Role]


def load_band(path: str | Path) -> Band:
    """
    Load a Band from JSON.

    A Band defines the available roles, their tools, and any attached policy.
    """
    path = Path(path)

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    name = data["name"]
    description = data.get("description")

    roles_data = data["roles"]
    roles: Dict[str, Role] = {}

    for role_name, role_cfg in roles_data.items():
        roles[role_name] = Role(
            name=role_name,
            description=role_cfg.get("description"),
            tools=role_cfg.get("tools", []),
            policy=role_cfg.get("policy"),
        )

    return Band(
        name=name,
        description=description,
        roles=roles,
    )
