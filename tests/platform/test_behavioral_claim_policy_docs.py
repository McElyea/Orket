from __future__ import annotations

from pathlib import Path


def test_prompt_reforger_contract_blocks_unproven_4b_portability_claim() -> None:
    """Layer: contract. Verifies Gemma 4B portability is truthfully downgraded until evidence clears."""
    contract = Path("docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md").read_text(encoding="utf-8")

    assert "`gemma-3-4b-it-qat` and other sub-7B targets are `unsupported`" in contract
    assert "must not be described as clearing the frozen 5-slice portability corpus" in contract


def test_determinism_policy_downgrades_unproven_odr_text_identity() -> None:
    """Layer: contract. Verifies ODR text identity claims require byte-level proof and variance data."""
    policy = Path("docs/specs/ORKET_DETERMINISM_GATE_POLICY.md").read_text(encoding="utf-8")

    assert "ODR, local-model, and prompt-refinement lanes must not claim `text_deterministic`" in policy
    assert "Missing variance data blocks the claim" in policy
