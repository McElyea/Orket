# scores/score_loader.py
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

SCORES_DIR = os.path.join(os.getcwd(), "scores")


@dataclass
class Score:
    name: str
    roles: List[str]
    dependencies: Dict[str, List[str]]
    require_all_roles_complete: bool
    description: Optional[str] = None


def load_score(score_name: str) -> Score:
    path = os.path.join(SCORES_DIR, f"{score_name}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Score config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    completion = data.get("completion", {})
    return Score(
        name=data["name"],
        roles=data["roles"],
        dependencies=data.get("dependencies", {}),
        require_all_roles_complete=completion.get("require_all_roles_complete", True),
        description=data.get("description"),
    )
