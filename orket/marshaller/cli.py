from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Sequence

from .promotion import promote_run
from .replay import replay_run
from .runner import MarshallerRunner


async def execute_marshaller_from_files(
    *,
    workspace_root: Path,
    run_request_path: Path,
    proposal_paths: Sequence[Path],
    run_id: str,
    allowed_paths: Sequence[str] = (),
    promote: bool = False,
    actor_id: str | None = None,
    actor_source: str = "cli",
    branch: str = "main",
) -> dict[str, Any]:
    run_request = await _read_json(run_request_path)
    proposals = [await _read_json(path) for path in proposal_paths]
    outcome = await MarshallerRunner(workspace_root).execute(
        run_id=run_id,
        run_request_payload=run_request,
        proposal_payloads=proposals,
        allowed_paths=tuple(allowed_paths),
    )
    run_path = Path(outcome.run_path)
    replay = await replay_run(run_path)

    result: dict[str, Any] = {
        "run_id": outcome.run_id,
        "accept": outcome.accept,
        "attempt_count": outcome.attempt_count,
        "accepted_attempt_index": outcome.accepted_attempt_index,
        "run_path": outcome.run_path,
        "summary_path": outcome.summary_path,
        "decision_path": outcome.decision_path,
        "run_root_digest": outcome.run_root_digest,
        "replay_result": replay,
    }
    if promote and outcome.accept:
        promotion = await promote_run(
            run_path,
            actor_id=_resolve_actor_id(actor_id),
            actor_source=actor_source,
            branch=branch,
        )
        result["promotion"] = promotion
    return result


async def list_marshaller_runs(workspace_root: Path, *, limit: int = 20) -> list[dict[str, Any]]:
    runs_root = _runs_root(workspace_root)
    if not await asyncio.to_thread(runs_root.exists):
        return []
    run_dirs = await asyncio.to_thread(
        lambda: sorted([p for p in runs_root.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True)
    )
    rows: list[dict[str, Any]] = []
    for run_dir in run_dirs[: max(1, int(limit))]:
        summary_path = run_dir / "summary.json"
        summary = await _read_json(summary_path) if await asyncio.to_thread(summary_path.exists) else {}
        rows.append(
            {
                "run_id": run_dir.name,
                "run_path": str(run_dir),
                "accepted": bool(summary.get("accepted", False)),
                "attempt_count": int(summary.get("attempt_count", 0) or 0),
                "accepted_attempt_index": summary.get("accepted_attempt_index"),
                "run_root_digest": str(summary.get("run_root_digest", "")),
            }
        )
    return rows


async def inspect_marshaller_attempt(
    workspace_root: Path,
    *,
    run_id: str,
    attempt_index: int | None = None,
) -> dict[str, Any]:
    run_path = _runs_root(workspace_root) / str(run_id).strip()
    if not await asyncio.to_thread(run_path.exists):
        raise ValueError(f"Run not found: {run_id}")
    selected_attempt = await _resolve_attempt_index(run_path, attempt_index)
    attempt_dir = run_path / "attempts" / str(selected_attempt)
    checks_dir = attempt_dir / "checks"
    check_files = (
        await asyncio.to_thread(
            lambda: sorted([p for p in checks_dir.glob("*.json") if p.is_file()], key=lambda p: p.name)
        )
        if await asyncio.to_thread(checks_dir.exists)
        else []
    )
    checks = {path.stem: await _read_json(path) for path in check_files}
    return {
        "run_id": run_id,
        "run_path": str(run_path),
        "attempt_index": selected_attempt,
        "proposal": await _read_json(attempt_dir / "proposal.json"),
        "decision": await _read_json(attempt_dir / "decision.json"),
        "metrics": await _read_json(attempt_dir / "metrics.json"),
        "apply_result": await _read_json(attempt_dir / "apply_result.json"),
        "checks": checks,
    }


def default_run_id() -> str:
    from datetime import UTC, datetime

    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"marshaller-{stamp}"


async def _read_json(path: Path) -> dict[str, Any]:
    text = await asyncio.to_thread(path.read_text, "utf-8")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object in {path}")
    return payload


async def _resolve_attempt_index(run_path: Path, attempt_index: int | None) -> int:
    if isinstance(attempt_index, int) and attempt_index >= 1:
        return attempt_index
    summary_path = run_path / "summary.json"
    if await asyncio.to_thread(summary_path.exists):
        summary = await _read_json(summary_path)
        accepted = summary.get("accepted_attempt_index")
        if isinstance(accepted, int) and accepted >= 1:
            return accepted
    attempts_root = run_path / "attempts"
    names = (
        await asyncio.to_thread(lambda: [p.name for p in attempts_root.iterdir() if p.is_dir()])
        if await asyncio.to_thread(attempts_root.exists)
        else []
    )
    numeric = sorted(int(name) for name in names if name.isdigit())
    if not numeric:
        raise ValueError(f"No attempts found under {attempts_root}")
    return numeric[-1]


def _runs_root(workspace_root: Path) -> Path:
    return workspace_root / "workspace" / "default" / "stabilizer" / "run"


def _resolve_actor_id(actor_id: str | None) -> str:
    value = (actor_id or "").strip()
    if value:
        return value
    return os.environ.get("GIT_AUTHOR_NAME") or os.environ.get("USERNAME") or os.environ.get("USER") or "unknown"
