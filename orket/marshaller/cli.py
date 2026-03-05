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


def _resolve_actor_id(actor_id: str | None) -> str:
    value = (actor_id or "").strip()
    if value:
        return value
    return (
        os.environ.get("GIT_AUTHOR_NAME")
        or os.environ.get("USERNAME")
        or os.environ.get("USER")
        or "unknown"
    )

