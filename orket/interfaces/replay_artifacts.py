from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict


def replay_recording_enabled() -> bool:
    raw = str(os.getenv("ORKET_REPLAY_ARTIFACTS", "0")).strip().lower()
    return raw not in {"0", "false", "off", "no"}


def write_replay_artifact(*, command_name: str, request: Dict[str, Any], result: Dict[str, Any], repo_root: Path) -> Path | None:
    if not replay_recording_enabled():
        return None

    payload: Dict[str, Any] = {
        "contract_version": "core_pillars/replay_artifact/v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "command": command_name,
        "request": request,
        "result": {
            "ok": bool(result.get("ok")),
            "code": str(result.get("code", "")),
            "message": str(result.get("message", "")),
        },
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    payload["artifact_id"] = digest

    out_dir = repo_root / ".orket" / "replay_artifacts" / command_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{digest}.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def write_refactor_parity_artifact(*, payload: Dict[str, Any], repo_root: Path) -> Path | None:
    if not replay_recording_enabled():
        return None

    normalized_payload = dict(payload)
    digest = hashlib.sha256(
        json.dumps(normalized_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    normalized_payload["artifact_id"] = digest

    out_dir = repo_root / ".orket" / "replay_artifacts" / "refactor_parity"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{digest}.json"
    out_path.write_text(json.dumps(normalized_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path
