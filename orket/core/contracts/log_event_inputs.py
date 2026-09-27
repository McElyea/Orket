"""Hook-free capture of application event values before required publication."""
from __future__ import annotations

import math
from typing import Any

LOG_EVENT_INPUT_ERROR = "E_LOG_EVENT_INPUT_UNSUPPORTED"


def _detach(value: Any, active: set[int]) -> Any:
    kind = type(value)
    # Identity checks also avoid user-defined metaclass equality or hashing.
    if value is None or kind is str or kind is bool or kind is int:
        return value
    if kind is float:
        if math.isfinite(value):
            return value
        raise TypeError(LOG_EVENT_INPUT_ERROR)
    if kind is not dict and kind is not list and kind is not tuple:
        raise TypeError(LOG_EVENT_INPUT_ERROR)
    identity = id(value)
    if identity in active:
        raise TypeError(LOG_EVENT_INPUT_ERROR)
    active.add(identity)
    try:
        if kind is dict:
            result = {}
            for key, child in value.items():
                if type(key) is not str:
                    raise TypeError(LOG_EVENT_INPUT_ERROR)
                result[key] = _detach(child, active)
            return result
        children = [_detach(child, active) for child in value]
        return tuple(children) if kind is tuple else children
    finally:
        active.remove(identity)


def capture_log_event_inputs(event: str, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Detach exact built-ins without invoking copy, conversion or serializer hooks."""
    if type(event) is not str or type(payload) is not dict:
        raise TypeError(LOG_EVENT_INPUT_ERROR)
    try:
        return event, _detach(payload, set())
    except RecursionError:
        raise TypeError(LOG_EVENT_INPUT_ERROR) from None
