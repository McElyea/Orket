"""Prompt metadata transitions over supplied values and an explicit calendar date."""
from __future__ import annotations

import re
from copy import deepcopy
from datetime import date
from types import MappingProxyType
from typing import Any

VALID_STATUSES = frozenset({"draft", "candidate", "canary", "stable", "deprecated"})
ALLOWED_STATUS_TRANSITIONS = MappingProxyType({
    "draft": frozenset({"candidate", "canary", "deprecated"}),
    "candidate": frozenset({"canary", "stable", "deprecated"}),
    "canary": frozenset({"stable", "deprecated"}),
    "stable": frozenset({"deprecated"}),
    "deprecated": frozenset(),
})


def prompt_asset_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
        raise ValueError("E_PROMPT_ASSET_NAME")
    return value


def parse_prompt_id(value: str) -> tuple[str, str]:
    kind, separator, name = str(value).strip().partition(".")
    if not separator or kind not in {"role", "dialect"}:
        raise ValueError(f"Unsupported prompt id format: {value}")
    return kind, prompt_asset_name(name)


def _promoted_status(metadata: dict[str, Any], target: str, report: dict[str, Any] | None) -> str:
    if target not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {target}")
    if report is not None and not isinstance(report, dict):
        raise ValueError("E_PROMPT_PROMOTION_REPORT_OBJECT")
    if isinstance(report, dict) and target in {"canary", "stable"} and report.get("pass") is not True:
        blockers = report.get("blockers", [])
        codes = [str(item.get("code") or "").strip() for item in blockers if isinstance(item, dict)] if isinstance(blockers, list) else []
        suffix = f" blockers={','.join(code for code in codes if code)}" if any(codes) else ""
        raise ValueError(f"Promotion criteria not met for {target}.{suffix}")
    current = str(metadata.get("status") or "").strip()
    allowed = ALLOWED_STATUS_TRANSITIONS.get(current, frozenset())
    if current and current != target and target not in allowed:
        raise ValueError(f"Invalid status transition: {current} -> {target}. Allowed: {sorted(allowed)}")
    return target


def _apply_mode(metadata: dict[str, Any], *, mode: str, version: str, status: str,
                notes: str, report: dict[str, Any] | None) -> str:
    old_version = str(metadata.get("version") or "").strip()
    if mode == "new":
        if not version.strip():
            raise ValueError("new requires --version")
        selected = str(status or "draft").strip()
        if selected not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {selected}")
        metadata["lineage"]["parent"] = old_version or None
        metadata.update(version=version.strip(), status=selected)
        return notes or "New prompt version created."
    if mode == "promote":
        target = _promoted_status(metadata, str(status or "stable").strip(), report)
        metadata["status"] = target
        return notes or f"Prompt promoted to {target}."
    if mode == "deprecate":
        metadata["status"] = "deprecated"
        return notes or "Prompt deprecated."
    raise ValueError(f"Unsupported update mode: {mode}")


def prepare_prompt_metadata(payload: dict[str, Any], *, prompt_id: str, mode: str, as_of: date,
                            version: str = "", status: str = "", notes: str = "",
                            promotion_report: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    parse_prompt_id(prompt_id)
    updated = deepcopy(payload)
    metadata = dict(updated.get("prompt_metadata") or {})
    if metadata.get("id") != prompt_id:
        raise ValueError("E_PROMPT_METADATA_ID_MISMATCH")
    before = {"version": str(metadata.get("version") or "").strip(), "status": str(metadata.get("status") or "").strip()}
    if not isinstance(metadata.get("lineage"), dict):
        metadata["lineage"] = {"parent": None}
    note = _apply_mode(metadata, mode=mode, version=version, status=status, notes=notes, report=promotion_report)
    metadata["updated_at"] = as_of.isoformat()
    if not isinstance(metadata.get("changelog"), list):
        metadata["changelog"] = []
    metadata["changelog"].append({"version": str(metadata.get("version") or "unknown"),
                                  "date": as_of.isoformat(), "notes": note})
    updated["prompt_metadata"] = metadata
    return updated, {"mode": mode, "before": before,
                     "after": {"version": metadata.get("version"), "status": metadata.get("status")},
                     "metadata": metadata}
