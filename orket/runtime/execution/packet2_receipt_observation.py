"""Own packet-2 receipt and artifact metadata observation through interruption."""
from __future__ import annotations

import hashlib
import json
from functools import partial
from pathlib import Path
from typing import Any, Literal

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.async_file_tools import capture_file_roots
from orket.naming import sanitize_name

FileObservation = Literal["outside", "missing", "present"]


async def observe_packet2_receipts(*, workspace: Path, run_id: str) -> list[dict[str, Any]]:
    """Capture the lexical root and retain discovery, reads and closes as one operation."""
    workspace, = capture_file_roots([workspace])
    captured_run_id = str(run_id)
    return await run_owned_thread(
        partial(_load_receipts, workspace=workspace, run_id=captured_run_id),
        label="packet2-receipt-observation",
    )


async def observe_packet2_file(*, workspace: Path, raw_path: str) -> FileObservation:
    """Observe only whether a contained candidate is an existing regular file."""
    workspace, = capture_file_roots([workspace])
    captured_path = str(raw_path)
    return await run_owned_thread(
        partial(_observe_file, workspace=workspace, raw_path=captured_path),
        label="packet2-file-audit",
    )


def _load_receipts(*, workspace: Path, run_id: str) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    observability_root = workspace / "observability" / sanitize_name(run_id)
    if not observability_root.exists():
        return receipts
    protocol_turn_dirs: set[Path] = set()
    for receipt_path in sorted(observability_root.rglob("protocol_receipts.log")):
        protocol_turn_dirs.add(receipt_path.parent.resolve())
        receipts.extend(_read_protocol_receipt(receipt_path, run_id=run_id, workspace=workspace))
    for turn_dir in _legacy_turn_dirs(
        observability_root=observability_root,
        protocol_turn_dirs=protocol_turn_dirs,
    ):
        receipts.extend(_read_legacy_turn(turn_dir, run_id=run_id, workspace=workspace))
    return sorted(
        receipts,
        key=lambda row: (
            str(row.get("_issue_id") or ""),
            _normalize_turn_index(row.get("_turn_index")),
            int(row.get("receipt_seq") or row.get("tool_index") or 0),
            str(row.get("operation_id") or ""),
        ),
    )


def _read_protocol_receipt(receipt_path: Path, *, run_id: str, workspace: Path) -> list[dict[str, Any]]:
    issue_id, role_name, turn_index = _receipt_context(
        receipt_path=receipt_path,
        run_id=run_id,
        workspace=workspace,
    )
    receipts: list[dict[str, Any]] = []
    try:
        with receipt_path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if isinstance(payload, dict):
                    receipts.append(
                        {
                            **payload,
                            "_issue_id": issue_id,
                            "_role_name": role_name,
                            "_turn_index": turn_index,
                        }
                    )
    except OSError:
        return receipts
    return receipts


def _legacy_turn_dirs(*, observability_root: Path, protocol_turn_dirs: set[Path]) -> list[Path]:
    turn_dirs: list[Path] = []
    for issue_dir in sorted(observability_root.iterdir(), key=lambda path: path.name):
        if not issue_dir.is_dir():
            continue
        for turn_dir in sorted(issue_dir.iterdir(), key=lambda path: path.name):
            if not turn_dir.is_dir():
                continue
            if (turn_dir.resolve() in protocol_turn_dirs) or ("_" not in turn_dir.name):
                continue
            if (turn_dir / "parsed_tool_calls.json").exists():
                turn_dirs.append(turn_dir)
    return turn_dirs


def _read_legacy_turn(turn_dir: Path, *, run_id: str, workspace: Path) -> list[dict[str, Any]]:
    issue_id, role_name, turn_index = _receipt_context(
        receipt_path=turn_dir / "protocol_receipts.log",
        run_id=run_id,
        workspace=workspace,
    )
    if not issue_id or turn_index <= 0:
        return []
    parsed_tool_calls = _load_json_payload(turn_dir / "parsed_tool_calls.json")
    if not isinstance(parsed_tool_calls, list):
        return []
    receipts: list[dict[str, Any]] = []
    for tool_index, item in enumerate(parsed_tool_calls):
        receipt = _legacy_receipt(
            item=item,
            tool_index=tool_index,
            turn_dir=turn_dir,
            run_id=run_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
        )
        if receipt is not None:
            receipts.append(receipt)
    return receipts


def _legacy_receipt(
    *, item: Any, tool_index: int, turn_dir: Path, run_id: str,
    issue_id: str, role_name: str, turn_index: int,
) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    tool_name = str(item.get("tool") or "").strip()
    if not tool_name:
        return None
    tool_args = dict(item.get("args") or {}) if isinstance(item.get("args"), dict) else {}
    replay_key = _legacy_tool_replay_key(tool_name, tool_args)
    execution_result = _load_json_payload(
        turn_dir / f"tool_result_{sanitize_name(tool_name)}_{replay_key}.json"
    )
    if not isinstance(execution_result, dict):
        return None
    return {
        "run_id": run_id,
        "step_id": f"{issue_id}:{turn_index}",
        "receipt_seq": tool_index + 1,
        "operation_id": _legacy_operation_id(
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            tool_index=tool_index,
            tool_name=tool_name,
            tool_args=tool_args,
        ),
        "tool_index": tool_index,
        "tool": tool_name,
        "tool_args": tool_args,
        "execution_result": execution_result,
        "_issue_id": issue_id,
        "_role_name": role_name,
        "_turn_index": turn_index,
    }


def _load_json_payload(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, TypeError, ValueError):
        return None


def _legacy_tool_replay_key(tool_name: str, tool_args: dict[str, Any]) -> str:
    payload = {
        "v": 1,
        "kind": "tool_replay_key",
        "fields": [str(tool_name or ""), dict(tool_args or {})],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _legacy_operation_id(
    *, issue_id: str, role_name: str, turn_index: int, tool_index: int,
    tool_name: str, tool_args: dict[str, Any],
) -> str:
    return (
        "legacy:"
        f"{sanitize_name(issue_id)}:"
        f"{sanitize_name(role_name)}:"
        f"{turn_index:03d}:"
        f"{tool_index:03d}:"
        f"{sanitize_name(tool_name)}:"
        f"{_legacy_tool_replay_key(tool_name, tool_args)}"
    )


def _receipt_context(*, receipt_path: Path, run_id: str, workspace: Path) -> tuple[str, str, int]:
    session_root = workspace / "observability" / sanitize_name(run_id)
    try:
        relative_path = receipt_path.relative_to(session_root)
    except ValueError:
        return "", "", 0
    parts = relative_path.parts
    if len(parts) < 3:
        return "", "", 0
    issue_id = str(parts[0]).strip()
    role_token = str(parts[1]).strip()
    turn_index = 0
    role_name = ""
    if "_" in role_token:
        raw_turn_index, role_name = role_token.split("_", 1)
        turn_index = _normalize_turn_index(raw_turn_index)
    return issue_id, role_name.strip(), turn_index


def _observe_file(*, workspace: Path, raw_path: str) -> FileObservation:
    candidate = Path(raw_path)
    workspace_root = workspace.resolve()
    if not candidate.is_absolute():
        candidate = workspace_root / candidate
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(workspace_root):
        return "outside"
    if not resolved.exists() or not resolved.is_file():
        return "missing"
    return "present"


def _normalize_turn_index(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    raw = str(value or "").strip()
    if not raw:
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return 0
