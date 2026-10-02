"""Public patch contracts and native compiler refusal/evidence paths."""
import json
from copy import deepcopy

import pytest
import yaml

from orket.reforger.compiler import apply_patch_ops, run_compile_pipeline
from tests.reforger.compiler.test_compile_meta_breaker_v0 import _seed_meta_breaker_inputs
from tests.reforger.compiler.test_compile_textmystery_v0 import _seed_textmystery_inputs


@pytest.mark.contract
def test_patch_edits_lists_and_maps_without_mutating_source():
    blob = {"banks": {"items": ["a", "b", "c"], "mapping": {"old": "retained"}}}
    before = deepcopy(blob)
    patched = apply_patch_ops(blob, [
        {"op": "replace", "path": "/banks/items/1", "value": "B"},
        {"op": "add", "path": "/banks/items/1", "value": "inserted"},
        {"op": "add", "path": "/banks/items/-", "value": "tail"},
        {"op": "remove", "path": "/banks/items/0"},
        {"op": "add", "path": "/banks/mapping/new", "value": "new"},
        {"op": "move", "from": "/banks/items/0", "path": "/banks/items/-"},
        {"op": "move", "from": "/banks/mapping/old", "path": "/banks/items/1"},
        {"op": "move", "from": "/banks/items/0", "path": "/banks/mapping/moved"},
        {"op": "remove", "path": "/banks/mapping/new"},
        {"op": "remove", "path": "/banks/mapping/absent"},
    ])
    assert blob == before
    assert patched == {"banks": {"items": ["retained", "c", "tail", "inserted"], "mapping": {"moved": "B"}}}


@pytest.mark.contract
@pytest.mark.parametrize("operation,diagnostic", [
    ({"op": "copy", "path": "/banks/items", "value": []}, "unsupported patch op"),
    ({"op": "add", "path": "/banks-extra/items", "value": []}, "outside allowed surface"),
    ({"op": "replace", "path": "banks/items", "value": []}, "outside allowed surface"),
    ({"op": "move", "from": "/private", "path": "/banks/items/-"}, "move from outside surface"),
    ({"op": "replace", "path": "/banks/scalar/child/key", "value": 0}, "invalid path resolution"),
])
def test_rejected_patch_does_not_leak_partial_mutation(operation, diagnostic):
    blob = {"banks": {"items": ["kept"], "scalar": 1}, "private": "not admitted"}
    before = deepcopy(blob)
    with pytest.raises(ValueError, match=diagnostic):
        apply_patch_ops(blob, [{"op": "add", "path": "/banks/items/-", "value": "temporary"}, operation])
    assert blob == before


def _compile(src, out, scenario, *, mode="truth_only", route="textmystery_persona_v0"):
    return run_compile_pipeline(route_id=route, input_dir=src, out_dir=out, mode=mode,
                                model_id="deterministic-fixture", seed=0, max_iters=1,
                                scenario_pack_path=scenario)


def _pack(path, tests, *, mode="truth_only"):
    path.write_text(json.dumps({"pack_id": "adverse", "version": "1", "mode": mode, "tests": tests}),
                    encoding="utf-8")


@pytest.mark.integration
@pytest.mark.parametrize("payload,diagnostic", [
    ([], "must be an object"),
    ({"version": "1", "mode": "truth_only", "tests": [{}]}, "pack_id and version"),
    ({"pack_id": "p", "mode": "truth_only", "tests": [{}]}, "pack_id and version"),
    ({"pack_id": "p", "version": "1", "mode": "truth_only", "tests": []}, "non-empty tests list"),
    ({"pack_id": "p", "version": "1", "mode": "truth_only", "tests": "test"}, "non-empty tests list"),
    ({"pack_id": "p", "version": "1", "mode": "truth_only", "tests": [None]}, "must contain objects"),
    ({"pack_id": "p", "version": "1", "mode": "truth_only", "tests": [{"id": "A"}]}, "requires id and kind"),
])
def test_invalid_scenario_never_materializes_a_candidate(tmp_path, payload, diagnostic):
    src, out, scenario = tmp_path / "input", tmp_path / "output", tmp_path / "scenario.json"
    _seed_textmystery_inputs(src)
    scenario.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match=diagnostic):
        _compile(src, out, scenario)
    assert (out / "artifacts" / "route_plan.json").is_file()
    assert not list((out / "materialized").iterdir())
    assert not (out / "artifacts" / "final_score_report.json").exists()


