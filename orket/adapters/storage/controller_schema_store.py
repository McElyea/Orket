"""Read the selected controller schema; application owns the worker lifetime."""
from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

side_effecting = False


def read_controller_schema(schema_path: Path | None = None) -> object:
    source = schema_path if schema_path is not None else files("orket").joinpath(
        "runtime", "config", "assets", "contracts", "controller_observability_v1.json")
    # A selected file can contain any JSON root; its consumer owns validation.
    schema: object = json.loads(source.read_bytes())
    return schema
