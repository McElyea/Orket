from __future__ import annotations

from scripts.prompt_lab import run_prompt_reforger_gemma_tool_use_inventory as script


def test_inventory_targets_freeze_admitted_gemma_lane_models() -> None:
    """Layer: contract. Verifies the admitted Gemma lane inventory targets stay frozen to the planned provider/model ids."""
    rows = [target.to_payload() for target in script.INVENTORY_TARGETS]

    assert [row["role"] for row in rows] == [
        "proposer_quality",
        "proposer_portability",
        "judge_primary",
        "judge_fallback",
    ]
    assert rows[0]["requested_model"] == "google/gemma-3-12b-it-qat"
    assert rows[0]["provider_model_candidates"] == ["google/gemma-3-12b-it-qat", "gemma-3-12b-it-qat"]
    assert rows[1]["requested_model"] == "google/gemma-3-4b-it-qat"
    assert rows[1]["provider_model_candidates"] == ["google/gemma-3-4b-it-qat", "gemma-3-4b-it-qat"]
    assert rows[2]["requested_model"] == "functiongemma"
    assert rows[2]["provider_model_candidates"] == ["functiongemma", "functiongemma:latest"]
    assert rows[3]["requested_model"] == "google/functiongemma-270m"
    assert rows[3]["provider_model_candidates"] == ["google/functiongemma-270m", "functiongemma-270m-it"]
    assert rows[2]["preferred_quantization"] == "Q8_0"


def test_bootstrap_proof_slice_freezes_current_harness_authority() -> None:
    """Layer: contract. Verifies the bootstrap proof slice stays bound to the current challenge_workflow_runtime harness."""
    payload = script._bootstrap_proof_slice()

    assert payload["slice_id"] == "challenge_workflow_runtime_bootstrap_v0"
    assert payload["harness_script"] == "scripts/benchmarks/run_local_model_coding_challenge.py"
    assert payload["harness_output"] == "benchmarks/staging/General/local_model_coding_challenge_report.json"
    assert payload["measured_outputs"] == [
        "accepted_tool_calls",
        "rejected_tool_calls",
        "argument_shape_defects",
        "turns_to_first_valid_tool_call",
        "turns_to_first_valid_completion",
        "final_disposition",
    ]
