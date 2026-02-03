# orket/venues/venue_loader.py
import json
import os
from dataclasses import dataclass
from typing import Optional


VENUES_DIR = os.path.join(os.getcwd(), "venues")


@dataclass
class Venue:
    name: str
    band: str
    score: str
    tempo: str
    permissions_file: str
    policy_file: str
    description: Optional[str] = None


def load_venue(venue_name: str) -> Venue:
    """
    Load a venue configuration from venues/<venue_name>.json
    and return a strongly-typed Venue object.
    """
    path = os.path.join(VENUES_DIR, f"{venue_name}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Venue config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    fs_cfg = data.get("filesystem", {})

    return Venue(
        name=data["name"],
        band=data["band"],
        score=data["score"],
        tempo=data.get("tempo", "standard"),
        permissions_file=fs_cfg.get("permissions_file", "permissions.json"),
        policy_file=fs_cfg.get("policy_file", "policy.json"),
        description=data.get("description"),
    )
