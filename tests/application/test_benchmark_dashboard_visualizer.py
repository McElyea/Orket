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


def test_dashboard_markdown_includes_trend_and_leaderboard_sections() -> None:
    mod = _load_script_module("render_benchmark_dashboard_test", "scripts/render_benchmark_dashboard.py")
    trends = {
        "row_count": 1,
        "rows": [
            {
                "source": "benchmarks/results/a.json",
                "venue": "standard",
                "flow": "default",
                "overall_avg_score": 4.7,
                "determinism_rate": 1.0,
                "avg_latency_ms": 20.0,
                "avg_cost_usd": 0.0,
            }
        ],
    }
    leaderboard = {
        "group_count": 1,
        "groups": [
            {
                "schema_version": "v1",
                "policy_version": "v1",
                "entries": [
                    {
                        "rank": 1,
                        "source": "benchmarks/results/a.json",
                        "venue": "standard",
                        "flow": "default",
                        "overall_avg_score": 4.7,
                    }
                ],
            }
        ],
    }
    markdown = mod.build_dashboard_markdown(trends=trends, leaderboard=leaderboard)
    assert "## Trends" in markdown
    assert "## Leaderboard" in markdown
    assert "benchmarks/results/a.json" in markdown
