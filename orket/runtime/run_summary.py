from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles

from orket.naming import sanitize_name

_EXCLUDED_ARTIFACT_IDS = {"gitea_export", "run_summary", "run_summary_path"}


def validate_run_summary_payload(payload: dict[str, Any]) -> None:
    run_id = str(payload.get("run_id") or "").strip()
    status = str(payload.get("status") or "").strip()
    duration_ms = payload.get("duration_ms")
    failure_reason = payload.get("failure_reason")
    tools_used = payload.get("tools_used")
    artifact_ids = payload.get("artifact_ids")

    if not run_id:
        raise ValueError("run_summary_run_id_required")
    if not status:
        raise ValueError("run_summary_status_required")
    if duration_ms is not None and (not isinstance(duration_ms, int) or duration_ms < 0):
        raise ValueError("run_summary_duration_invalid")
    if failure_reason is not None and not isinstance(failure_reason, str):
        raise ValueError("run_summary_failure_reason_invalid")
    _validate_token_list(tools_used, field_name="tools_used")
    _validate_token_list(artifact_ids, field_name="artifact_ids")


def build_run_summary_payload(
    *,
    run_id: str,
    status: str,
    failure_reason: str | None,
    started_at: str | None,
    ended_at: str | None,
    tool_names: list[str],
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    duration_ms = _resolve_duration_ms(started_at=started_at, ended_at=ended_at)
    payload = {
        "run_id": str(run_id).strip(),
        "status": str(status).strip(),
        "duration_ms": duration_ms,
        "tools_used": _normalize_token_list(tool_names),
        "artifact_ids": _artifact_ids(artifacts),
        "failure_reason": _normalize_failure_reason(failure_reason),
    }
    validate_run_summary_payload(payload)
    return payload


def build_degraded_run_summary_payload(
    *,
    run_id: str,
    status: str,
    failure_reason: str | None,
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "run_id": str(run_id).strip(),
        "status": str(status).strip(),
        "duration_ms": None,
        "tools_used": [],
        "artifact_ids": _artifact_ids(artifacts),
        "failure_reason": _normalize_failure_reason(failure_reason),
    }
    validate_run_summary_payload(payload)
    return payload


async def generate_run_summary_for_finalize(
    *,
    workspace: Path,
    run_id: str,
    status: str,
    failure_reason: str | None,
    started_at: str | None,
    ended_at: str | None,
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    tool_names = await _tool_names_from_receipts(workspace=workspace, run_id=run_id)
    return build_run_summary_payload(
        run_id=run_id,
        status=status,
        failure_reason=failure_reason,
        started_at=started_at,
        ended_at=ended_at,
        tool_names=tool_names,
        artifacts=artifacts,
    )


def reconstruct_run_summary(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    ordered_events = sorted(
        [dict(event or {}) for event in events if isinstance(event, dict)],
        key=lambda event: (
            int(event.get("event_seq") or event.get("sequence_number") or 0),
            str(event.get("kind") or ""),
        ),
    )
    run_id = str(session_id or "").strip()
    artifacts: dict[str, Any] = {}
    tool_names: list[str] = []
    started_at: str | None = None
    ended_at: str | None = None
    status = ""
    failure_reason: str | None = None

    for event in ordered_events:
        kind = str(event.get("kind") or "").strip()
        if not run_id:
            run_id = str(event.get("run_id") or event.get("session_id") or "").strip()
        event_artifacts = event.get("artifacts")
        if isinstance(event_artifacts, dict):
            artifacts.update(dict(event_artifacts))
        run_identity = artifacts.get("run_identity")
        if isinstance(run_identity, dict) and not started_at:
            identity_start = str(run_identity.get("start_time") or "").strip()
            if identity_start:
                started_at = identity_start
        if kind == "run_started" and not started_at:
            started_at = str(event.get("timestamp") or "").strip() or None
            continue
        if kind == "tool_call":
            tool_name = str(event.get("tool_name") or event.get("tool") or "").strip()
            if tool_name:
                tool_names.append(tool_name)
            continue
        if kind != "run_finalized":
            continue
        status = str(event.get("status") or status).strip()
        normalized_failure_reason = _normalize_failure_reason(event.get("failure_reason"))
        if normalized_failure_reason is not None:
            failure_reason = normalized_failure_reason
        ended_at = str(event.get("timestamp") or "").strip() or ended_at

    if not run_id:
        raise ValueError("run_summary_run_id_required")
    if not status:
        raise ValueError("run_summary_status_required")
    return build_run_summary_payload(
        run_id=run_id,
        status=status,
        failure_reason=failure_reason,
        started_at=started_at,
        ended_at=ended_at,
        tool_names=tool_names,
        artifacts=artifacts,
    )


async def write_run_summary_artifact(
    *,
    root: Path,
    session_id: str,
    payload: dict[str, Any],
) -> Path:
    validate_run_summary_payload(payload)
    run_summary_path = Path(root) / "runs" / str(session_id).strip() / "run_summary.json"
    await asyncio.to_thread(run_summary_path.parent.mkdir, parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    async with aiofiles.open(run_summary_path, mode="w", encoding="utf-8") as handle:
        await handle.write(content)
    return run_summary_path


async def _tool_names_from_receipts(*, workspace: Path, run_id: str) -> list[str]:
    receipt_paths = await asyncio.to_thread(_receipt_paths, Path(workspace), str(run_id))
    tool_names: list[str] = []
    for path in receipt_paths:
        async with aiofiles.open(path, mode="r", encoding="utf-8") as handle:
            async for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                payload = json.loads(stripped)
                if not isinstance(payload, dict):
                    continue
                tool_name = str(payload.get("tool") or payload.get("tool_name") or "").strip()
                if tool_name:
                    tool_names.append(tool_name)
    return _normalize_token_list(tool_names)


def _receipt_paths(workspace: Path, run_id: str) -> list[Path]:
    session_root = workspace / "observability" / sanitize_name(run_id)
    if not session_root.exists():
        return []
    paths: list[Path] = []
    for issue_dir in sorted(session_root.iterdir(), key=lambda path: path.name):
        if not issue_dir.is_dir():
            continue
        for turn_dir in sorted(issue_dir.iterdir(), key=lambda path: path.name):
            if not turn_dir.is_dir():
                continue
            candidate = turn_dir / "protocol_receipts.log"
            if candidate.exists():
                paths.append(candidate)
    return paths


def _artifact_ids(artifacts: dict[str, Any]) -> list[str]:
    rows = []
    for artifact_id in sorted(artifacts.keys()):
        normalized_id = str(artifact_id or "").strip()
        if not normalized_id or normalized_id in _EXCLUDED_ARTIFACT_IDS:
            continue
        artifact_value = artifacts.get(artifact_id)
        if not isinstance(artifact_value, (dict, list)):
            continue
        rows.append(normalized_id)
    return rows


def _resolve_duration_ms(*, started_at: str | None, ended_at: str | None) -> int:
    normalized_start = str(started_at or "").strip()
    normalized_end = str(ended_at or "").strip()
    if not normalized_start or not normalized_end:
        raise ValueError("run_summary_duration_missing")
    start_dt = datetime.fromisoformat(normalized_start)
    end_dt = datetime.fromisoformat(normalized_end)
    delta_ms = int((end_dt - start_dt).total_seconds() * 1000)
    if delta_ms < 0:
        raise ValueError("run_summary_duration_negative")
    return delta_ms


def _normalize_failure_reason(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _normalize_token_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for raw in values:
        token = str(raw or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        rows.append(token)
    rows.sort()
    return rows


def _validate_token_list(value: Any, *, field_name: str) -> None:
    if not isinstance(value, list):
        raise ValueError(f"run_summary_{field_name}_invalid")
    normalized = _normalize_token_list([str(item) for item in value])
    if normalized != value:
        raise ValueError(f"run_summary_{field_name}_not_canonical")
