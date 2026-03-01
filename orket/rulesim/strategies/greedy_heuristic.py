from __future__ import annotations

from random import Random
from typing import Any


class GreedyHeuristicStrategy:
    def __init__(self, *, score_map: dict[str, float] | None = None) -> None:
        self._score_map = dict(score_map or {})

    def select_action(self, observation: Any, legal_actions: list[Any], rng: Random, context: dict[str, Any]) -> Any:
        if not legal_actions:
            raise ValueError("legal_actions must not be empty")
        rulesystem = context.get("rulesystem")
        if rulesystem is None:
            return legal_actions[0]
        best = legal_actions[0]
        best_score = float(self._score_map.get(str(rulesystem.action_key(best)), 0.0))
        for action in legal_actions[1:]:
            key = str(rulesystem.action_key(action))
            score = float(self._score_map.get(key, 0.0))
            if score > best_score:
                best = action
                best_score = score
        return best

