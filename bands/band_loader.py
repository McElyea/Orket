# bands/band_loader.py
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional


BANDS_DIR = os.path.join(os.getcwd(), "bands")


@dataclass
class BandRole:
    name: str
    prompt: str
    tools_allowed: List[str]


@dataclass
class Band:
    name: str
    roles: Dict[str, BandRole]
    description: Optional[str] = None


def load_band(band_name: str) -> Band:
    path = os.path.join(BANDS_DIR, f"{band_name}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Band config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    roles: Dict[str, BandRole] = {}
    for role_name, cfg in data["roles"].items():
        roles[role_name] = BandRole(
            name=role_name,
            prompt=cfg["prompt"],
            tools_allowed=cfg.get("tools_allowed", []),
        )

    return Band(
        name=data["name"],
        roles=roles,
        description=data.get("description"),
    )
