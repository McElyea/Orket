from __future__ import annotations

from typing import Any

from .canonical import hash_canonical_json


def compute_equivalence_key(
    *,
    base_revision_digest: str,
    proposal_digest: str,
    policy_version: str,
    gate_results_normalized: list[dict[str, Any]],
) -> str:
    payload = {
        "base_revision_digest": base_revision_digest,
        "proposal_digest": proposal_digest,
        "policy_version": policy_version,
        "gate_results_normalized": gate_results_normalized,
    }
    return hash_canonical_json(payload)
