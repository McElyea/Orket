"""Capture explicit execution identities before setup observations can suspend."""
from __future__ import annotations

from typing import Any

from orket.application.services.runtime_input_service import RuntimeInputService
from orket.naming import sanitize_name


def _selected_id(value: Any, field: str) -> str:
    if type(value) is not str or not value:
        raise ValueError("E_EXECUTION_POLICY_INVALID_" + field.upper())
    return value


def capture_execution_identifiers(node: Any, runtime_inputs: RuntimeInputService, *, name: str,
                                  session_id: str | None, build_id: str | None,
                                  collection: bool = False) -> tuple[str, str]:
    requested_session = session_id or runtime_inputs.create_session_id()
    sanitized = sanitize_name(name)
    select_session = node.select_epic_collection_session_id if collection else node.select_run_id
    select_build = node.select_epic_collection_build_id if collection else node.select_epic_build_id
    selected_session = _selected_id(select_session(requested_session), "session_id")
    selected_build = _selected_id(select_build(build_id, name, sanitized), "build_id")
    return selected_session, selected_build
