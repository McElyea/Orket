from __future__ import annotations

from typing import Any

from orket.application.services.loop_decision_service import admit_policy_names
from orket.core.contracts.decision_inputs import SeatPolicyInput
from orket.exceptions import ExecutionFailed


def normalize_turn_contract_override_list(value: Any, *, lowercase: bool = False) -> list[str] | None:
    if not isinstance(value, list):
        return None
    normalized: list[str] = []
    for item in value:
        token = str(item).strip()
        if not token:
            continue
        normalized.append(token.lower() if lowercase else token)
    return normalized


def resolve_policy_list(
    *,
    loop_policy_node: Any,
    attribute: str,
    inputs: SeatPolicyInput,
) -> list[str]:
    resolver = getattr(loop_policy_node, attribute, None)
    if not callable(resolver):
        return []
    return admit_policy_names(resolver(inputs))


def resolve_policy_token(
    *,
    loop_policy_node: Any,
    attribute: str,
    inputs: SeatPolicyInput,
    default: str,
) -> str:
    resolver = getattr(loop_policy_node, attribute, None)
    if not callable(resolver):
        return default
    value = resolver(inputs)
    if type(value) is not str:
        raise ExecutionFailed("E_LOOP_POLICY_INVALID_TOKEN")
    return value
