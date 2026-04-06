# LIFECYCLE: live
from pathlib import Path

from scripts.odr.model_role_fit_lane import load_lane_config, load_matrix_registry
from scripts.odr.model_role_fit_triple_runtime import run_live_triple_scenario
from scripts.odr.run_odr_single_vs_coordinated import _load_scenario_inputs, _load_scenarios

REPO_ROOT = Path(__file__).resolve().parents[2]
LANE_CONFIG_PATH = (
    REPO_ROOT / "docs" / "projects" / "archive" / "ODRModelRoleFit" / "MRF03212026" / "odr_model_role_fit_lane_config.json"
)


async def test_run_live_triple_scenario_accepts_reused_v1_state_contract_key(monkeypatch) -> None:
    """Layer: integration. Verifies the triple runtime accepts the archived role-fit config shape that carries reused_v1_state_contract_path instead of v1_state_contract_path."""
    config = load_lane_config(LANE_CONFIG_PATH)
    registry = load_matrix_registry(config)
    triple_variant = registry["preferred_triples"][0].ordered_variants()[0]
    scenario = next(row for row in _load_scenarios() if str(row["id"]) == "overfitting")
    scenario_input = _load_scenario_inputs(scenario)

    async def _fake_call_role(*, model: str, provider_name: str, messages: list[dict[str, str]], timeout_sec: int):
        if "Architect" in str(messages[0]["content"]):
            return (
                "### REQUIREMENT\nThe assistant must work fully offline and must not call external APIs.\n"
                "### CHANGELOG\n- preserved offline-only scope.\n"
                "### ASSUMPTIONS\n- none.\n"
                "### OPEN_QUESTIONS\n- none.",
                {"input_tokens": 42},
                25,
                42,
            )
        return (
            "### CRITIQUE\n- none.\n"
            "### PATCHES\n- none.\n"
            "### EDGE_CASES\n- none.\n"
            "### TEST_GAPS\n- none.",
            {"input_tokens": 33},
            20,
            33,
        )

    monkeypatch.setattr("scripts.odr.model_role_fit_triple_runtime._call_role", _fake_call_role)

    inspect_row, compare_row = await run_live_triple_scenario(
        config={
            "config_path": str(LANE_CONFIG_PATH.resolve()),
            "reused_v1_state_contract_path": str(config["reused_v1_state_contract_path"]),
            "role_timeout_sec": 1,
        },
        triple_variant=triple_variant,
        scenario_input=scenario_input,
        locked_budget=1,
    )

    assert inspect_row["entity_id"] == str(triple_variant["triple_id"])
    assert len(inspect_row["rounds"]) == 1
    assert "shared_state_snapshot" in inspect_row["rounds"][0]["mode_artifacts"]
    assert compare_row["entity_id"] == str(triple_variant["triple_id"])
    assert compare_row["base_triple_id"] == str(triple_variant["base_triple_id"])
    assert compare_row["rounds_consumed"] == 1
    assert compare_row["stop_reason"] != "RUNTIME_BLOCKER"
