from __future__ import annotations

from typing import Any

from orket.schema import CardStatus, IssueConfig


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
    seat_name: str,
    issue: IssueConfig,
    turn_status: CardStatus,
) -> list[str]:
    resolver = getattr(loop_policy_node, attribute, None)
    if not callable(resolver):
        return []
    try:
        return list(
            resolver(
                seat_name=seat_name,
                issue=issue,
                turn_status=turn_status,
            )
            or []
        )
    except TypeError:
        return list(resolver(seat_name) or [])


def resolve_policy_token(
    *,
    loop_policy_node: Any,
    attribute: str,
    seat_name: str,
    issue: IssueConfig,
    turn_status: CardStatus,
    default: str,
) -> str:
    resolver = getattr(loop_policy_node, attribute, None)
    if not callable(resolver):
        return default
    try:
        return str(
            resolver(
                seat_name=seat_name,
                issue=issue,
                turn_status=turn_status,
            )
        )
    except TypeError:
        return str(resolver(seat_name))
