from __future__ import annotations

import json
from pathlib import Path


def test_bootstrap_corpus_freezes_bounded_challenge_slices() -> None:
    """Layer: contract. Verifies the bounded Gemma bootstrap corpus stays fixed to the admitted challenge slices and metrics."""
    corpus_path = Path("c:/Source/Orket/docs/projects/PromptReforgerToolCompatibility/GEMMA_TOOL_USE_CHALLENGE_CORPUS_V1.json")
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))

    assert payload["corpus_id"] == "challenge_workflow_runtime_bootstrap_v1"
    assert payload["tool_call_contract_family"] == "challenge_workflow_runtime.turn_contract.v1"
    assert payload["measured_outputs"] == [
        "accepted_tool_calls",
        "rejected_tool_calls",
        "argument_shape_defects",
        "turns_to_first_valid_tool_call",
        "turns_to_first_valid_completion",
        "final_disposition",
    ]
    assert [row["slice_id"] for row in payload["slices"]] == [
        "PRGTU-CWR01-CODER-SINGLE-WRITE",
        "PRGTU-CWR01-GUARD-READ-ACCEPT",
        "PRGTU-CWR03-CODER-MULTI-WRITE",
        "PRGTU-CWR03-GUARD-MULTI-READ",
        "PRGTU-CWR04-CODER-PACKAGE-REPAIR",
    ]
