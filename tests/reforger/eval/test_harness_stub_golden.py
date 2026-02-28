from __future__ import annotations

import json
from pathlib import Path

from orket.reforger.eval.runner import AdapterEvalHarness, FakeModelAdapter, FakeModelFixture


def _seed_pack(pack: Path) -> None:
    pack.mkdir(parents=True, exist_ok=True)
    (pack / "system.txt").write_text("Truth only.\n", encoding="utf-8")
    (pack / "constraints.yaml").write_text("rules: []\n", encoding="utf-8")


def test_fake_model_harness_matches_golden_report(tmp_path: Path) -> None:
    here = Path(__file__).resolve().parent
    suite = here / "fixtures" / "suites" / "truth_only"
    golden = here / "fixtures" / "golden_reports" / "truth_only_fake_report.json"
    fixture = FakeModelFixture.from_path(suite / "fake_outputs.json")
    harness = AdapterEvalHarness(FakeModelAdapter(fixture))

    pack = tmp_path / "pack"
    out = tmp_path / "eval"
    _seed_pack(pack)
    result = harness.run(
        model_id="fake",
        mode_id="truth_only",
        pack_path=pack,
        suite_path=suite,
        out_dir=out,
    )
    assert result.hard_fail_count == 0
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert report == json.loads(golden.read_text(encoding="utf-8"))

