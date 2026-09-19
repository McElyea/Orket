"""Read the selected controller schema; application owns the worker lifetime."""
from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

side_effecting = False


def read_controller_schema(schema_path: Path | None = None) -> dict[str, Any] | bool:
    source = schema_path if schema_path is not None else files("orket").joinpath(
        "runtime", "config", "assets", "contracts", "controller_observability_v1.json")
    return json.loads(source.read_bytes())
