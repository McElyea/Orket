import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List


@dataclass
class Score:
    name: str
    steps: List[dict]
    tempo: str = "standard"
    description: str | None = None


def load_score(path: str | Path) -> Score:
    """
    Load a Score from JSON.

    A Score defines sequencing only. Roles come from the Band.
    """
    path = Path(path)

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    name = data["name"]
    steps = data["steps"]

    tempo = data.get("tempo", "standard")
    description = data.get("description")

    return Score(
        name=name,
        steps=steps,
        tempo=tempo,
        description=description,
    )
