from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.async_file_tools import capture_file_roots

from .artifacts import read_json_object
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
    workspace_root, run_request_path, *proposal_paths = capture_file_roots(
        [workspace_root, run_request_path, *proposal_paths])
    allowed_paths = tuple(allowed_paths)
    selected_actor = resolve_actor_id(actor_id) if promote else actor_id
    run_request = await read_json_object(run_request_path, error_location="in")
    proposals = [await read_json_object(path, error_location="in") for path in proposal_paths]
    outcome = await MarshallerRunner(workspace_root).execute(
        run_id=run_id,
        run_request_payload=run_request,
        proposal_payloads=proposals,
        allowed_paths=allowed_paths,
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
            actor_id=selected_actor,
            actor_source=actor_source,
            branch=branch,
        )
        result["promotion"] = promotion
    return result


async def list_marshaller_runs(workspace_root: Path, *, limit: int = 20) -> list[dict[str, Any]]:
    workspace_root, = capture_file_roots([workspace_root])
    runs_root = _runs_root(workspace_root)
    if not await run_owned_thread(runs_root.exists, label="marshaller-exists"):
        return []
    run_dirs = await run_owned_thread(
        lambda: sorted([p for p in runs_root.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True),
        label="marshaller-runs")
    rows: list[dict[str, Any]] = []
    for run_dir in run_dirs[: max(1, int(limit))]:
        summary_path = run_dir / "summary.json"
        summary = await read_json_object(summary_path, error_location="in") if await run_owned_thread(summary_path.exists, label="marshaller-exists") else {}
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
    workspace_root, = capture_file_roots([workspace_root])
    run_path = _runs_root(workspace_root) / str(run_id).strip()
    if not await run_owned_thread(run_path.exists, label="marshaller-exists"):
        raise ValueError(f"Run not found: {run_id}")
    selected_attempt = await _resolve_attempt_index(run_path, attempt_index)
    attempt_dir = run_path / "attempts" / str(selected_attempt)
    checks_dir = attempt_dir / "checks"
    check_files = (
        await run_owned_thread(
            lambda: sorted([p for p in checks_dir.glob("*.json") if p.is_file()], key=lambda p: p.name),
            label="marshaller-checks")
        if await run_owned_thread(checks_dir.exists, label="marshaller-exists")
        else []
    )
    checks = {path.stem: await read_json_object(path, error_location="in") for path in check_files}
    return {
        "run_id": run_id,
        "run_path": str(run_path),
        "attempt_index": selected_attempt,
        "proposal": await read_json_object(attempt_dir / "proposal.json", error_location="in"),
        "decision": await read_json_object(attempt_dir / "decision.json", error_location="in"),
        "metrics": await read_json_object(attempt_dir / "metrics.json", error_location="in"),
        "apply_result": await read_json_object(attempt_dir / "apply_result.json", error_location="in"),
        "checks": checks,
    }


def default_run_id() -> str:
    from datetime import UTC, datetime

    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"marshaller-{stamp}"


async def _resolve_attempt_index(run_path: Path, attempt_index: int | None) -> int:
    if isinstance(attempt_index, int) and attempt_index >= 1:
        return attempt_index
    summary_path = run_path / "summary.json"
    if await run_owned_thread(summary_path.exists, label="marshaller-exists"):
        summary = await read_json_object(summary_path, error_location="in")
        accepted = summary.get("accepted_attempt_index")
        if isinstance(accepted, int) and accepted >= 1:
            return accepted
    attempts_root = run_path / "attempts"
    names = (
        await run_owned_thread(lambda: [p.name for p in attempts_root.iterdir() if p.is_dir()], label="marshaller-attempts")
        if await run_owned_thread(attempts_root.exists, label="marshaller-exists")
        else []
    )
    numeric = sorted(int(name) for name in names if name.isdigit())
    if not numeric:
        raise ValueError(f"No attempts found under {attempts_root}")
    return numeric[-1]


def _runs_root(workspace_root: Path) -> Path:
    return workspace_root / "workspace" / "default" / "stabilizer" / "run"


def resolve_actor_id(actor_id: str | None) -> str:
    value = (actor_id or "").strip()
    if value:
        return value
    return os.environ.get("GIT_AUTHOR_NAME") or os.environ.get("USERNAME") or os.environ.get("USER") or "unknown"
