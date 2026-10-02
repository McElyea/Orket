"""Integration: public CLI effects with an explicit deterministic model fixture."""
import json

import pytest

from orket.interfaces.orket_bundle_cli import main
from tests.application.test_reforger_cli_layer0 import _seed_base_pack, _seed_mode_and_suite
from tests.reforger.compiler.test_compile_textmystery_v0 import _seed_scenario_pack, _seed_textmystery_inputs

pytestmark = pytest.mark.integration


def _workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "reforge"
    _seed_mode_and_suite(root, "truth_only")
    baseline = root / "packs/base/truth_only"
    _seed_base_pack(baseline)
    suite = root / "suites/truth_only"
    (suite / "cases.jsonl").write_text(json.dumps({"case_id": "known", "prompt": "fixture only",
        "expectations": {"hard": ["output_must_include:APPROVED"], "soft": []}}) + "\n", encoding="utf-8")
    (suite / "fake_outputs.json").write_text(json.dumps({"known": "APPROVED"}), encoding="utf-8")
    return root, baseline


def _run(out, *, baseline=None, save="false"):
    args = ["reforge", "run", "--mode", "truth_only", "--model", "fake", "--seed", "1",
            "--budget", "1", "--optimizer", "noop", "--out", str(out), "--save-best", save]
    if baseline is not None:
        args += ["--baseline", str(baseline)]
    return main(args)


@pytest.mark.parametrize("index_text", [None, "not-json", "[]", '{"other:mode": "retained"}'])
def test_save_best_replaces_previous_contents_and_preserves_valid_foreign_index(tmp_path, monkeypatch, index_text):
    root, baseline = _workspace(tmp_path, monkeypatch)
    index = root / "packs/best_index.json"
    if index_text is not None:
        index.write_text(index_text, encoding="utf-8")
    best = root / "packs/model/fake/truth_only/best"
    best.mkdir(parents=True)
    (best / "stale.txt").write_text("previous selection", encoding="utf-8")
    out = tmp_path / "selected-run"
    assert _run(out, baseline=baseline, save="true") == 0
    assert not (best / "stale.txt").exists()
    assert (best / "system.txt").read_text(encoding="utf-8") == "Follow hard rules.\n"
    retained = json.loads(index.read_text(encoding="utf-8"))
    assert retained["fake:truth_only"] == str(best)
    assert retained.get("other:mode") == ("retained" if index_text and "other:mode" in index_text else None)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["model_id"] == "fake"
    assert "0001" in (out / "eval/scoreboard.csv").read_text(encoding="utf-8")
    assert (out / "diff/best_vs_baseline.md").is_file()


@pytest.mark.parametrize("selection", ["absolute-index", "relative-index", "missing-index-target",
                                        "nonobject-index", "empty-index-value", "explicit-pack-ref"])
def test_baseline_resolution_selects_retained_pack_without_inventing_an_index(tmp_path, monkeypatch, selection):
    root, baseline = _workspace(tmp_path, monkeypatch)
    index = root / "packs/best_index.json"
    assert main(["reforge", "init", "--mode", "truth_only", "--model", "fake", "--from", str(baseline)]) == 0
    (root / "packs/model/fake/truth_only/system.txt").write_text("Model-specific baseline\n", encoding="utf-8")
    if selection == "nonobject-index":
        index.write_text("[]", encoding="utf-8")
    elif selection != "explicit-pack-ref":
        value = {"absolute-index": str(baseline), "relative-index": "base/truth_only",
                 "missing-index-target": "absent", "empty-index-value": " "}[selection]
        index.write_text(json.dumps({"fake:truth_only": value}), encoding="utf-8")
    before = index.read_bytes() if index.exists() else None
    out = tmp_path / "resolved-run"
    assert _run(out, baseline="base/truth_only" if selection == "explicit-pack-ref" else None) == 0
    resolved = (out / "inputs/baseline_pack_resolved/system.txt").read_text(encoding="utf-8")
    uses_indexed_base = selection in {"absolute-index", "relative-index", "explicit-pack-ref"}
    assert resolved == ("Follow hard rules.\n" if uses_indexed_base else "Model-specific baseline\n")
    assert (index.read_bytes() if index.exists() else None) == before


def test_init_preserves_local_pack_text_on_repeat_and_supports_logical_parent(tmp_path, monkeypatch):
    root, _ = _workspace(tmp_path, monkeypatch)
    args = ["reforge", "init", "--mode", "truth_only", "--model", "fake", "--from", "base/truth_only"]
    assert main(args) == 0
    target = root / "packs/model/fake/truth_only"
    (target / "system.txt").write_text("Operator constraints\n", encoding="utf-8")
    (target / "constraints.yaml").write_text("rules: [retain]\n", encoding="utf-8")
    assert main(args) == 0
    assert json.loads((target / "pack.json").read_text(encoding="utf-8"))["extends"] == "base/truth_only"
    assert (target / "system.txt").read_text(encoding="utf-8") == "Operator constraints\n"
    assert (target / "constraints.yaml").read_text(encoding="utf-8") == "rules: [retain]\n"


@pytest.mark.parametrize("invalid", [False, True])
def test_compile_cli_returns_native_candidate_outcome_with_retained_report(tmp_path, invalid):
    src, out, scenario = tmp_path / "input", tmp_path / "output", tmp_path / "scenario.json"
    _seed_textmystery_inputs(src, invalid_npc_archetype=invalid)
    _seed_scenario_pack(scenario)
    code = main(["reforge", "compile", "textmystery_persona_v0", "--in", str(src), "--out", str(out),
                 "--mode", "truth_only", "--model", "fake", "--scenario-pack", str(scenario)])
    assert code == int(invalid)
    report = json.loads((out / "artifacts/route_plan.json").read_text(encoding="utf-8"))
    assert bool(report["errors"]) is invalid
    assert (out / "artifacts/final_score_report.json").exists() is (not invalid)


@pytest.mark.parametrize("run_exists", [False, True])
def test_open_last_without_report_has_no_publication_side_effect(tmp_path, monkeypatch, run_exists):
    monkeypatch.chdir(tmp_path)
    if run_exists:
        (tmp_path / "reforge/runs/last").mkdir(parents=True)
    assert main(["reforge", "open", "last"]) == 0
    assert not list(tmp_path.rglob("*.md"))
