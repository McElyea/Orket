from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.adapters.tools.families.reforger_tools import ReforgerTools


def _seed_textmystery_inputs(root: Path) -> None:
    yaml = pytest.importorskip("yaml")
    assert yaml is not None
    prompts = root / "content" / "prompts"
    prompts.mkdir(parents=True, exist_ok=True)
    (root / "content").mkdir(parents=True, exist_ok=True)
    (prompts / "archetypes.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "defaults": {"max_words": 14, "allow_exclamation": False},
                "archetypes": {"TERSE": {"description": "x", "rules": {"max_words": 10}, "banks": {"refuse": ["No"]}}},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (prompts / "npcs.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "npcs": {
                    "NICK": {
                        "archetype": "TERSE",
                        "display_name": "Nick",
                        "refusal_style_id": "REF_STYLE_STEEL",
                        "voice_profile_id": "NICK_VOICE",
                    }
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (root / "content" / "refusal_styles.yaml").write_text(
        yaml.safe_dump([{"id": "REF_STYLE_STEEL", "templates": ["No comment."]}], sort_keys=True),
        encoding="utf-8",
    )
    voices = root / "content" / "voices"
    voices.mkdir(parents=True, exist_ok=True)
    (voices / "profiles.yaml").write_text(
        yaml.safe_dump(
            {"version": 1, "profiles": {"NICK_VOICE": {"voice_id": "male_low_clipped", "emotion_map": {"neutral": {}}}}},
            sort_keys=True,
        ),
        encoding="utf-8",
    )
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
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_reforger_tools_inspect_and_run(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    tools = ReforgerTools(workspace, [tmp_path])
    _seed_textmystery_inputs(tmp_path)

    inspect = tools.inspect(
        {
            "route_id": "textmystery_v1",
            "input_dir": str(tmp_path),
            "mode": "truth_only",
            "scenario_pack": "truth_only_v0",
        }
    )
    assert inspect["ok"] is True
    assert inspect["tool"] == "reforger_inspect"
    assert inspect["version"] == "1"
    assert inspect["suite_ready"] is True
    assert Path(str(inspect["artifact_root"])).exists()

    out_dir = workspace / "materialized"
    run = tools.run(
        {
            "route_id": "textmystery_v1",
            "input_dir": str(tmp_path),
            "output_dir": "materialized",
            "mode": "truth_only",
            "scenario_pack": "truth_only_v0",
            "seed": 1,
            "max_iters": 2,
            "model_id": "fake",
        }
    )
    assert run["ok"] is True
    assert run["tool"] == "reforger_run"
    assert run["version"] == "1"
    assert run["forced"] is False
    assert (out_dir / "content" / "prompts" / "archetypes.yaml").exists()


def test_reforger_run_rejects_absolute_and_parent_escape_output_dir(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    tools = ReforgerTools(workspace, [tmp_path])
    _seed_textmystery_inputs(tmp_path)

    bad_abs = tools.run(
        {
            "route_id": "textmystery_v1",
            "input_dir": str(tmp_path),
            "output_dir": str(tmp_path / "outside_abs"),
            "mode": "truth_only",
            "scenario_pack": "truth_only_v0",
            "seed": 1,
            "max_iters": 2,
        }
    )
    assert bad_abs["ok"] is False
    assert "workspace-relative" in bad_abs["error"]

    bad_escape = tools.run(
        {
            "route_id": "textmystery_v1",
            "input_dir": str(tmp_path),
            "output_dir": "../escape",
            "mode": "truth_only",
            "scenario_pack": "truth_only_v0",
            "seed": 1,
            "max_iters": 2,
        }
    )
    assert bad_escape["ok"] is False
    assert "must not contain '..'" in bad_escape["error"]

    ok_dot = tools.run(
        {
            "route_id": "textmystery_v1",
            "input_dir": str(tmp_path),
            "output_dir": ".",
            "mode": "truth_only",
            "scenario_pack": "truth_only_v0",
            "seed": 1,
            "max_iters": 2,
        }
    )
    assert ok_dot["ok"] is True


def test_reforger_run_deterministic_digests_with_same_inputs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    tools = ReforgerTools(workspace, [tmp_path])
    _seed_textmystery_inputs(tmp_path)

    args = {
        "route_id": "textmystery_v1",
        "input_dir": str(tmp_path),
        "output_dir": "materialized",
        "mode": "truth_only",
        "scenario_pack": "truth_only_v0",
        "seed": 7,
        "max_iters": 4,
        "model_id": "fake",
    }
    run1 = tools.run(args)
    run2 = tools.run(args)
    assert run1["ok"] is True and run2["ok"] is True
    assert run1["best_candidate_id"] == run2["best_candidate_id"]

    artifact_root = Path(str(run1["artifact_root"]))
    dig1 = json.loads((artifact_root / "run" / "artifacts" / "bundle_digests.json").read_text(encoding="utf-8"))
    score1 = json.loads((artifact_root / "run" / "artifacts" / "final_score_report.json").read_text(encoding="utf-8"))
    dig2 = json.loads((artifact_root / "run" / "artifacts" / "bundle_digests.json").read_text(encoding="utf-8"))
    score2 = json.loads((artifact_root / "run" / "artifacts" / "final_score_report.json").read_text(encoding="utf-8"))
    assert dig1 == dig2
    assert score1 == score2


def test_reforger_run_force_fields_present(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    tools = ReforgerTools(workspace, [tmp_path])
    _seed_textmystery_inputs(tmp_path)
    # Remove scenario pack so forced fallback path is exercised.
    (tmp_path / "reforge" / "scenario_packs" / "truth_only_v0.json").unlink()
    run = tools.run(
        {
            "route_id": "textmystery_v1",
            "input_dir": str(tmp_path),
            "output_dir": "materialized",
            "mode": "truth_only",
            "scenario_pack": "truth_only_v0",
            "seed": 1,
            "max_iters": 2,
            "forced": True,
            "force_reason": "suite_ready_false",
        }
    )
    assert run["ok"] is True
    assert run["forced"] is True
    assert run["force_reason"] == "suite_ready_false"
    assert "forced_without_scenario_pack" in run["warnings"]
