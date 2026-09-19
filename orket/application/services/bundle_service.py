"""Application authority for bundle admission, packing and inspection."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from orket.adapters.storage.bundle_store import BundleManifestSource, BundleSourceChangedError, BundleStore
from orket.application.services import bundle_policy as policy
from orket.core.domain.orket_manifest import OrketManifest


class BundleService:
    def __init__(self, *, store: BundleStore | None = None, engine_version: str = "") -> None:
        self.store = store if store is not None else BundleStore()
        self.engine_version = engine_version.strip()

    async def validate(self, target: Path, *, available_models: list[str] | None = None,
                       model_override: str = "") -> dict[str, Any]:
        store, version = self.store, self.engine_version
        models = tuple(available_models) if available_models is not None else None
        result, _, _ = await _validate(store, target, version, models, model_override)
        return result

    async def pack(self, source: Path, *, out_path: Path | None = None) -> dict[str, Any]:
        store, version = self.store, self.engine_version
        if await store.target_kind(source) != "directory":
            return policy.error_result(source, "E_PACK_SOURCE_NOT_DIRECTORY", "source",
                                       "Pack source must be a directory containing an Orket manifest and assets.")
        validation, captured, manifest = await _validate(store, source, version, None, "")
        if not validation["ok"]:
            result = policy.error_result(source, "E_PACK_VALIDATE_FAILED", "bundle",
                                         "Bundle must pass 'orket validate' before packing.")
            result["validation"] = validation
            return result
        assert captured is not None and manifest is not None
        destination = out_path if out_path is not None else Path(f"{manifest.metadata.name}-{manifest.metadata.version}.orket")
        try:
            required = tuple(row[0] for row in policy.references(manifest, archive=True))
            destination, count = await store.pack(captured, destination, required)
        except BundleSourceChangedError as exc:
            return policy.error_result(source, "E_PACK_SOURCE_CHANGED", "manifest", str(exc))
        except ValueError as exc:
            return policy.error_result(source, "E_PACK_UNSAFE_ARCHIVE_PATH", "archive", str(exc))
        return {"ok": True, "source": str(source), "output": str(destination),
                "manifest_name": manifest.metadata.name, "manifest_version": manifest.metadata.version,
                "file_count": count, "error_count": 0, "errors": []}

    async def inspect(self, target: Path) -> dict[str, Any]:
        store, version = self.store, self.engine_version
        kind = await store.target_kind(target)
        if kind == "missing":
            return policy.error_result(target, "E_INSPECT_TARGET_NOT_FOUND", "target", f"Target not found: {target}")
        if kind == "file" and target.suffix.lower() == ".orket":
            return await _inspect_archive(store, target)
        validation, captured, manifest = await _validate(store, target, version, None, "")
        if not validation["ok"]:
            return validation
        assert captured is not None and manifest is not None
        return policy.inspect_summary(target, manifest, captured.path, None)


async def _validate(store: BundleStore, target: Path, version: str,
                    models: tuple[str, ...] | None, override: str
                    ) -> tuple[dict[str, Any], BundleManifestSource | None, OrketManifest | None]:
    try:
        captured = await store.read_manifest(target)
    except (UnicodeError, ValueError) as exc:
        return policy.error_result(target, "E_MANIFEST_PARSE", target.name, str(exc)), None, None
    if captured.path is None:
        return policy.error_result(target, "E_MANIFEST_NOT_FOUND", "manifest",
                                   "Manifest not found. Expected one of: orket.yaml, orket.yml, orket.json"), None, None
    try:
        payload = policy.parse_manifest(captured.path.suffix.lower(), (captured.content or b"").decode("utf-8"))
    except (ValueError, yaml.YAMLError) as exc:
        return policy.error_result(target, "E_MANIFEST_PARSE", captured.path.name, str(exc)), captured, None
    try:
        manifest = OrketManifest.model_validate(payload)
    except ValidationError as exc:
        rows = policy.schema_errors(exc)
        return {"ok": False, "target": str(target), "error_count": len(rows), "errors": rows}, captured, None
    existing = await store.existing_references(captured.root, tuple(row[0] for row in policy.references(manifest)))
    effective_version = version or await store.engine_version()
    result = policy.validate_values(manifest, target=target, manifest_path=captured.path, existing=existing,
                                    engine_version=effective_version, available_models=models, model_override=override)
    return result, captured, manifest


async def _inspect_archive(store: BundleStore, target: Path) -> dict[str, Any]:
    captured = await store.read_archive(target)
    if captured.manifest_name is None:
        return policy.error_result(target, "E_INSPECT_MANIFEST_NOT_FOUND", "archive",
                                   "Archive missing manifest: expected orket.yaml, orket.yml, or orket.json.")
    try:
        payload = policy.parse_manifest(Path(captured.manifest_name).suffix.lower(),
                                        (captured.manifest_bytes or b"").decode("utf-8"))
        manifest = OrketManifest.model_validate(payload)
    except (ValueError, yaml.YAMLError) as exc:
        return policy.error_result(target, "E_MANIFEST_PARSE", captured.manifest_name, str(exc))
    errors = policy.reference_errors(manifest, frozenset(captured.names), archive=True)
    if errors:
        return {"ok": False, "target": str(target), "error_count": len(errors), "errors": errors}
    return policy.inspect_summary(target, manifest, captured.manifest_name, len(captured.names))
