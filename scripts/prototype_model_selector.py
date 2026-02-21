from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prototype model/quant selector from quant sweep summary artifacts.")
    parser.add_argument("--summary", required=True, help="Path to quant sweep summary JSON.")
    parser.add_argument("--out", default="benchmarks/results/quant_sweep/model_selector_prototype.json")
    parser.add_argument("--min-adherence", type=float, default=0.95)
    parser.add_argument("--max-latency", type=float, default=10.0)
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Summary must be a JSON object.")
    return payload


def _utility(row: dict[str, Any]) -> float:
    adherence = float(row.get("adherence_score", 0.0) or 0.0)
    latency = float(row.get("total_latency", 0.0) or 0.0)
    if latency <= 0:
        return 0.0
    return adherence / latency


def main() -> int:
    args = _parse_args()
    summary = _load(Path(args.summary))
    sessions = summary.get("sessions") if isinstance(summary.get("sessions"), list) else []

    candidates: list[dict[str, Any]] = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        model_id = str(session.get("model_id") or "unknown")
        rows = session.get("per_quant") if isinstance(session.get("per_quant"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if bool(row.get("valid")) is not True:
                continue
            adherence = float(row.get("adherence_score", 0.0) or 0.0)
            latency = float(row.get("total_latency", 0.0) or 0.0)
            if adherence < float(args.min_adherence):
                continue
            if latency > float(args.max_latency):
                continue
            entry = {
                "model_id": model_id,
                "quant_tag": str(row.get("quant_tag") or ""),
                "adherence_score": adherence,
                "total_latency": latency,
                "utility": round(_utility(row), 6),
            }
            candidates.append(entry)

    ranked = sorted(
        candidates,
        key=lambda row: (
            float(row.get("utility", 0.0) or 0.0),
            float(row.get("adherence_score", 0.0) or 0.0),
            -float(row.get("total_latency", 0.0) or 0.0),
        ),
        reverse=True,
    )
    selected = ranked[0] if ranked else None

    report = {
        "schema_version": "selector.prototype.v1",
        "summary_path": str(Path(args.summary)).replace("\\", "/"),
        "policy": {
            "min_adherence": float(args.min_adherence),
            "max_latency": float(args.max_latency),
            "valid_runs_only": True,
        },
        "candidate_count": len(ranked),
        "selected": selected,
        "ranked_candidates": ranked,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

