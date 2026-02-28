from __future__ import annotations

import json
from pathlib import Path

from orket.reforger.optimizer.mutate import MutateOptimizer
from orket.reforger.packs import resolve_pack, write_resolved_pack


def _seed_pack(base: Path) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    (base / "pack.json").write_text('{"id":"base","version":"1.0.0"}\n', encoding="utf-8")
    (base / "system.txt").write_text("- rule one\n- rule two\n", encoding="utf-8")
    (base / "constraints.yaml").write_text("rules: []\n", encoding="utf-8")
    resolved = resolve_pack(base, packs_root=base.parent)
    resolved_dir = base.parent / "resolved"
    write_resolved_pack(resolved, resolved_dir)
    return resolved_dir


def test_mutate_generates_exact_budget_and_stable_ids(tmp_path: Path) -> None:
    baseline = _seed_pack(tmp_path / "base")
    out = tmp_path / "candidates"
    optimizer = MutateOptimizer()
    cands = optimizer.generate(baseline_pack=baseline, mode={"mode_id": "truth_only"}, seed=123, budget=5, out_dir=out)
    assert [path.name for path in cands] == [
        "0001_pack_resolved",
        "0002_pack_resolved",
        "0003_pack_resolved",
        "0004_pack_resolved",
        "0005_pack_resolved",
    ]
    for cand in cands:
        assert (cand / "mutation.json").is_file()


def test_mutate_forbidden_pattern_gate_prevents_injection(tmp_path: Path) -> None:
    baseline = _seed_pack(tmp_path / "base")
    out = tmp_path / "candidates"
    optimizer = MutateOptimizer()
    cands = optimizer.generate(baseline_pack=baseline, mode={"mode_id": "truth_only"}, seed=1, budget=3, out_dir=out)
    for cand in cands:
        system = (cand / "system.txt").read_text(encoding="utf-8")
        assert "IGNORE ALL RULES" not in system
        assert "DISABLE SAFETY" not in system
        payload = json.loads((cand / "mutation.json").read_text(encoding="utf-8"))
        assert "kind" in payload

