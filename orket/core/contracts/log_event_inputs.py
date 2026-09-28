"""Hook-free capture of application event values before required publication."""
from __future__ import annotations

from typing import Any

from orket.core.contracts.value_capture import capture_builtin_values

LOG_EVENT_INPUT_ERROR = "E_LOG_EVENT_INPUT_UNSUPPORTED"


def capture_log_event_inputs(event: str, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Detach exact built-ins without invoking copy, conversion or serializer hooks."""
    if type(event) is not str or type(payload) is not dict:
        raise TypeError(LOG_EVENT_INPUT_ERROR)
    return event, capture_builtin_values(payload, error_code=LOG_EVENT_INPUT_ERROR)
