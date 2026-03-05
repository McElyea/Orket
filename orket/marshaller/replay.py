from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from .canonical import hash_canonical_json
from .equivalence import compute_equivalence_key


async def replay_run(run_path: Path) -> dict[str, Any]:
    """
    Offline replay for Marshaller v0 decision equivalence.

    Reads recorded artifacts only and emits `replay_result.json`.
    """

    decision_path = run_path / "attempts" / "1" / "decision.json"
    proposal_path = run_path / "attempts" / "1" / "proposal.json"
    decision = await _read_json(decision_path)
    proposal = await _read_json(proposal_path)

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
        "decision_path": str(decision_path),
        "proposal_path": str(proposal_path),
    }
    await _write_json(run_path / "replay_result.json", payload)
    return payload


async def _read_json(path: Path) -> dict[str, Any]:
    text = await asyncio.to_thread(path.read_text, "utf-8")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError(f"Expected object at {path}")
    return value


async def _write_json(path: Path, payload: dict[str, Any]) -> None:
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    await asyncio.to_thread(_write_utf8_text, path, text)


def _write_utf8_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")
