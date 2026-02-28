from __future__ import annotations

from pathlib import Path

from orket.reforger.eval.base import EvalResult, FailingCase
from orket.reforger.report.diff import write_best_vs_baseline_diff
from orket.reforger.report.summary import write_summary


def _eval(score: float, hard: int, soft: int, cases: list[tuple[str, float, bool]], root: Path) -> EvalResult:
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "r.json"
    md_path = root / "r.md"
    json_path.write_text("{}", encoding="utf-8")
    md_path.write_text("#", encoding="utf-8")
    return EvalResult(
        score=score,
        hard_fail_count=hard,
        soft_fail_count=soft,
        failing_cases=tuple(FailingCase(case_id=i, severity=s, hard=h) for i, s, h in cases),
        report_json_path=json_path,
        report_md_path=md_path,
    )


def test_summary_and_diff_are_deterministic_and_bounded(tmp_path: Path) -> None:
    baseline = _eval(0.5, 1, 2, [("A", 1.0, True), ("B", 0.2, False)], tmp_path / "base")
    best = _eval(0.7, 0, 1, [("B", 0.4, False), ("C", 0.8, True)], tmp_path / "best")
    all_results = {
        "0001": best,
        "0002": _eval(0.6, 1, 0, [("C", 1.0, True)], tmp_path / "r2"),
        "0003": _eval(0.6, 0, 1, [("B", 0.2, False)], tmp_path / "r3"),
    }
    diff_path = tmp_path / "best_vs_baseline.md"
    delta = write_best_vs_baseline_diff(
        baseline=baseline,
        best=best,
        all_results=all_results,
        out_path=diff_path,
    )
    summary_path = tmp_path / "summary.txt"
    write_summary(
        out_path=summary_path,
        timestamp="deterministic",
        seed=1,
        model_id="fake",
        mode_id="truth_only",
        budget=3,
        best_candidate_id="0001",
        scoreboard=[
            {"candidate_id": "0001", "score": 0.7, "hard_fail_count": 0, "soft_fail_count": 1},
            {"candidate_id": "0002", "score": 0.6, "hard_fail_count": 1, "soft_fail_count": 0},
        ],
        baseline=baseline,
        best=best,
        all_results=all_results,
        delta_counts=delta,
    )
    text = summary_path.read_text(encoding="utf-8")
    assert "Top 5 New Failures" in text
    assert text.count("\n- ") < 40
    first = diff_path.read_text(encoding="utf-8")
    second = diff_path.read_text(encoding="utf-8")
    assert first == second
