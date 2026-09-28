"""Hook-free detachment of exact built-in value graphs for explicit admission."""
from __future__ import annotations

import math
from typing import Any


def _detach(value: Any, active: set[int], error_code: str) -> Any:
    kind = type(value)
    # Identity checks also avoid user-defined metaclass equality or hashing.
    if value is None or kind is str or kind is bool or kind is int:
        return value
    if kind is float:
        if math.isfinite(value):
            return value
        raise TypeError(error_code)
    if kind is not dict and kind is not list and kind is not tuple:
        raise TypeError(error_code)
    identity = id(value)
    if identity in active:
        raise TypeError(error_code)
    active.add(identity)
    try:
        if kind is dict:
            result = {}
            for key, child in value.items():
                if type(key) is not str:
                    raise TypeError(error_code)
                result[key] = _detach(child, active, error_code)
            return result
        children = [_detach(child, active, error_code) for child in value]
        return tuple(children) if kind is tuple else children
    finally:
        active.remove(identity)


def capture_builtin_values(value: Any, *, error_code: str) -> Any:
    """Detach without hooks; the boundary supplies its fixed refusal vocabulary."""
    try:
        return _detach(value, set(), error_code)
    except RecursionError:
        raise TypeError(error_code) from None
