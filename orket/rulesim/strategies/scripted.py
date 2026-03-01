from __future__ import annotations

from random import Random
from typing import Any


class ScriptedStrategy:
    def __init__(self, sequence: list[Any]) -> None:
        self._sequence = list(sequence)
        self._cursor = 0

    def select_action(self, observation: Any, legal_actions: list[Any], rng: Random, context: dict[str, Any]) -> Any:
        if self._cursor < len(self._sequence):
            action = self._sequence[self._cursor]
            self._cursor += 1
            return action
        return self._sequence[-1] if self._sequence else legal_actions[0]

