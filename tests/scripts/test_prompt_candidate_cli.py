from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/prompt_lab/compare_candidates.py"


def _compare(tmp_path: Path, *, passed: int = 10, extra: tuple[str, ...] = ()) -> subprocess.CompletedProcess:
    metrics = tmp_path / "metrics.json"
    metrics.write_text("{}", encoding="utf-8")
    patterns = tmp_path / "patterns.json"
    patterns.write_text(
        json.dumps({"completion_by_model": {"fixture": {"passed": passed, "failed": 10 - passed}}}),
        encoding="utf-8",
    )
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--stable-eval", str(metrics), "--candidate-eval", str(metrics),
         "--stable-patterns", str(patterns), "--candidate-patterns", str(patterns), *extra],
        cwd=tmp_path, capture_output=True, text=True, timeout=20, check=False,
    )


@pytest.mark.integration
@pytest.mark.parametrize("passed,expected_exit", [(10, 0), (9, 1)])
# Layer: integration
def test_default_thresholds_apply_outside_repository(tmp_path: Path, passed: int, expected_exit: int) -> None:
    """Layer: integration. The real CLI loads its tracked defaults and enforces absolute guard criteria."""
    result = _compare(tmp_path, passed=passed)
    assert result.returncode == expected_exit, result.stderr
    report = json.loads(result.stdout)
    assert report["thresholds"]["candidate_guard_pass_rate_min"] == 0.95
    assert len(report["criteria"]) == 4
    assert report["criteria"]["candidate_guard_pass_rate_min"] is (passed == 10)
    assert report["pass"] is (expected_exit == 0)


@pytest.mark.integration
@pytest.mark.parametrize("content", [None, "{", "[]"])
# Layer: integration
def test_unreadable_threshold_override_is_not_a_gate_pass(tmp_path: Path, content: str | None) -> None:
    """Layer: integration. Missing/invalid configuration fails before reporting or overwriting prior results."""
    thresholds = tmp_path / "thresholds.json"
    if content is not None:
        thresholds.write_text(content, encoding="utf-8")
    output = tmp_path / "comparison.json"
    output.write_text("prior result", encoding="utf-8")
    result = _compare(tmp_path, extra=("--thresholds", str(thresholds), "--out", str(output)))
    assert result.returncode == 2, result.stderr
    assert "thresholds" in result.stderr.lower()
    assert result.stdout == ""
    assert output.read_text(encoding="utf-8") == "prior result"
