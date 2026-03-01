from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.reforger.compiler import apply_patch_ops, run_compile_pipeline
from orket.reforger.routes.textmystery_persona_v0 import TextMysteryPersonaRouteV0


def _seed_textmystery_inputs(root: Path, *, invalid_npc_archetype: bool = False) -> None:
    yaml = pytest.importorskip("yaml")
    assert yaml is not None
    prompts = root / "content" / "prompts"
    prompts.mkdir(parents=True, exist_ok=True)
    (root / "content").mkdir(parents=True, exist_ok=True)

    archetypes = {
        "version": 1,
        "defaults": {
            "max_words": 14,
            "end_punctuation": ".",
            "allow_ellipsis": False,
            "allow_exclamation": False,
            "allow_questions": True,
            "allow_contractions": True,
        },
        "archetypes": {
            "TERSE": {
                "description": "short",
                "rules": {"max_words": 10, "allow_exclamation": False},
                "banks": {"refuse": ["No comment."]},
            }
        },
    }
    npcs = {
        "version": 1,
        "npcs": {
            "NICK": {
                "archetype": ("MISSING_ARCH" if invalid_npc_archetype else "TERSE"),
                "display_name": "Nick",
                "refusal_style_id": "REF_STYLE_STEEL",
            }
        },
    }
    refusal_styles = [{"id": "REF_STYLE_STEEL", "templates": ["No comment."]}]

    (prompts / "archetypes.yaml").write_text(yaml.safe_dump(archetypes, sort_keys=True), encoding="utf-8")
    (prompts / "npcs.yaml").write_text(yaml.safe_dump(npcs, sort_keys=True), encoding="utf-8")
    (root / "content" / "refusal_styles.yaml").write_text(yaml.safe_dump(refusal_styles, sort_keys=True), encoding="utf-8")


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _seed_scenario_pack(path: Path, *, mode: str = "truth_only") -> None:
    payload = {
        "pack_id": "truth_only_fixture",
        "version": "1.0.0",
        "mode": mode,
        "tests": [
            {"id": "TRUTH_001", "kind": "npc_archetype_exists", "hard": True, "weight": 1.0},
            {"id": "TRUTH_002", "kind": "npc_refusal_style_exists", "hard": True, "weight": 1.0},
            {"id": "TRUTH_003", "kind": "refusal_templates_non_empty", "hard": True, "weight": 1.0},
            {"id": "TRUTH_004", "kind": "no_exclamation_rules", "hard": False, "weight": 0.3},
            {"id": "TRUTH_005", "kind": "reasonable_word_limits", "hard": False, "weight": 0.2, "params": {"max_allowed": 24}},
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_roundtrip_idempotence_by_canonical_digest(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed_textmystery_inputs(src)
    route = TextMysteryPersonaRouteV0()
    blob1 = route.normalize(src)
    out = tmp_path / "materialized"
    route.materialize(blob1, out)
    blob2 = route.normalize(out)
    assert route.canonical_json(blob1) == route.canonical_json(blob2)


def test_compile_pipeline_is_deterministic(tmp_path: Path) -> None:
    src = tmp_path / "src"
    out = tmp_path / "out"
    scenario = tmp_path / "scenario_pack.json"
    _seed_textmystery_inputs(src)
    _seed_scenario_pack(scenario)
    first = run_compile_pipeline(
        route_id="textmystery_persona_v0",
        input_dir=src,
        out_dir=out,
        mode="truth_only",
        model_id="fake",
        seed=7,
        max_iters=4,
        scenario_pack_path=scenario,
    )
    assert first.ok
    snapshot = {
        "final_score": _json(out / "artifacts" / "final_score_report.json"),
        "digests": _json(out / "artifacts" / "bundle_digests.json"),
        "route_plan": _json(out / "artifacts" / "route_plan.json"),
        "outputs_manifest": _json(out / "artifacts" / "outputs_manifest.json"),
    }
    second = run_compile_pipeline(
        route_id="textmystery_persona_v0",
        input_dir=src,
        out_dir=out,
        mode="truth_only",
        model_id="fake",
        seed=7,
        max_iters=4,
        scenario_pack_path=scenario,
    )
    assert second.ok
    assert snapshot["final_score"] == _json(out / "artifacts" / "final_score_report.json")
    assert snapshot["digests"] == _json(out / "artifacts" / "bundle_digests.json")
    assert snapshot["route_plan"] == _json(out / "artifacts" / "route_plan.json")
    assert snapshot["outputs_manifest"] == _json(out / "artifacts" / "outputs_manifest.json")


def test_inspector_catches_reference_integrity_error(tmp_path: Path) -> None:
    src = tmp_path / "src"
    out = tmp_path / "out"
    scenario = tmp_path / "scenario_pack.json"
    _seed_textmystery_inputs(src, invalid_npc_archetype=True)
    _seed_scenario_pack(scenario)
    result = run_compile_pipeline(
        route_id="textmystery_persona_v0",
        input_dir=src,
        out_dir=out,
        mode="truth_only",
        model_id="fake",
        seed=1,
        max_iters=2,
        scenario_pack_path=scenario,
    )
    assert not result.ok
    route_plan = _json(out / "artifacts" / "route_plan.json")
    assert route_plan["errors"]
    assert "unknown archetype" in route_plan["errors"][0]


def test_patch_safety_rejects_outside_surface() -> None:
    blob = {
        "version": "persona_blob.v0",
        "banks": {"archetypes": {}, "refusal_styles": {}},
        "entities": {"npcs": {}},
        "rules": {"defaults": {}},
    }
    with pytest.raises(ValueError):
        apply_patch_ops(blob, [{"op": "replace", "path": "/version", "value": "x"}])


def test_scenario_pack_mode_mismatch_fails(tmp_path: Path) -> None:
    src = tmp_path / "src"
    out = tmp_path / "out"
    scenario = tmp_path / "scenario_pack.json"
    _seed_textmystery_inputs(src)
    _seed_scenario_pack(scenario, mode="lies_only")
    with pytest.raises(ValueError):
        run_compile_pipeline(
            route_id="textmystery_persona_v0",
            input_dir=src,
            out_dir=out,
            mode="truth_only",
            model_id="fake",
            seed=1,
            max_iters=2,
            scenario_pack_path=scenario,
        )
