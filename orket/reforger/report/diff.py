from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable

from orket.reforger.eval.base import EvalResult


def write_best_vs_baseline_diff(
    *,
    baseline: EvalResult,
    best: EvalResult,
    all_results: dict[str, EvalResult],
    out_path: Path,
) -> dict[str, int]:
    baseline_cases = {row.case_id for row in baseline.failing_cases}
    best_cases = {row.case_id for row in best.failing_cases}
    fixed = len(sorted(baseline_cases - best_cases))
    regressed = len(sorted(best_cases - baseline_cases))
    unchanged = len(sorted(baseline_cases & best_cases))

    counts = _frequent_failures(all_results.values())
    frequent = [f"{case_id} ({count})" for case_id, count in counts[:5]]
    severe = [row.case_id for row in sorted(best.failing_cases, key=lambda x: (-x.severity, x.case_id))[:5]]
    new_failures = [case_id for case_id in sorted(best_cases - baseline_cases)[:5]]

    lines = [
        "# Best vs Baseline",
        "",
        f"- fixed: {fixed}",
        f"- regressed: {regressed}",
        f"- unchanged: {unchanged}",
        "",
        "## Top New Failures",
        "",
    ]
    lines.extend([f"- {item}" for item in new_failures] or ["- <none>"])
    lines.extend(["", "## Top Frequent Failures", ""])
    lines.extend([f"- {item}" for item in frequent] or ["- <none>"])
    lines.extend(["", "## Top Severe Failures", ""])
    lines.extend([f"- {item}" for item in severe] or ["- <none>"])
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"fixed": fixed, "regressed": regressed, "unchanged": unchanged}


def _frequent_failures(results: Iterable[EvalResult]) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for result in results:
        for row in result.failing_cases:
            counter[row.case_id] += 1
    return sorted(counter.items(), key=lambda row: (-row[1], row[0]))

