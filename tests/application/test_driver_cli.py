import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.adapters.tools.families.reforger_tools import ReforgerTools
from orket.driver import OrketDriver


def _build_driver(tmp_path: Path) -> OrketDriver:
    model_root = tmp_path / "model"
    core = model_root / "core"
    for folder in ("teams", "environments", "epics", "rocks", "roles", "dialects", "skills"):
        (core / folder).mkdir(parents=True, exist_ok=True)

    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = model_root
    driver.fs = AsyncFileTools(tmp_path)
    driver.skill = None
    driver.dialect = None
    driver.provider = SimpleNamespace(complete=None)
    driver.reforger_tools = ReforgerTools(tmp_path / "workspace" / "default", [tmp_path])
    return driver


def _seed_textmystery_inputs(root: Path) -> None:
    import yaml

    prompts = root / "content" / "prompts"
    prompts.mkdir(parents=True, exist_ok=True)
    (root / "content").mkdir(parents=True, exist_ok=True)
    archetypes = {
        "version": 1,
        "defaults": {"max_words": 14, "allow_exclamation": False},
        "archetypes": {"TERSE": {"description": "x", "rules": {"max_words": 10}, "banks": {"refuse": ["No"]}}},
    }
    npcs = {
        "version": 1,
        "npcs": {
            "NICK": {
                "archetype": "TERSE",
                "display_name": "Nick",
                "refusal_style_id": "REF_STYLE_STEEL",
                "voice_profile_id": "NICK_VOICE",
            }
        },
    }
    styles = [{"id": "REF_STYLE_STEEL", "templates": ["No comment."]}]
    voices = {"version": 1, "profiles": {"NICK_VOICE": {"voice_id": "male_low_clipped", "emotion_map": {"neutral": {}}}}}
    (prompts / "archetypes.yaml").write_text(yaml.safe_dump(archetypes, sort_keys=True), encoding="utf-8")
    (prompts / "npcs.yaml").write_text(yaml.safe_dump(npcs, sort_keys=True), encoding="utf-8")
    (root / "content" / "refusal_styles.yaml").write_text(yaml.safe_dump(styles, sort_keys=True), encoding="utf-8")
    voices_dir = root / "content" / "voices"
    voices_dir.mkdir(parents=True, exist_ok=True)
    (voices_dir / "profiles.yaml").write_text(yaml.safe_dump(voices, sort_keys=True), encoding="utf-8")
    scenario = root / "reforge" / "scenario_packs"
    scenario.mkdir(parents=True, exist_ok=True)
    (scenario / "truth_only_v0.json").write_text(
        json.dumps(
            {
                "pack_id": "truth_only_fixture",
                "version": "1.0.0",
                "mode": "truth_only",
                "tests": [
                    {"id": "TRUTH_001", "kind": "npc_archetype_exists", "hard": True, "weight": 1.0},
                    {"id": "TRUTH_002", "kind": "npc_refusal_style_exists", "hard": True, "weight": 1.0},
                    {"id": "TRUTH_003", "kind": "refusal_templates_non_empty", "hard": True, "weight": 1.0},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_cli_list_departments(tmp_path: Path):
    driver = _build_driver(tmp_path)
    response = await driver.process_request("/list departments")
    assert "Departments" in response
    assert "core" in response


@pytest.mark.asyncio
async def test_cli_create_and_show_team(tmp_path: Path):
    driver = _build_driver(tmp_path)
    create = await driver.process_request("/create team platform_ops core")
    assert "Created team 'platform_ops'" in create

    show = await driver.process_request("/show team platform_ops core")
    payload = json.loads(show)
    assert payload["name"] == "platform_ops"
    assert "code_reviewer" in payload["roles"]


@pytest.mark.asyncio
async def test_cli_create_environment_and_list(tmp_path: Path):
    driver = _build_driver(tmp_path)
    create = await driver.process_request("/create environment staging core")
    assert "Created environment 'staging'" in create

    listed = await driver.process_request("/list environments core")
    assert "staging" in listed


@pytest.mark.asyncio
async def test_cli_add_card_and_list_cards(tmp_path: Path):
    driver = _build_driver(tmp_path)
    await driver.process_request("/create epic payments_upgrade core")

    added = await driver.process_request('/add-card payments_upgrade coder 2.5 "Implement retry policy" --department core')
    assert "Added card to epic 'payments_upgrade'" in added

    listed = await driver.process_request("/list-cards payments_upgrade core")
    assert "Implement retry policy" in listed
    assert "[coder]" in listed


@pytest.mark.asyncio
async def test_cli_reforge_inspect_and_run(tmp_path: Path):
    driver = _build_driver(tmp_path)
    _seed_textmystery_inputs(tmp_path)
    inspect = await driver.process_request(
        f"/reforge inspect --route textmystery_v1 --in {tmp_path.as_posix()} --mode truth_only --scenario-pack truth_only_v0"
    )
    assert "Reforger inspect ok." in inspect
    assert "suite_ready=True" in inspect

    out_dir = tmp_path / "workspace" / "default" / "compiled_out"
    run = await driver.process_request(
        (
            f"/reforge run --route textmystery_v1 --in {tmp_path.as_posix()} --out compiled_out "
            "--mode truth_only --scenario-pack truth_only_v0 --seed 1 --max-iters 2"
        )
    )
    assert "Reforger run ok=True" in run
    assert "forced=False" in run
    assert (out_dir / "content" / "prompts" / "archetypes.yaml").exists()


@pytest.mark.asyncio
async def test_cli_reforge_run_block_lists_missing_details(tmp_path: Path):
    driver = _build_driver(tmp_path)
    _seed_textmystery_inputs(tmp_path)
    # Remove scenario pack so suite_ready=false.
    scenario = tmp_path / "reforge" / "scenario_packs" / "truth_only_v0.json"
    scenario.unlink()
    out_dir = tmp_path / "workspace" / "default" / "compiled_out"
    run = await driver.process_request(
        (
            f"/reforge run --route textmystery_v1 --in {tmp_path.as_posix()} --out compiled_out "
            "--mode truth_only --scenario-pack truth_only_v0 --seed 1 --max-iters 2"
        )
    )
    assert "suite_ready=false" in run
    assert "missing_inputs=" in run
    assert "errors=" in run
    assert "suite_requirements=" in run
    assert not out_dir.exists()


@pytest.mark.asyncio
async def test_cli_reforge_run_force_includes_force_fields(tmp_path: Path):
    driver = _build_driver(tmp_path)
    _seed_textmystery_inputs(tmp_path)
    scenario = tmp_path / "reforge" / "scenario_packs" / "truth_only_v0.json"
    scenario.unlink()
    run = await driver.process_request(
        (
            f"/reforge run --route textmystery_v1 --in {tmp_path.as_posix()} --out compiled_out "
            "--mode truth_only --scenario-pack truth_only_v0 --seed 1 --max-iters 2 --force"
        )
    )
    assert "Reforger run ok=True" in run
    assert "forced=True" in run
    assert "force_reason=suite_ready_false" in run
