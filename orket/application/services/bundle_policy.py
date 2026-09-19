"""Bundle admission and rendering from explicitly supplied manifest/file facts."""
from __future__ import annotations

import json
from typing import Any

import yaml
from pydantic import ValidationError

from orket.core.domain.orket_manifest import OrketManifest, is_engine_compatible, resolve_model_selection


def error_result(target: object, code: str, location: str, message: str) -> dict[str, Any]:
    return {"ok": False, "target": str(target), "error_count": 1,
            "errors": [{"code": code, "location": location, "message": message}]}


def parse_manifest(suffix: str, text: str) -> dict[str, Any]:
    if suffix == ".json":
        raw = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        raw = yaml.safe_load(text)
    else:
        raise ValueError(f"Unsupported manifest extension: {suffix}")
    if not isinstance(raw, dict):
        raise ValueError("Manifest payload must be an object.")
    return raw


def schema_errors(exc: ValidationError) -> list[dict[str, str]]:
    rows = [{"code": "E_MANIFEST_SCHEMA", "location": ".".join(str(p) for p in item.get("loc", ())),
             "message": str(item.get("msg") or "schema violation")} for item in exc.errors()]
    return sorted(rows, key=lambda row: (row["location"], row["message"]))


def references(manifest: OrketManifest, *, archive: bool = False) -> tuple[tuple[str, str, str], ...]:
    state = manifest.stateMachine.file
    if archive:
        state = state.replace("\\", "/")
    rows = [(state, "E_STATE_MACHINE_MISSING", "stateMachine.file")]
    for agent in manifest.agents:
        rows.extend(((f"agents/{agent.name}.json", "E_AGENT_FILE_MISSING", f"agents.{agent.name}"),
                     (f"prompts/{agent.name}.md", "E_PROMPT_FILE_MISSING", f"prompts.{agent.name}")))
    rows.extend((f"guards/{guard.value}.json", "E_GUARD_FILE_MISSING", f"guards.{guard.value}")
                for guard in manifest.guards)
    return tuple(rows)


def reference_errors(manifest: OrketManifest, existing: frozenset[str], *, archive: bool = False):
    rows = [{"code": code, "location": location, "message": f"Missing referenced file: {name}"}
            for name, code, location in references(manifest, archive=archive) if name not in existing]
    return sorted(rows, key=lambda row: (row["code"], row["location"], row["message"]))


def validate_values(manifest: OrketManifest, *, target: object, manifest_path: object,
                    existing: frozenset[str], engine_version: str,
                    available_models: tuple[str, ...] | None, model_override: str) -> dict[str, Any]:
    rows = reference_errors(manifest, existing)
    if not is_engine_compatible(manifest, engine_version):
        rows.append({"code": "E_ENGINE_INCOMPATIBLE", "location": "metadata.engineVersion",
                     "message": f"Engine version {engine_version} does not satisfy "
                                f"manifest range {manifest.metadata.engineVersion}."})
    selection = None
    if available_models is not None or model_override.strip():
        selection = resolve_model_selection(manifest, available_models=list(available_models or ()),
                                            model_override=model_override)
        if not selection["ok"]:
            rows.append({"code": str(selection.get("code") or "E_MODEL_SELECTION"), "location": "model",
                         "message": str(selection.get("message") or "model selection failed")})
    rows.sort(key=lambda row: (row["code"], row["location"], row["message"]))
    result = {"ok": not rows, "target": str(target), "manifest_path": str(manifest_path),
              "manifest_name": manifest.metadata.name, "manifest_version": manifest.metadata.version,
              "engine_version_checked": engine_version, "error_count": len(rows), "errors": rows}
    if selection is not None:
        result["model_selection"] = selection
    return result


def inspect_summary(target: object, manifest: OrketManifest, manifest_path: object,
                    entry_count: int | None) -> dict[str, Any]:
    summary = {"ok": True, "target": str(target), "manifest_path": str(manifest_path),
               "name": manifest.metadata.name, "version": manifest.metadata.version,
               "engineVersion": manifest.metadata.engineVersion,
               "model": manifest.model.model_dump(),
               "permissions": {"filesystem_read_count": len(manifest.permissions.filesystem.read),
                               "filesystem_write_count": len(manifest.permissions.filesystem.write),
                               "network_allowed": bool(manifest.permissions.network.allowed),
                               "tools_allowed_count": len(manifest.permissions.tools.allowed)},
               "agents_count": len(manifest.agents), "guards": [guard.value for guard in manifest.guards],
               "error_count": 0, "errors": []}
    if entry_count is not None:
        summary["entry_count"] = entry_count
    return summary
