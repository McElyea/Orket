from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _index_by_run(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        run_id = str(row.get("run_id") or "").strip()
        if run_id:
            indexed[run_id] = row
    return indexed


def score(eval_payload: dict[str, Any], gold_payload: dict[str, Any]) -> dict[str, Any]:
    eval_runs = _index_by_run(list(eval_payload.get("runs", [])))
    gold_runs = _index_by_run(list(gold_payload.get("runs", [])))
    shared_ids = sorted(set(eval_runs.keys()) & set(gold_runs.keys()))

    false_stop_cases = 0
    overrun_cases = 0
    loop_miss_cases = 0
    format_miss_cases = 0

    counted_false_stop = 0
    counted_overrun = 0
    counted_loop = 0
    counted_format = 0

    details: list[dict[str, Any]] = []
    for run_id in shared_ids:
        eval_row = eval_runs[run_id]
        gold_row = gold_runs[run_id]
        eval_outcome = str(eval_row.get("final_outcome_eval") or "")
        eval_stop_round = len(list(eval_row.get("rounds", [])))
        first_good_round = gold_row.get("first_good_enough_round")
        final_gold = gold_row.get("final_outcome_gold")

        false_stop = False
        if isinstance(first_good_round, int):
            counted_false_stop += 1
            false_stop = eval_stop_round < first_good_round
            false_stop_cases += int(false_stop)

        overrun = False
        if isinstance(first_good_round, int):
            counted_overrun += 1
            overrun = eval_stop_round > (first_good_round + 1)
            overrun_cases += int(overrun)

        loop_miss = False
        if isinstance(final_gold, str) and final_gold.strip():
            if final_gold == "LOOP_DETECTED":
                counted_loop += 1
                loop_miss = eval_outcome != "LOOP_DETECTED"
                loop_miss_cases += int(loop_miss)

        format_miss = False
        if isinstance(final_gold, str) and final_gold.strip():
            if final_gold == "FORMAT_VIOLATION":
                counted_format += 1
                format_miss = eval_outcome != "FORMAT_VIOLATION"
                format_miss_cases += int(format_miss)

        details.append(
            {
                "run_id": run_id,
                "eval_outcome": eval_outcome,
                "gold_outcome": final_gold,
                "eval_stop_round": eval_stop_round,
                "first_good_enough_round": first_good_round,
                "false_stop": false_stop,
                "overrun": overrun,
                "loop_miss": loop_miss,
                "format_miss": format_miss,
            }
        )

    false_stop_rate = (false_stop_cases / counted_false_stop) if counted_false_stop > 0 else 0.0
    overrun_rate = (overrun_cases / counted_overrun) if counted_overrun > 0 else 0.0
    loop_miss_rate = (loop_miss_cases / counted_loop) if counted_loop > 0 else 0.0
    format_miss_rate = (format_miss_cases / counted_format) if counted_format > 0 else 0.0
    loss = 2.0 * false_stop_rate + overrun_rate + loop_miss_rate + format_miss_rate

    return {
        "schema_version": "odr.calibration.score.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "counts": {
            "shared_runs": len(shared_ids),
            "counted_false_stop": counted_false_stop,
            "counted_overrun": counted_overrun,
            "counted_loop": counted_loop,
            "counted_format": counted_format,
        },
        "rates": {
            "false_stop_rate": false_stop_rate,
            "overrun_rate": overrun_rate,
            "loop_miss_rate": loop_miss_rate,
            "format_miss_rate": format_miss_rate,
        },
        "loss": loss,
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score ODR calibration evaluation against gold labels.")
    parser.add_argument("--eval", default="benchmarks/results/odr_calibration/evaluation_v1.json")
    parser.add_argument("--gold", default="benchmarks/results/odr_calibration/gold_labels_v1.json")
    parser.add_argument("--out", default="benchmarks/results/odr_calibration/score_v1.json")
    args = parser.parse_args()

    eval_payload = json.loads(Path(args.eval).read_text(encoding="utf-8"))
    gold_payload = json.loads(Path(args.gold).read_text(encoding="utf-8"))
    report = score(eval_payload, gold_payload)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} (loss={report['loss']:.6f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
