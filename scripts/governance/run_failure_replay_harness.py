from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.failure_replay_harness_contract import (
    failure_replay_harness_contract_snapshot,
)
from orket.runtime.replay_drift_classifier import classify_replay_drift

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - script execution fallback
    import importlib.util

    helper_path = Path(__file__).resolve().parents[1] / "common" / "rerun_diff_ledger.py"
    spec = importlib.util.spec_from_file_location("rerun_diff_ledger", helper_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive fallback
        raise RuntimeError(f"E_DIFF_LEDGER_HELPER_LOAD_FAILED:{helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    write_payload_with_diff_ledger = module.write_payload_with_diff_ledger


VOLATILE_TOP_LEVEL_FIELDS = {"recorded_at", "artifact_id"}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run failure replay harness against two replay artifacts.")
    parser.add_argument("--baseline", required=True, help="Baseline replay artifact path.")
    parser.add_argument("--candidate", required=True, help="Candidate replay artifact path.")
    parser.add_argument("--out", default="", help="Optional output JSON path.")
    parser.add_argument(
        "--max-differences",
        type=int,
        default=int(failure_replay_harness_contract_snapshot()["max_reported_differences"]),
        help="Maximum differences to retain in output report.",
    )
    return parser.parse_args(argv)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_value(value: Any) -> str:
    rendered = json.dumps(value, ensure_ascii=True, sort_keys=True)
    if len(rendered) > 160:
        return rendered[:157] + "..."
    return rendered


def _compare_values(*, baseline: Any, candidate: Any, path: str, differences: list[dict[str, str]]) -> None:
    if type(baseline) is not type(candidate):
        differences.append(
            {
                "field": path,
                "reason": "type_mismatch",
                "baseline": type(baseline).__name__,
                "candidate": type(candidate).__name__,
            }
        )
        return

    if isinstance(baseline, dict):
        baseline_keys = set(baseline.keys())
        candidate_keys = set(candidate.keys())
        for key in sorted(baseline_keys | candidate_keys):
            if not path and key in VOLATILE_TOP_LEVEL_FIELDS:
                continue
            field = f"{path}.{key}" if path else key
            if key not in baseline:
                differences.append(
                    {
                        "field": field,
                        "reason": "missing_baseline",
                        "baseline": "<missing>",
                        "candidate": "present",
                    }
                )
                continue
            if key not in candidate:
                differences.append(
                    {
                        "field": field,
                        "reason": "missing_candidate",
                        "baseline": "present",
                        "candidate": "<missing>",
                    }
                )
                continue
            _compare_values(
                baseline=baseline[key],
                candidate=candidate[key],
                path=field,
                differences=differences,
            )
        return

    if isinstance(baseline, list):
        if len(baseline) != len(candidate):
            differences.append(
                {
                    "field": path,
                    "reason": "length_mismatch",
                    "baseline": str(len(baseline)),
                    "candidate": str(len(candidate)),
                }
            )
            return
        for index, (baseline_item, candidate_item) in enumerate(zip(baseline, candidate)):
            _compare_values(
                baseline=baseline_item,
                candidate=candidate_item,
                path=f"{path}[{index}]",
                differences=differences,
            )
        return

    if baseline != candidate:
        differences.append(
            {
                "field": path,
                "reason": "value_mismatch",
                "baseline": _format_value(baseline),
                "candidate": _format_value(candidate),
            }
        )


def evaluate_failure_replay_harness(
    *,
    baseline_path: Path,
    candidate_path: Path,
    max_differences: int,
) -> dict[str, Any]:
    if max_differences < 1:
        raise ValueError("max_differences must be >= 1")

    baseline_payload = _load_json(baseline_path)
    candidate_payload = _load_json(candidate_path)
    if not isinstance(baseline_payload, dict) or not isinstance(candidate_payload, dict):
        raise ValueError("baseline and candidate replay artifacts must be JSON objects")

    differences: list[dict[str, str]] = []
    _compare_values(
        baseline=baseline_payload,
        candidate=candidate_payload,
        path="",
        differences=differences,
    )
    differences = sorted(differences, key=lambda row: (row.get("field", ""), row.get("reason", "")))
    drift = classify_replay_drift(differences=[{"field": row.get("field")} for row in differences])
    primary_layer = str(drift.get("primary_layer") or "none")
    if not differences:
        path = "primary"
    elif primary_layer in {"artifact_formatting_drift", "prompt_drift"}:
        path = "degraded"
    else:
        path = "blocked"
    return {
        "schema_version": "failure_replay_harness.v1",
        "ok": not differences,
        "path": path,
        "baseline": str(baseline_path),
        "candidate": str(candidate_path),
        "difference_count": len(differences),
        "differences": differences[:max_differences],
        "differences_truncated": len(differences) > max_differences,
        "drift": drift,
    }


def run_failure_replay_harness(
    *,
    baseline_path: Path,
    candidate_path: Path,
    out_path: Path | None,
    max_differences: int,
) -> tuple[int, dict[str, Any]]:
    payload = evaluate_failure_replay_harness(
        baseline_path=baseline_path,
        candidate_path=candidate_path,
        max_differences=max_differences,
    )
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 2), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    baseline_path = Path(args.baseline).resolve()
    candidate_path = Path(args.candidate).resolve()
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = run_failure_replay_harness(
        baseline_path=baseline_path,
        candidate_path=candidate_path,
        out_path=out_path,
        max_differences=int(args.max_differences),
    )
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
