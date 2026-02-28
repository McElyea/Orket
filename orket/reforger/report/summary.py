from __future__ import annotations

from collections import Counter
from pathlib import Path

from orket.reforger.eval.base import EvalResult


def write_summary(
    *,
    out_path: Path,
    timestamp: str,
    seed: int,
    model_id: str,
    mode_id: str,
    budget: int,
    best_candidate_id: str,
    scoreboard: list[dict[str, object]],
    baseline: EvalResult,
    best: EvalResult,
    all_results: dict[str, EvalResult],
    delta_counts: dict[str, int],
) -> None:
    top_n = scoreboard[:5]
    lines: list[str] = [
        "Orket Reforge Summary",
        f"timestamp: {timestamp}",
        f"seed: {seed}",
        f"model: {model_id}",
        f"mode: {mode_id}",
        f"budget: {budget}",
        "",
        f"best_candidate: {best_candidate_id}",
        "",
        "Scoreboard Top N",
    ]
    if top_n:
        for row in top_n:
            lines.append(
                "- {candidate_id}: score={score:.6f}, hard={hard_fail_count}, soft={soft_fail_count}".format(
                    candidate_id=str(row["candidate_id"]),
                    score=float(row["score"]),
                    hard_fail_count=int(row["hard_fail_count"]),
                    soft_fail_count=int(row["soft_fail_count"]),
                )
            )
    else:
        lines.append("- <none>")

    lines.extend(
        [
            "",
            "Delta vs Baseline",
            f"- fixed: {int(delta_counts.get('fixed', 0))}",
            f"- regressed: {int(delta_counts.get('regressed', 0))}",
            f"- unchanged: {int(delta_counts.get('unchanged', 0))}",
            "",
            "Failure Triage",
            "Top 5 New Failures",
        ]
    )
    baseline_set = {row.case_id for row in baseline.failing_cases}
    best_set = {row.case_id for row in best.failing_cases}
    new_failures = sorted(best_set - baseline_set)[:5]
    lines.extend([f"- {item}" for item in new_failures] or ["- <none>"])

    lines.extend(["", "Top 5 Frequent Failures"])
    counter: Counter[str] = Counter()
    for result in all_results.values():
        for row in result.failing_cases:
            counter[row.case_id] += 1
    frequent = sorted(counter.items(), key=lambda row: (-row[1], row[0]))[:5]
    lines.extend([f"- {case_id} ({count})" for case_id, count in frequent] or ["- <none>"])

    lines.extend(["", "Top 5 Most Severe Failures"])
    severe = sorted(best.failing_cases, key=lambda row: (-row.severity, row.case_id))[:5]
    lines.extend([f"- {row.case_id} ({row.severity:.3f})" for row in severe] or ["- <none>"])

    hard_violations = int(best.hard_fail_count)
    status = "PASS" if hard_violations == 0 else "FAIL"
    lines.extend(["", "Hard Constraint Gate", f"- status: {status}", f"- hard_violations: {hard_violations}"])
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

