from __future__ import annotations

import json
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any

from .models import CONTRACT_STYLE_LEGACY, ExtensionRecord, WorkloadRecord


class ExtensionCatalog:
    """Catalog persistence and entrypoint discovery for extension metadata."""

    def __init__(self, catalog_path: Path) -> None:
        self.catalog_path = catalog_path

    def list_extensions(self, entry_point_rows: list[dict[str, Any]] | None = None) -> list[ExtensionRecord]:
        payload = self.load_catalog_payload()
        rows = list(payload.get("extensions", []))
        if entry_point_rows:
            rows.extend(entry_point_rows)

        records: list[ExtensionRecord] = []
        seen_ids: set[str] = set()
        for row in rows:
            extension_id = str(row.get("extension_id", "")).strip()
            extension_version = str(row.get("extension_version", "")).strip() or "0.0.0"
            source = str(row.get("source", "")).strip() or "unknown"
            extension_api_version = str(row.get("extension_api_version", "")).strip() or "1.0.0"
            path = str(row.get("path", "")).strip()
            module = str(row.get("module", "")).strip()
            register_callable = str(row.get("register_callable", "")).strip() or "register"
            contract_style = str(row.get("contract_style", "")).strip() or CONTRACT_STYLE_LEGACY
            manifest_path = str(row.get("manifest_path", "")).strip()
            if not extension_id or extension_id in seen_ids:
                continue
            seen_ids.add(extension_id)

            workloads: list[WorkloadRecord] = []
            for item in row.get("workloads", []):
                workload_id = str(item.get("workload_id", "")).strip()
                if not workload_id:
                    continue
                required_capabilities = tuple(
                    str(cap).strip() for cap in item.get("required_capabilities", []) if str(cap).strip()
                )
                workloads.append(
                    WorkloadRecord(
                        workload_id=workload_id,
                        workload_version=str(item.get("workload_version", "")).strip() or "0.0.0",
                        entrypoint=str(item.get("entrypoint", "")).strip(),
                        required_capabilities=required_capabilities,
                        contract_style=str(item.get("contract_style", "")).strip() or contract_style,
                    )
                )

            records.append(
                ExtensionRecord(
                    extension_id=extension_id,
                    extension_version=extension_version,
                    source=source,
                    extension_api_version=extension_api_version,
                    path=path,
                    module=module,
                    register_callable=register_callable,
                    workloads=tuple(workloads),
                    contract_style=contract_style,
                    manifest_path=manifest_path,
                )
            )
        return records

    def resolve_workload(
        self, workload_id: str, entry_point_rows: list[dict[str, Any]] | None = None
    ) -> tuple[ExtensionRecord, WorkloadRecord] | None:
        target = str(workload_id or "").strip()
        if not target:
            return None
        for extension in self.list_extensions(entry_point_rows=entry_point_rows):
            for workload in extension.workloads:
                if workload.workload_id == target:
                    return extension, workload
        return None

    def load_catalog_payload(self) -> dict[str, Any]:
        if not self.catalog_path.exists():
            return {"extensions": []}
        data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"extensions": []}
        extensions = data.get("extensions", [])
        if not isinstance(extensions, list):
            return {"extensions": []}
        return {"extensions": extensions}

    def save_catalog_payload(self, payload: dict[str, Any]) -> None:
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self.catalog_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def row_from_record(record: ExtensionRecord) -> dict[str, Any]:
        return {
            "extension_id": record.extension_id,
            "extension_version": record.extension_version,
            "extension_api_version": record.extension_api_version,
            "source": record.source,
            "path": record.path,
            "module": record.module,
            "register_callable": record.register_callable,
            "contract_style": record.contract_style,
            "manifest_path": record.manifest_path,
            "workloads": [
                {
                    "workload_id": workload.workload_id,
                    "workload_version": workload.workload_version,
                    "entrypoint": workload.entrypoint,
                    "required_capabilities": list(workload.required_capabilities),
                    "contract_style": workload.contract_style,
                }
                for workload in record.workloads
            ],
        }

    @staticmethod
    def discover_entry_point_rows() -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            group = entry_points().select(group="orket.extensions")
        except (AttributeError, TypeError):
            return rows

        for ep in group:
            try:
                loader = ep.load()
                if not callable(loader):
                    continue
                descriptor = loader()
                if not isinstance(descriptor, dict):
                    continue
                if "source" not in descriptor:
                    descriptor["source"] = f"entrypoint:{ep.name}"
                if "register_callable" not in descriptor:
                    descriptor["register_callable"] = "register"
                rows.append(descriptor)
            except (ImportError, AttributeError, TypeError, ValueError):
                continue
        return rows
