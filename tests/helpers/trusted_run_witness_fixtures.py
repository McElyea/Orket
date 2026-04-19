from __future__ import annotations

from scripts.proof.trusted_run_witness_fixture_bundle import build_valid_trusted_run_witness_bundle


def valid_bundle(*, session_id: str = "sess-a") -> dict[str, object]:
    return build_valid_trusted_run_witness_bundle(session_id=session_id)
