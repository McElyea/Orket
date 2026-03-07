from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from orket.application.workflows.protocol_hashing import hash_canonical_json


def capture_workspace_state_snapshot(
    *,
    workspace: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    resolved_workspace = workspace.resolve()
    inventory = _workspace_inventory(
        resolved_workspace,
        exclude_prefixes=("observability/",),
    )
    return {
        "workspace_path": str(resolved_workspace),
        "workspace_type": "filesystem",
        "workspace_hash": _inventory_hash(inventory),
        "file_count": len(inventory),
    }


def _workspace_inventory(
    workspace: Path,
    *,
    exclude_prefixes: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    if not workspace.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(workspace.rglob("*"), key=lambda entry: entry.as_posix()):
        if not path.is_file():
            continue
        rel_path = str(path.relative_to(workspace)).replace("\\", "/")
        if any(rel_path == prefix.rstrip("/") or rel_path.startswith(prefix) for prefix in exclude_prefixes):
            continue
        rows.append(
            {
                "path": rel_path,
                "sha256": _sha256_file(path),
                "size_bytes": int(path.stat().st_size),
            }
        )
    return rows


def _inventory_hash(rows: list[dict[str, Any]]) -> str:
    return hash_canonical_json(rows)


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()
