from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from .ledger import LedgerWriter
from .process import run_process


def _resolve_repo_path(run_payload: dict[str, Any]) -> Path:
    return Path(str(((run_payload.get("request") or {}).get("repo_path")) or "")).resolve()


async def promote_run(
    run_path: Path,
    *,
    actor_id: str,
    actor_source: str,
    branch: str = "main",
    attempt_index: int | None = None,
) -> dict[str, Any]:
    """
    Human-triggered promotion for a single accepted attempt.

    Reads run artifacts, applies the accepted patch to canonical repo, commits,
    writes `promotion.json`, and appends `promotion_event` to ledger.
    """

    run_payload = await _read_json(run_path / "run.json")
    selected_attempt = await _resolve_attempt_index(run_path, attempt_index)
    decision = await _read_json(run_path / "attempts" / str(selected_attempt) / "decision.json")
    if not bool(decision.get("accept")):
        raise ValueError("Cannot promote a rejected attempt")

    patch_path = run_path / "attempts" / str(selected_attempt) / "patch.diff"
    repo_path = await asyncio.to_thread(_resolve_repo_path, run_payload)
    if not await asyncio.to_thread(repo_path.exists):
        raise ValueError(f"Repository path does not exist: {repo_path}")

    checkout = await run_process(("git", "checkout", branch), cwd=repo_path)
    if checkout.returncode != 0:
        raise RuntimeError(f"Failed to checkout branch '{branch}': {checkout.stderr.strip()}")

    apply_result = await run_process(("git", "apply", str(patch_path)), cwd=repo_path)
    if apply_result.returncode != 0:
        raise RuntimeError(f"Failed to apply patch during promotion: {apply_result.stderr.strip()}")

    add_result = await run_process(("git", "add", "-A"), cwd=repo_path)
    if add_result.returncode != 0:
        raise RuntimeError(f"Failed to stage promotion changes: {add_result.stderr.strip()}")

    run_id = str(run_payload.get("run_id") or run_path.name)
    commit_message = f"marshaller promote {run_id} attempt {selected_attempt}"
    commit_result = await run_process(("git", "commit", "-m", commit_message), cwd=repo_path)
    if commit_result.returncode != 0:
        raise RuntimeError(f"Failed to create promotion commit: {commit_result.stderr.strip()}")

    commit_sha = (await run_process(("git", "rev-parse", "HEAD"), cwd=repo_path)).stdout.strip()
    tree_digest = (await run_process(("git", "rev-parse", "HEAD^{tree}"), cwd=repo_path)).stdout.strip()

    promotion_payload = {
        "actor_type": "human",
        "actor_id": str(actor_id).strip(),
        "actor_source": str(actor_source).strip(),
        "branch": branch,
        "run_id": run_id,
        "attempt_index": selected_attempt,
        "commit_sha": commit_sha,
        "tree_digest": tree_digest,
        "decision_path": str(run_path / "attempts" / str(selected_attempt) / "decision.json"),
    }
    await _write_json(run_path / "promotion.json", promotion_payload)

    ledger = await LedgerWriter.resume(run_path / "ledger.jsonl")
    event = await ledger.append("promotion_event", promotion_payload)
    promotion_payload["promotion_entry_digest"] = str(event.get("entry_digest", ""))
    await _write_json(run_path / "promotion.json", promotion_payload)
    return promotion_payload


async def _resolve_attempt_index(run_path: Path, attempt_index: int | None) -> int:
    if isinstance(attempt_index, int) and attempt_index >= 1:
        return attempt_index
    summary_path = run_path / "summary.json"
    if await asyncio.to_thread(summary_path.exists):
        summary = await _read_json(summary_path)
        accepted = summary.get("accepted_attempt_index")
        if isinstance(accepted, int) and accepted >= 1:
            return accepted
    raise ValueError("No accepted attempt index available; pass attempt_index explicitly")


async def _read_json(path: Path) -> dict[str, Any]:
    text = await asyncio.to_thread(path.read_text, "utf-8")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object at {path}")
    return payload


async def _write_json(path: Path, payload: dict[str, Any]) -> None:
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    await asyncio.to_thread(_write_utf8_text, path, text)


def _write_utf8_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")
