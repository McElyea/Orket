from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.async_file_tools import capture_file_roots

from .artifacts import read_json_object, write_json_file
from .canonical import hash_canonical_json
from .equivalence import compute_equivalence_key


async def replay_run(run_path: Path) -> dict[str, Any]:
    """
    Offline replay for Marshaller v0 decision equivalence.

    Reads recorded artifacts only and emits `replay_result.json`.
    """

    run_path, = capture_file_roots([run_path])
    attempt_index = await _resolve_attempt_index(run_path)
    decision_path = run_path / "attempts" / str(attempt_index) / "decision.json"
    proposal_path = run_path / "attempts" / str(attempt_index) / "proposal.json"
    decision = await read_json_object(decision_path)
    proposal = await read_json_object(proposal_path)

    gate_results = list(decision.get("gate_results_normalized") or [])
    policy_version = str(decision.get("policy_version") or "v0")
    base_revision_digest = str(proposal.get("base_revision_digest") or "")
    proposal_digest = hash_canonical_json(proposal)
    replay_key = compute_equivalence_key(
        base_revision_digest=base_revision_digest,
        proposal_digest=proposal_digest,
        policy_version=policy_version,
        gate_results_normalized=gate_results,
    )
    stored_key = str(decision.get("equivalence_key") or "")
    payload = {
        "replay_contract_version": "marshaller.replay.v0",
        "equivalence_key_match": replay_key == stored_key,
        "recorded_equivalence_key": stored_key,
        "replayed_equivalence_key": replay_key,
        "attempt_index": attempt_index,
        "decision_path": str(decision_path),
        "proposal_path": str(proposal_path),
    }
    await write_json_file(run_path / "replay_result.json", payload)
    return payload


async def _resolve_attempt_index(run_path: Path) -> int:
    summary_path = run_path / "summary.json"
    if await run_owned_thread(summary_path.exists, label="marshaller-replay-exists"):
        summary = await read_json_object(summary_path)
        accepted = summary.get("accepted_attempt_index")
        if isinstance(accepted, int) and accepted >= 1:
            return accepted
    attempts_root = run_path / "attempts"
    if not await run_owned_thread(attempts_root.exists, label="marshaller-replay-exists"):
        raise ValueError(f"No attempts found under {attempts_root}")
    names = await run_owned_thread(lambda: [p.name for p in attempts_root.iterdir() if p.is_dir()], label="marshaller-replay-attempts")
    numeric = sorted(int(name) for name in names if name.isdigit())
    if not numeric:
        raise ValueError(f"No numeric attempt directories found under {attempts_root}")
    return numeric[-1]
