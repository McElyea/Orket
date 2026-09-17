from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from orket.core.contracts.model_timing import nonnegative_duration
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from orket.core.contracts.model_timing import nonnegative_duration
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prototype model/quant selector from quant sweep summary artifacts.")
    parser.add_argument("--summary", required=True, help="Path to quant sweep summary JSON.")
    parser.add_argument("--out", default="benchmarks/results/quant/quant_sweep/model_selector_prototype.json")
    parser.add_argument("--min-adherence", type=float, default=0.95)
    parser.add_argument("--max-latency", type=float, default=10.0)
    args = parser.parse_args()
    if (nonnegative_duration(args.min_adherence) is None or args.min_adherence > 1
            or nonnegative_duration(args.max_latency) is None):
        parser.error("E_MODEL_SELECTOR_POLICY_INVALID: require finite 0 <= adherence <= 1 and latency >= 0")
    return args


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Summary must be a JSON object.")
    return payload


def _candidate(row: dict[str, Any], min_adherence: float, max_latency: float) -> tuple[dict[str, Any] | None, str | None]:
    if row.get("valid") is not True:
        return None, "run_not_valid"
    adherence = nonnegative_duration(row.get("adherence_score"))
    latency = nonnegative_duration(row.get("total_latency"))
    if adherence is None or adherence > 1:
        return None, "adherence_unavailable"
    if latency is None:
        return None, "latency_unavailable"
    if adherence < min_adherence:
        return None, "adherence_below_minimum"
    if latency > max_latency:
        return None, "latency_above_maximum"
    utility = nonnegative_duration(adherence / latency if latency > 0 else 0.0)
    if utility is None:
        return None, "utility_unrepresentable"
    return {"adherence_score": adherence, "total_latency": latency, "utility": round(utility, 6)}, None


def _candidates(summary: dict[str, Any], min_adherence: float, max_latency: float) -> tuple[list, list]:
    sessions = summary.get("sessions")
    if not isinstance(sessions, list):
        raise ValueError("E_MODEL_SELECTOR_SESSIONS_INVALID")
    candidates, rejected = [], []
    for session in sessions:
        if not isinstance(session, dict) or not isinstance(session.get("per_quant"), list):
            raise ValueError("E_MODEL_SELECTOR_SESSION_INVALID")
        model_id = session.get("model_id")
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("E_MODEL_SELECTOR_MODEL_ID_INVALID")
        for row in session["per_quant"]:
            if not isinstance(row, dict):
                raise ValueError("E_MODEL_SELECTOR_CANDIDATE_INVALID")
            identity = {"model_id": model_id, "quant_tag": str(row.get("quant_tag") or "")}
            candidate, reason = _candidate(row, min_adherence, max_latency)
            if candidate is None:
                rejected.append({**identity, "reason": reason})
            else:
                candidates.append({**identity, **candidate})
    return candidates, rejected


def main() -> int:
    args = _parse_args()
    summary = _load(Path(args.summary))
    candidates, rejected = _candidates(summary, args.min_adherence, args.max_latency)

    ranked = sorted(
        candidates,
        key=lambda row: (
            row["utility"], row["adherence_score"], -row["total_latency"],
        ),
        reverse=True,
    )
    selected = ranked[0] if ranked else None

    report = {
        "schema_version": "selector.prototype.v2",
        "summary_path": str(Path(args.summary)).replace("\\", "/"),
        "policy": {
            "min_adherence": float(args.min_adherence),
            "max_latency": float(args.max_latency),
            "valid_runs_only": True,
        },
        "candidate_count": len(ranked),
        "selected": selected,
        "ranked_candidates": ranked,
        "rejected_candidates": rejected,
        "measurement_posture": "reported_unverified",
    }

    out_path = Path(args.out)
    persisted = write_payload_with_diff_ledger(out_path, report)
    print(json.dumps(persisted, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
