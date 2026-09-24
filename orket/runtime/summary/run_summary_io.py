"""Owned native file operations used by run-summary publication."""
from __future__ import annotations

import json
from functools import partial
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.async_file_tools import capture_file_roots
from orket.naming import sanitize_name


async def _read_run_summary_tool_names(*, workspace: Path, run_id: str) -> list[str]:
    captured_workspace, = capture_file_roots([workspace])
    captured_run_id = str(run_id)
    receipt_paths = await run_owned_thread(
        partial(_receipt_paths, captured_workspace, captured_run_id),
        label="run-summary-receipt-discovery",
    )
    tool_names: list[str] = []
    for path in receipt_paths:
        content = await run_owned_thread(
            partial(path.read_text, encoding="utf-8"),
            label="run-summary-receipt-read",
        )
        for line in content.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, dict):
                continue
            tool_name = str(payload.get("tool") or payload.get("tool_name") or "").strip()
            if tool_name:
                tool_names.append(tool_name)
    return tool_names


async def _publish_run_summary_content(*, path: Path, content: str) -> None:
    await run_owned_thread(
        partial(_write_run_summary_content, path, str(content)),
        label="run-summary-publication",
    )


def _write_run_summary_content(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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
