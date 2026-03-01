from __future__ import annotations

from random import Random
from typing import Any


class RandomUniformStrategy:
    def select_action(self, observation: Any, legal_actions: list[Any], rng: Random, context: dict[str, Any]) -> Any:
        if not legal_actions:
            raise ValueError("legal_actions must not be empty")
        index = rng.randrange(len(legal_actions))
        return legal_actions[index]

