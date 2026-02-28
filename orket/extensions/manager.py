from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.runtime_paths import durable_root


def default_extensions_catalog_path() -> Path:
    env_path = (os.getenv("ORKET_EXTENSIONS_CATALOG") or "").strip()
    if env_path:
        return Path(env_path)
    return durable_root() / "config" / "extensions_catalog.json"


@dataclass(frozen=True)
class WorkloadRecord:
    workload_id: str
    workload_version: str


@dataclass(frozen=True)
class ExtensionRecord:
    extension_id: str
    extension_version: str
    source: str
    workloads: tuple[WorkloadRecord, ...]


class ExtensionManager:
    def __init__(self, catalog_path: Path | None = None):
        self.catalog_path = (catalog_path or default_extensions_catalog_path()).resolve()

    def list_extensions(self) -> list[ExtensionRecord]:
        payload = self._load_catalog_payload()
        records: list[ExtensionRecord] = []
        for row in payload.get("extensions", []):
            extension_id = str(row.get("extension_id", "")).strip()
            extension_version = str(row.get("extension_version", "")).strip() or "0.0.0"
            source = str(row.get("source", "")).strip() or "unknown"
            if not extension_id:
                continue

            workloads: list[WorkloadRecord] = []
            for item in row.get("workloads", []):
                workload_id = str(item.get("workload_id", "")).strip()
                if not workload_id:
                    continue
                workloads.append(
                    WorkloadRecord(
                        workload_id=workload_id,
                        workload_version=str(item.get("workload_version", "")).strip() or "0.0.0",
                    )
                )

            records.append(
                ExtensionRecord(
                    extension_id=extension_id,
                    extension_version=extension_version,
                    source=source,
                    workloads=tuple(workloads),
                )
            )
        return records

    def resolve_workload(self, workload_id: str) -> tuple[ExtensionRecord, WorkloadRecord] | None:
        target = str(workload_id or "").strip()
        if not target:
            return None
        for extension in self.list_extensions():
            for workload in extension.workloads:
                if workload.workload_id == target:
                    return extension, workload
        return None

    def _load_catalog_payload(self) -> dict[str, Any]:
        if not self.catalog_path.exists():
            return {"extensions": []}
        data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"extensions": []}
        extensions = data.get("extensions", [])
        if not isinstance(extensions, list):
            return {"extensions": []}
        return {"extensions": extensions}
