from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_script_module(module_name: str, script_path: str) -> ModuleType:
    path = Path(script_path)
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_trend_report_includes_required_fields(tmp_path: Path) -> None:
    mod = _load_script_module("report_benchmark_trends_test", "scripts/report_benchmark_trends.py")
    input_path = tmp_path / "scored.json"
    input_path.write_text(
        """{
  "schema_version": "v1",
  "policy_version": "v1",
  "venue": "standard",
  "flow": "default",
  "overall_avg_score": 4.5
}
""",
        encoding="utf-8",
    )

    report = mod.build_trend_report([input_path])
    assert report["row_count"] == 1
    row = report["rows"][0]
    assert row["overall_avg_score"] == 4.5
    assert "determinism_rate" in row
    assert "avg_latency_ms" in row
    assert "avg_cost_usd" in row


def test_leaderboard_groups_by_schema_and_policy(tmp_path: Path) -> None:
    mod = _load_script_module("build_benchmark_leaderboard_test", "scripts/build_benchmark_leaderboard.py")
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(
        """{
  "schema_version": "v1",
  "policy_version": "v1",
  "venue": "standard",
  "flow": "default",
  "overall_avg_score": 4.1
}
""",
        encoding="utf-8",
    )
    b.write_text(
        """{
  "schema_version": "v1",
  "policy_version": "v1",
  "venue": "fast",
  "flow": "default",
  "overall_avg_score": 4.8
}
""",
        encoding="utf-8",
    )

    leaderboard = mod.build_leaderboard([a, b])
    assert leaderboard["group_count"] == 1
    entries = leaderboard["groups"][0]["entries"]
    assert entries[0]["overall_avg_score"] >= entries[1]["overall_avg_score"]
    assert entries[0]["rank"] == 1
