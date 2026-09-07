from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

GOVERNED_AGENT_SCHEMA_FILENAME = "governed_agent_loop_v1.json"


def load_governed_agent_schema() -> dict[str, Any]:
    """Load the packaged canonical governed-agent wire schema."""
    schema_resource = files("orket_extension_sdk.schemas").joinpath(GOVERNED_AGENT_SCHEMA_FILENAME)
    payload = json.loads(schema_resource.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):  # pragma: no cover - package corruption guard
        raise ValueError("E_SDK_AGENT_SCHEMA_INVALID")
    return payload
