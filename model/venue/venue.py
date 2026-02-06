import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass
class Venue:
    name: str
    model: str
    temperature: float
    seed: int | None
    description: str | None = None
    params: Dict[str, Any] | None = None


def load_venue(path: str | Path) -> Venue:
    """
    Load a Venue from JSON.

    A Venue defines model behavior and parameters.
    """
    path = Path(path)

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return Venue(
        name=data["name"],
        model=data["model"],
        temperature=data.get("temperature", 0.0),
        seed=data.get("seed"),
        description=data.get("description"),
        params=data.get("params"),
    )
