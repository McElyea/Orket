from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .turn_contract_input_capture import capture_mapping

_CONSUMED_RAW_KEYS = frozenset(
    {
        "tool_calls",
        "openai_native_tool_names",
        "total_tokens",
        "input_tokens",
        "output_tokens",
        "usage",
        "timings",
        "timing_schema_version",
        "model",
        "prompt_metadata",
        "state_delta",
        "control_plane_resume",
    }
)


@dataclass(frozen=True, slots=True)
class CapturedTurnResponse:
    """One response snapshot shared by artifacts, parsing and later consumers."""

    content: Any
    text_artifact_content: Any
    raw_payload: dict[str, Any]
    raw_artifact_content: str


def capture_turn_response(response: Any) -> CapturedTurnResponse:
    """Capture consumed response values and render raw evidence before suspension."""
    if isinstance(response, dict):
        content = response.get("content", "")
        raw_source: Any = response
    else:
        content = getattr(response, "content", "")
        raw_source = getattr(response, "raw", {})

    raw_payload = dict(raw_source) if isinstance(raw_source, dict) else {}
    detached = capture_mapping({key: raw_payload[key] for key in _CONSUMED_RAW_KEYS if key in raw_payload})
    raw_payload.update(detached)
    artifact_payload = raw_payload if isinstance(raw_source, dict) else raw_source
    raw_artifact_content = json.dumps(artifact_payload, indent=2, ensure_ascii=False, default=str)
    return CapturedTurnResponse(
        content=content,
        text_artifact_content=content or "",
        raw_payload=raw_payload,
        raw_artifact_content=raw_artifact_content,
    )


__all__ = ["CapturedTurnResponse", "capture_turn_response"]
