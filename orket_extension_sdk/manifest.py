from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class WorkloadManifest(BaseModel):
    workload_id: str = Field(min_length=1)
    entrypoint: str = Field(min_length=1)
    required_capabilities: list[str] = Field(default_factory=list)


class ExtensionManifest(BaseModel):
    manifest_version: str = Field(min_length=1)
    extension_id: str = Field(min_length=1)
    extension_version: str = Field(min_length=1)
    workloads: list[WorkloadManifest] = Field(default_factory=list)


def load_manifest(path: Path) -> ExtensionManifest:
    payload = _load_payload(path)
    try:
        return ExtensionManifest.model_validate(payload)
    except ValidationError as exc:  # pragma: no cover - exercised by tests
        raise ValueError(f"E_SDK_MANIFEST_SCHEMA: {exc}") from exc


def _load_payload(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"E_SDK_MANIFEST_NOT_FOUND: {path}")
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    try:
        if suffix == ".json":
            payload = json.loads(text)
        elif suffix in {".yaml", ".yml"}:
            try:
                import yaml
            except ModuleNotFoundError as exc:
                raise ValueError("E_SDK_MANIFEST_PARSE: PyYAML not available") from exc
            payload = yaml.safe_load(text)
        else:
            raise ValueError(f"E_SDK_MANIFEST_PARSE: unsupported extension '{suffix}'")
    except (json.JSONDecodeError, ValueError) as exc:
        if str(exc).startswith("E_SDK_"):
            raise
        raise ValueError(f"E_SDK_MANIFEST_PARSE: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("E_SDK_MANIFEST_SCHEMA: root must be object")
    return payload

