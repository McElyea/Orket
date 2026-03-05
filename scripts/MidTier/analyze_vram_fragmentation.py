from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Experimental VRAM fragmentation analyzer for quant sweep summaries.")
    parser.add_argument("--summary", required=True, help="Path to quant sweep summary JSON.")
    parser.add_argument("--out", default="benchmarks/results/quant_sweep/vram_fragmentation_analysis.json")
    parser.add_argument("--high-risk-threshold", type=float, default=0.25)
    parser.add_argument("--medium-risk-threshold", type=float, default=0.10)
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Summary must be a JSON object")
    return payload


def _risk_label(score: float, *, high: float, medium: float) -> str:
    if score >= float(high):
        return "HIGH"
    if score >= float(medium):
        return "MEDIUM"
    return "LOW"


def main() -> int:
    args = _parse_args()
    summary = _load(Path(args.summary))
    sessions = summary.get("sessions") if isinstance(summary.get("sessions"), list) else []

    by_model: list[dict[str, Any]] = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        model_id = str(session.get("model_id") or "unknown")
        rows = session.get("per_quant") if isinstance(session.get("per_quant"), list) else []
        utilizations: list[float] = []
        headroom_samples: list[float] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            sidecar = row.get("hardware_sidecar") if isinstance(row.get("hardware_sidecar"), dict) else {}
            total = sidecar.get("vram_total_mb")
            used = sidecar.get("vram_used_mb")
            if not isinstance(total, (int, float)) or not isinstance(used, (int, float)) or float(total) <= 0:
                continue
            utilization = max(0.0, min(1.0, float(used) / float(total)))
            utilizations.append(utilization)
            headroom_samples.append(max(0.0, float(total) - float(used)))

        if not utilizations:
            by_model.append(
                {
                    "model_id": model_id,
                    "sample_count": 0,
                    "fragmentation_score": 0.0,
                    "risk": "UNKNOWN",
                    "reason": "no_sidecar_vram_samples",
                }
            )
            continue

        max_util = max(utilizations)
        min_util = min(utilizations)
        spread = max_util - min_util
        score = round(float(spread), 6)
        by_model.append(
            {
                "model_id": model_id,
                "sample_count": len(utilizations),
                "max_utilization": round(max_util, 6),
                "min_utilization": round(min_util, 6),
                "avg_utilization": round(sum(utilizations) / len(utilizations), 6),
                "avg_headroom_mb": round(sum(headroom_samples) / len(headroom_samples), 3) if headroom_samples else 0.0,
                "fragmentation_score": score,
                "risk": _risk_label(score, high=float(args.high_risk_threshold), medium=float(args.medium_risk_threshold)),
                "reason": "utilization_spread_heuristic",
            }
        )

    report = {
        "schema_version": "vram.fragmentation.v1",
        "summary_path": str(Path(args.summary)).replace("\\", "/"),
        "thresholds": {
            "high_risk_threshold": float(args.high_risk_threshold),
            "medium_risk_threshold": float(args.medium_risk_threshold),
        },
        "models": by_model,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

