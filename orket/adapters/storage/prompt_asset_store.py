"""Prompt files share model-root ownership with driver resource writers."""
from __future__ import annotations

import json
from pathlib import Path

from orket.adapters.storage.driver_resource_store import DriverResourceStore
from orket.adapters.storage.file_admission import require_regular_or_absent
from orket.core.contracts.prompt_assets import prompt_asset_name


class PromptAssetStore:
    side_effecting = True

    def __init__(self, project_root: Path):
        self.models = DriverResourceStore(project_root / "model")

    def guard(self):
        return self.models.guard()

    def directory(self, kind: str) -> Path:
        if kind not in {"role", "dialect"}:
            raise ValueError(f"Unsupported asset kind: {kind}")
        return self.models.path("core", kind + "s")

    def path(self, kind: str, name: str) -> Path:
        raw = self.directory(kind) / (prompt_asset_name(name) + ".json")
        require_regular_or_absent(raw, error_code="E_PROMPT_ASSET_NOT_REGULAR")
        path = self.models.path(str(raw))
        if not path.is_relative_to(self.directory(kind)):
            raise ValueError("E_PROMPT_ASSET_ESCAPE")
        if not path.is_file():
            raise FileNotFoundError(f"Prompt asset not found: {path}")
        return path

    def paths(self, kind: str) -> list[Path]:
        return [self.path(kind, item.stem) for item in sorted(self.directory(kind).glob("*.json"))]

    def read(self, path: Path) -> dict:
        return self.models.read(path)

    def content(self, path: Path) -> str:
        return self.models.path(str(path)).read_text(encoding="utf-8")

    def write(self, path: Path, payload: dict) -> None:
        require_regular_or_absent(path, error_code="E_PROMPT_ASSET_NOT_REGULAR")
        self.models.write(path, payload)

    @staticmethod
    def read_report(path: Path) -> dict:
        if not path.is_absolute():
            raise ValueError("E_PROMPT_REPORT_ABSOLUTE_REQUIRED")
        payload = json.loads(path.read_bytes())
        if not isinstance(payload, dict):
            raise ValueError("Promotion report must be a JSON object")
        return payload
