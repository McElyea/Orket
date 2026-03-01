from __future__ import annotations

import json
from pathlib import Path

from orket.reforger.compiler import run_compile_pipeline
from orket.reforger.routes.meta_breaker_v0 import MetaBreakerRouteV0


def _seed_meta_breaker_inputs(root: Path) -> None:
    rules_dir = root / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "archetypes": {
            "aggro": {"vs": {"aggro": 0.50, "control": 0.54, "combo": 0.48}},
            "control": {"vs": {"aggro": 0.46, "control": 0.50, "combo": 0.56}},
            "combo": {"vs": {"aggro": 0.52, "control": 0.44, "combo": 0.50}},
        },
        "balance": {
            "first_player_advantage": 0.02,
            "dominant_threshold": 0.55,
        },
    }
    (rules_dir / "meta_breaker_rules.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_scenario_pack(path: Path) -> None:
    payload = {
        "pack_id": "meta_balance_fixture",
        "version": "1.0.0",
        "mode": "meta_balance",
        "tests": [
            {"id": "MB_001", "kind": "matrix_bounds", "hard": True, "weight": 1.0},
            {"id": "MB_002", "kind": "first_player_advantage_cap", "hard": True, "weight": 1.0, "params": {"max_allowed": 0.08}},
            {"id": "MB_003", "kind": "dominant_strategy_absent", "hard": False, "weight": 0.6},
            {"id": "MB_004", "kind": "winrate_variance_cap", "hard": False, "weight": 0.4, "params": {"max_spread": 0.15}},
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_meta_breaker_route_roundtrip_is_canonical(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed_meta_breaker_inputs(src)
    route = MetaBreakerRouteV0()
    blob1 = route.normalize(src)
    out = tmp_path / "materialized"
    route.materialize(blob1, out)
    blob2 = route.normalize(out)
    assert route.canonical_json(blob1) == route.canonical_json(blob2)


def test_compile_pipeline_meta_balance_is_deterministic(tmp_path: Path) -> None:
    src = tmp_path / "src"
    out = tmp_path / "out"
    scenario = tmp_path / "scenario_pack.json"
    _seed_meta_breaker_inputs(src)
    _seed_scenario_pack(scenario)
    first = run_compile_pipeline(
        route_id="meta_breaker_v0",
        input_dir=src,
        out_dir=out,
        mode="meta_balance",
        model_id="fake",
        seed=4,
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
        route_id="meta_breaker_v0",
        input_dir=src,
        out_dir=out,
        mode="meta_balance",
        model_id="fake",
        seed=4,
        max_iters=4,
        scenario_pack_path=scenario,
    )
    assert second.ok
    assert snapshot["final_score"] == _json(out / "artifacts" / "final_score_report.json")
    assert snapshot["digests"] == _json(out / "artifacts" / "bundle_digests.json")
    assert snapshot["route_plan"] == _json(out / "artifacts" / "route_plan.json")
    assert snapshot["outputs_manifest"] == _json(out / "artifacts" / "outputs_manifest.json")
