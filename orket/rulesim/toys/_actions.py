from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def require_action_kind(action: Mapping[str, Any]) -> str:
    kind = action.get("kind")
    if not isinstance(kind, str):
        raise TypeError("RuleSystem action.kind must be a string")
    return kind

