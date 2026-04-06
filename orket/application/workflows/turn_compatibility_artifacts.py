from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def append_compatibility_artifacts(
    *,
    turn_output_dir: Path,
    operation_id: str,
    translation: dict[str, Any],
) -> None:
    turn_output_dir.mkdir(parents=True, exist_ok=True)
    _append_compat_translation(
        out_path=turn_output_dir / "compat_translation.json",
        operation_id=operation_id,
        translation=translation,
    )
    _append_compat_latency_profile(
        out_path=turn_output_dir / "compat_latency_profile.json",
        operation_id=operation_id,
        translation=translation,
    )


def _append_compat_translation(
    *,
    out_path: Path,
    operation_id: str,
    translation: dict[str, Any],
) -> None:
    schema_version = "1.0"
    translations: list[dict[str, Any]] = []
    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        if isinstance(existing, dict):
            rows = existing.get("translations")
            schema_version = str(existing.get("schema_version") or "1.0")
            if isinstance(rows, list):
                translations = [dict(row) for row in rows if isinstance(row, dict)]
    row = dict(translation)
    row["operation_id"] = str(operation_id or "")
    translations.append(row)
    payload = {"schema_version": schema_version, "translations": translations}
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_compat_latency_profile(
    *,
    out_path: Path,
    operation_id: str,
    translation: dict[str, Any],
) -> None:
    latency_ms = translation.get("latency_ms")
    if not isinstance(latency_ms, (int, float)):
        return
    compat_tool_name = str(translation.get("compat_tool_name") or "").strip()
    if not compat_tool_name:
        return
    mapped_core_tools = translation.get("mapped_core_tools")
    mapped_core_tools = mapped_core_tools if isinstance(mapped_core_tools, list) else []
    profile: dict[str, Any] = {
        "compat_tool": compat_tool_name,
        "core_tools_used": [str(token).strip() for token in mapped_core_tools if str(token).strip()],
        "latency_ms": int(latency_ms),
        "mapping_version": translation.get("mapping_version"),
        "operation_id": str(operation_id or ""),
    }
    schema_version = "1.0"
    profiles: list[dict[str, Any]] = []
    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        if isinstance(existing, dict):
            rows = existing.get("profiles")
            schema_version = str(existing.get("schema_version") or "1.0")
            if isinstance(rows, list):
                profiles = [dict(row) for row in rows if isinstance(row, dict)]
    profiles.append(profile)
    payload = {"schema_version": schema_version, "profiles": profiles}
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
