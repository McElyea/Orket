import json
from pathlib import Path

from scripts.odr.model_role_fit_live_proof import run_model_role_fit_live_proof

REPO_ROOT = Path(__file__).resolve().parents[2]
LANE_CONFIG_PATH = (
    REPO_ROOT / "docs" / "projects" / "archive" / "ODRModelRoleFit" / "MRF03212026" / "odr_model_role_fit_lane_config.json"
)


def _temp_config(tmp_path: Path) -> Path:
    raw = json.loads(LANE_CONFIG_PATH.read_text(encoding="utf-8"))
    raw["matrix_registry"] = str(
        (
            REPO_ROOT
            / "docs"
            / "projects"
            / "archive"
            / "ODRModelRoleFit"
            / "MRF03212026"
            / "odr_model_role_fit_matrix_registry.json"
        ).resolve()
    )
    raw["output_schema"] = str(
        (
            REPO_ROOT
            / "docs"
            / "projects"
            / "archive"
            / "ODRModelRoleFit"
            / "MRF03212026"
            / "odr_model_role_fit_output_schema.json"
        ).resolve()
    )
    raw["reused_v1_state_contract"] = str(
        (REPO_ROOT / "docs" / "projects" / "archive" / "ContextContinuity" / "CC03212026" / "odr_context_continuity_v1_state_contract.json").resolve()
    )
    raw["reused_continuity_closeout"] = str(
        (REPO_ROOT / "docs" / "projects" / "archive" / "ContextContinuity" / "CC03212026" / "Closeout.md").resolve()
    )
    raw["artifact_paths"] = {
        "root": str((tmp_path / "artifacts").resolve()),
        "bootstrap_output": str((tmp_path / "artifacts" / "bootstrap.json").resolve()),
        "pair_inspectability_output": str((tmp_path / "artifacts" / "pair_inspect.json").resolve()),
        "pair_compare_output": str((tmp_path / "artifacts" / "pair_compare.json").resolve()),
        "pair_verdict_output": str((tmp_path / "artifacts" / "pair_verdict.json").resolve()),
        "triple_inspectability_output": str((tmp_path / "artifacts" / "triple_inspect.json").resolve()),
        "triple_compare_output": str((tmp_path / "artifacts" / "triple_compare.json").resolve()),
        "triple_verdict_output": str((tmp_path / "artifacts" / "triple_verdict.json").resolve()),
        "closeout_output": str((tmp_path / "artifacts" / "closeout.json").resolve()),
    }
    config_path = tmp_path / "lane_config.json"
    config_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return config_path


async def test_run_model_role_fit_live_proof_writes_artifacts_and_skips_triples_when_only_one_pair_survives(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Layer: integration. Verifies the serial live-proof orchestrator writes all required artifacts and preserves a skipped triple phase when fewer than two pairs survive."""
    config_path = _temp_config(tmp_path)

    async def _fake_preflight_inventory(
        registry: dict[str, object],
        *,
        role_timeout_sec: int,
    ) -> list[dict[str, object]]:
        assert role_timeout_sec == 300
        return [
            {"model_id": "gemma3:27b", "provider": "ollama", "status": "ok"},
            {"model_id": "mistralai/magistral-small-2509", "provider": "lmstudio", "status": "ok"},
        ]

    async def _fake_pair_run(*, pair, scenario_input, locked_budget, **_kwargs):
        stop_reason = "STABLE_DIFF_FLOOR" if int(pair.execution_order) == 1 else "CODE_LEAK"
        converged = int(pair.execution_order) == 1
        return (
            {
                "pair_id": str(pair.pair_id),
                "scenario_id": str(scenario_input["id"]),
                "locked_budget": int(locked_budget),
                "rounds": [{"round_index": 0}],
            },
            {
                "pair_id": str(pair.pair_id),
                "scenario_id": str(scenario_input["id"]),
                "locked_budget": int(locked_budget),
                "converged": converged,
                "stop_reason": stop_reason,
                "rounds_consumed": int(locked_budget),
                "reopened_decision_count": 0,
                "contradiction_count": 0,
                "regression_count": 0,
                "carry_forward_integrity": 1.0,
                "round_latency_ms": [100 + int(pair.execution_order)],
                "round_active_context_size_bytes": [1000 + int(pair.execution_order)],
                "round_active_context_size_tokens": [256],
            },
        )

    async def _unexpected_triple_run(**_kwargs):
        raise AssertionError("Triple phase should not execute when fewer than two pairs survive.")

    monkeypatch.setattr("scripts.odr.model_role_fit_live_proof._preflight_inventory", _fake_preflight_inventory)
    monkeypatch.setattr("scripts.odr.model_role_fit_live_proof.run_live_scenario_mode", _fake_pair_run)
    monkeypatch.setattr("scripts.odr.model_role_fit_live_proof.run_live_triple_scenario", _unexpected_triple_run)

    result = await run_model_role_fit_live_proof(config_path=config_path)

    for key in (
        "bootstrap_output",
        "pair_inspectability_output",
        "pair_compare_output",
        "pair_verdict_output",
        "triple_inspectability_output",
        "triple_compare_output",
        "triple_verdict_output",
        "closeout_output",
    ):
        assert Path(result[key]).exists()

    closeout_payload = json.loads(Path(result["closeout_output"]).read_text(encoding="utf-8"))
    pair_verdict_payload = json.loads(Path(result["pair_verdict_output"]).read_text(encoding="utf-8"))
    triple_verdict_payload = json.loads(Path(result["triple_verdict_output"]).read_text(encoding="utf-8"))

    assert pair_verdict_payload["best_observed_pair"] == "magistral_small_2509__gemma3_27b"
    assert pair_verdict_payload["triple_phase_status"] == "skipped_insufficient_survivors"
    assert closeout_payload["triple_phase_status"] == "skipped_insufficient_survivors"
    assert closeout_payload["evidence_scope"] == "serial_pair_matrix_only"
    assert triple_verdict_payload["admitted_triples"] == []
    assert triple_verdict_payload["skipped_triples"] == [
        {
            "reason": "insufficient_surviving_pairs",
            "selected_pair_ids": ["magistral_small_2509__gemma3_27b"],
        }
    ]
