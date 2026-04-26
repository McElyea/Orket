from __future__ import annotations

from .biased_first_player import BiasedFirstPlayerRuleSystem
from .deadlock import DeadlockRuleSystem
from .illegal_action import IllegalActionRuleSystem
from .loop import LoopRuleSystem
from ..contracts import RuleSystem


TOY_RULESYSTEMS: dict[str, type[RuleSystem]] = {
    "toy_loop": LoopRuleSystem,
    "loop": LoopRuleSystem,
    "toy_deadlock": DeadlockRuleSystem,
    "deadlock": DeadlockRuleSystem,
    "toy_illegal_action": IllegalActionRuleSystem,
    "illegal_action": IllegalActionRuleSystem,
    "toy_biased_first_player": BiasedFirstPlayerRuleSystem,
    "biased_first_player": BiasedFirstPlayerRuleSystem,
    "toy_golden_determinism": LoopRuleSystem,
    "golden_determinism": LoopRuleSystem,
}


def build_toy_rulesystem(rulesystem_id: str) -> RuleSystem:
    normalized = str(rulesystem_id or "").strip().lower()
    rulesystem_class = TOY_RULESYSTEMS.get(normalized)
    if rulesystem_class is None:
        raise ValueError(f"Unknown rulesystem_id '{rulesystem_id}'")
    rulesystem = rulesystem_class()
    if not isinstance(rulesystem, RuleSystem):
        raise TypeError(f"Registered RuleSystem '{rulesystem_id}' does not satisfy the RuleSystem protocol")
    return rulesystem
