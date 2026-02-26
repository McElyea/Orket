from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple

from orket.kernel.v1.canon import canonical_bytes

from .scoring import aggregate_pairing


def build_report(*, spec_hash: str, spec: Dict[str, Any], run_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    ranking = sorted(
        run_rows,
        key=lambda row: (
            bool(row.get("hard_fail")),
            float(row.get("score_total", 0.0)),
            str(row.get("scenario_id", "")),
            int(row.get("seed", 0)),
            int(row.get("repeat_index", 0)),
        ),
    )

    pair_buckets: Dict[Tuple[Tuple[str, str], ...], List[Dict[str, Any]]] = defaultdict(list)
    for row in run_rows:
        model_map = row.get("model_map", {})
        key = tuple((role, str(model_map.get(role))) for role in sorted(model_map.keys()))
        pair_buckets[key].append(row)

    aggregates: List[Dict[str, Any]] = []
    for key in sorted(pair_buckets.keys()):
        rows = pair_buckets[key]
        aggregate = aggregate_pairing(rows)
        aggregates.append(
            {
                "model_map": {role: model for role, model in key},
                "aggregate": aggregate,
            }
        )
    aggregates.sort(
        key=lambda row: (
            float(row["aggregate"].get("hard_fail_rate") or 0.0),
            float(row["aggregate"].get("mean_score") or 0.0),
            float(row["aggregate"].get("variance_score") or 0.0),
        )
    )

    return {
        "experiment_v": "1.0.0",
        "spec_hash": spec_hash,
        "spec": spec,
        "run_count": len(run_rows),
        "runs": run_rows,
        "ranking": ranking,
        "aggregates_by_model_map": aggregates,
    }


def report_canonical_bytes(report: Dict[str, Any]) -> bytes:
    return canonical_bytes(report)
