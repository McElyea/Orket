import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from model.venue.venue import Venue, load_venue
from model.band.band import Band, load_band
from model.score.score import Score, load_score


@dataclass
class Flow:
    name: str
    description: str | None
    venue: Venue
    band: Band
    score: Score
    raw: Dict[str, Any]


def load_flow(path: str | Path) -> Flow:
    """
    Load a Flow from JSON.

    A Flow bundles:
    - Venue (model behavior)
    - Band (roles, tools, policies)
    - Score (step sequencing)
    """
    path = Path(path)

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    name = data["name"]
    description = data.get("description")

    venue_path = Path(data["venue"])
    band_path = Path(data["band"])
    score_path = Path(data["score"])

    venue = load_venue(venue_path)
    band = load_band(band_path)
    score = load_score(score_path)

    return Flow(
        name=name,
        description=description,
        venue=venue,
        band=band,
        score=score,
        raw=data,
    )
