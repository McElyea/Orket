from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.async_file_tools import capture_file_roots

from .artifacts import read_json_object, write_json_file
from .ledger import LedgerWriter
from .process import run_process


def _resolve_repo_path(run_payload: dict[str, Any], invocation_root: Path) -> Path:
    return (invocation_root / str(((run_payload.get("request") or {}).get("repo_path")) or "")).resolve()


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

    run_path, invocation_root = capture_file_roots([run_path, Path()])
    run_payload = await read_json_object(run_path / "run.json")
    selected_attempt = await _resolve_attempt_index(run_path, attempt_index)
    decision = await read_json_object(run_path / "attempts" / str(selected_attempt) / "decision.json")
    if not bool(decision.get("accept")):
        raise ValueError("Cannot promote a rejected attempt")

    patch_path = run_path / "attempts" / str(selected_attempt) / "patch.diff"
    repo_path = await run_owned_thread(partial(_resolve_repo_path, run_payload, invocation_root), label="marshaller-promotion-repo")
    if not await run_owned_thread(repo_path.exists, label="marshaller-promotion-exists"):
        raise ValueError(f"Repository path does not exist: {repo_path}")

    run_id = str(run_payload.get("run_id") or run_path.name)
    commit_sha, tree_digest = await _promote_git(repo_path, patch_path, branch, run_id, selected_attempt)

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
    await write_json_file(run_path / "promotion.json", promotion_payload)

    ledger = await LedgerWriter.resume(run_path / "ledger.jsonl")
    event = await ledger.append("promotion_event", promotion_payload)
    promotion_payload["promotion_entry_digest"] = str(event.get("entry_digest", ""))
    await write_json_file(run_path / "promotion.json", promotion_payload)
    return promotion_payload


async def _resolve_attempt_index(run_path: Path, attempt_index: int | None) -> int:
    if isinstance(attempt_index, int) and attempt_index >= 1:
        return attempt_index
    summary_path = run_path / "summary.json"
    if await run_owned_thread(summary_path.exists, label="marshaller-promotion-exists"):
        summary = await read_json_object(summary_path)
        accepted = summary.get("accepted_attempt_index")
        if isinstance(accepted, int) and accepted >= 1:
            return accepted
    raise ValueError("No accepted attempt index available; pass attempt_index explicitly")



async def _promote_git(repo_path: Path, patch_path: Path, branch: str, run_id: str, selected_attempt: int) -> tuple[str, str]:
    checkout = await run_process(("git", "checkout", branch), cwd=repo_path)
    if checkout.returncode != 0:
        raise RuntimeError(f"Failed to checkout branch '{branch}': {checkout.stderr.strip()}")

    apply_result = await run_process(("git", "apply", str(patch_path)), cwd=repo_path)
    if apply_result.returncode != 0:
        raise RuntimeError(f"Failed to apply patch during promotion: {apply_result.stderr.strip()}")

    add_result = await run_process(("git", "add", "-A"), cwd=repo_path)
    if add_result.returncode != 0:
        raise RuntimeError(f"Failed to stage promotion changes: {add_result.stderr.strip()}")

    commit_message = f"marshaller promote {run_id} attempt {selected_attempt}"
    commit_result = await run_process(("git", "commit", "-m", commit_message), cwd=repo_path)
    if commit_result.returncode != 0:
        raise RuntimeError(f"Failed to create promotion commit: {commit_result.stderr.strip()}")

    commit_sha = (await run_process(("git", "rev-parse", "HEAD"), cwd=repo_path)).stdout.strip()
    tree_digest = (await run_process(("git", "rev-parse", "HEAD^{tree}"), cwd=repo_path)).stdout.strip()

    return commit_sha, tree_digest