@pytest.mark.integration
def test_missing_scenario_and_unknown_route_fail_with_observable_partial_artifacts(tmp_path):
    src, out, scenario = tmp_path / "input", tmp_path / "output", tmp_path / "absent.json"
    _seed_textmystery_inputs(src)
    with pytest.raises(ValueError, match="scenario pack file not found"):
        _compile(src, out, scenario)
    assert (out / "artifacts" / "canonical_blob.json").is_file()
    with pytest.raises(ValueError, match="unsupported route_id"):
        _compile(src, tmp_path / "unknown", scenario, route="unknown")
    assert not (tmp_path / "unknown").exists()


@pytest.mark.integration
@pytest.mark.parametrize("kind,mutation,detail", [
    ("no_exclamation_rules", "archetype-exclamation", "TERSE.rules.allow_exclamation=true"),
    ("reasonable_word_limits", "zero-words", "TERSE.rules.max_words=0"),
    ("refusal_templates_non_empty", "empty-refusal", "REF_STYLE_STEEL has empty templates"),
    ("refusal_templates_use_reason_code", "plain-refusal", "REF_STYLE_STEEL missing refusal_reason token"),
])
def test_valid_inputs_can_fail_declared_hard_policy_without_false_certification(tmp_path, kind, mutation, detail):
    src, out, scenario = tmp_path / "input", tmp_path / "output", tmp_path / "scenario.json"
    _seed_textmystery_inputs(src)
    if mutation in {"archetype-exclamation", "zero-words"}:
        path = src / "content/prompts/archetypes.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        field, value = ("allow_exclamation", True) if mutation == "archetype-exclamation" else ("max_words", 0)
        data["archetypes"]["TERSE"]["rules"][field] = value
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
    elif mutation == "empty-refusal":
        (src / "content/refusal_styles.yaml").write_text(
            yaml.safe_dump([{"id": "REF_STYLE_STEEL", "templates": []}]), encoding="utf-8")
    _pack(scenario, [{"id": "hard", "kind": kind, "hard": True}])
    result = _compile(src, out, scenario)
    assert not result.ok and result.hard_fail_count == 1 and result.best_score == 0
    baseline = json.loads((out / "artifacts/candidates/candidate_0000.json").read_text(encoding="utf-8"))
    check, = baseline["eval"]["checks"]
    assert not check["pass"] and check["detail"] == detail
    assert result.best_candidate_id == "0000"
    assert (result.materialized_root / "content/prompts/npcs.yaml").is_file()


@pytest.mark.integration
def test_soft_policy_score_retains_weighted_failure_and_sorted_test_identity(tmp_path):
    src, out, scenario = tmp_path / "input", tmp_path / "output", tmp_path / "scenario.json"
    _seed_textmystery_inputs(src)
    _pack(scenario, [{"id": "z", "kind": "refusal_templates_use_reason_code", "weight": 3},
                     {"id": "a", "kind": "npc_archetype_exists", "weight": 1, "params": "ignored"}])
    result = _compile(src, out, scenario)
    assert result.ok and result.hard_fail_count == 0 and result.best_score == .25
    baseline = json.loads((out / "artifacts/candidates/candidate_0000.json").read_text(encoding="utf-8"))
    assert [(row["id"], row["pass"]) for row in baseline["eval"]["checks"]] == [("a", True), ("z", False)]


@pytest.mark.integration
@pytest.mark.parametrize("kind,params,detail", [
    ("first_player_advantage_cap", {"max_allowed": .01}, "first_player_advantage=0.02"),
    ("dominant_strategy_absent", {}, "aggro,combo,control"),
    ("winrate_variance_cap", {"max_spread": .0001}, "spread="),
])
def test_meta_balance_reports_valid_but_unacceptable_policies(tmp_path, kind, params, detail):
    src, out, scenario = tmp_path / "input", tmp_path / "output", tmp_path / "scenario.json"
    _seed_meta_breaker_inputs(src)
    if kind == "dominant_strategy_absent":
        path = src / "rules/meta_breaker_rules.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["balance"]["dominant_threshold"] = .45
        path.write_text(json.dumps(data), encoding="utf-8")
    _pack(scenario, [{"id": "policy", "kind": kind, "hard": True, "params": params}], mode="meta_balance")
    result = _compile(src, out, scenario, mode="meta_balance", route="meta_breaker_v0")
    assert not result.ok and result.hard_fail_count == 1 and result.best_score == 0
    baseline = json.loads((out / "artifacts/candidates/candidate_0000.json").read_text(encoding="utf-8"))
    assert detail in baseline["eval"]["checks"][0]["detail"]
    assert (result.materialized_root / "rules/meta_breaker_rules.json").is_file()
