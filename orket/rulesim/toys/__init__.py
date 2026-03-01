from __future__ import annotations

from .biased_first_player import BiasedFirstPlayerRuleSystem
from .deadlock import DeadlockRuleSystem
from .illegal_action import IllegalActionRuleSystem
from .loop import LoopRuleSystem


def build_toy_rulesystem(rulesystem_id: str):
    normalized = str(rulesystem_id or "").strip().lower()
    if normalized in {"toy_loop", "loop"}:
        return LoopRuleSystem()
    if normalized in {"toy_deadlock", "deadlock"}:
        return DeadlockRuleSystem()
    if normalized in {"toy_illegal_action", "illegal_action"}:
        return IllegalActionRuleSystem()
    if normalized in {"toy_biased_first_player", "biased_first_player"}:
        return BiasedFirstPlayerRuleSystem()
    if normalized in {"toy_golden_determinism", "golden_determinism"}:
        return LoopRuleSystem()
    raise ValueError(f"Unknown rulesystem_id '{rulesystem_id}'")

