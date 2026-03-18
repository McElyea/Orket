from __future__ import annotations

import os
from typing import Any


E_LOCAL_PROMPT_LMSTUDIO_SESSION_MODE_INVALID = "E_LOCAL_PROMPT_LMSTUDIO_SESSION_MODE_INVALID"
_LMSTUDIO_SESSION_MODES = {"none", "context", "fixed"}


def _first_non_empty(values: list[Any]) -> str:
    for value in values:
        token = str(value or "").strip()
        if token:
            return token
    return ""


def normalize_lmstudio_session_mode(value: Any) -> str:
    token = str(value or "").strip().lower().replace("-", "_")
    if not token:
        return "none"
    if token not in _LMSTUDIO_SESSION_MODES:
        raise ValueError(f"{E_LOCAL_PROMPT_LMSTUDIO_SESSION_MODE_INVALID}:{token}")
    return token


def resolve_lmstudio_session_settings(context: dict[str, Any], provider_backend: str) -> tuple[str, str]:
    if provider_backend != "openai_compat":
        return "none", ""
    mode = normalize_lmstudio_session_mode(
        context.get("lmstudio_session_mode") or os.getenv("ORKET_LMSTUDIO_SESSION_MODE") or "none"
    )
    if mode == "none":
        return mode, ""
    if mode == "fixed":
        return mode, _first_non_empty(
            [
                context.get("lmstudio_session_id"),
                os.getenv("ORKET_LMSTUDIO_SESSION_ID"),
                "orket_lmstudio_fixed",
            ]
        )
    return mode, _first_non_empty(
        [
            context.get("session_id"),
            context.get("conversation_id"),
            context.get("lmstudio_session_id"),
            os.getenv("ORKET_LMSTUDIO_SESSION_ID"),
        ]
    )
