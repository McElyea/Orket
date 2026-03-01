from __future__ import annotations

from random import Random
from typing import Any


class MixedStrategy:
    def __init__(self, weighted_strategies: list[tuple[float, Any]]) -> None:
        total = sum(max(0.0, float(weight)) for weight, _ in weighted_strategies)
        if total <= 0:
            raise ValueError("weighted_strategies must include positive weights")
        self._weighted_strategies = [(max(0.0, float(weight)) / total, strategy) for weight, strategy in weighted_strategies]

    def select_action(self, observation: Any, legal_actions: list[Any], rng: Random, context: dict[str, Any]) -> Any:
        needle = rng.random()
        cumulative = 0.0
        strategy = self._weighted_strategies[-1][1]
        for weight, candidate in self._weighted_strategies:
            cumulative += weight
            if needle <= cumulative:
                strategy = candidate
                break
        return strategy.select_action(observation, legal_actions, rng, context)

