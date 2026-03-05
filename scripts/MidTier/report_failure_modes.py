from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict


def parse_log(path: Path) -> Dict[str, Any]:
    counters = Counter()
    failure_by_type = Counter()
    non_progress_by_role = Counter()
    guard_outcomes = Counter()
    retries = 0

    if not path.exists():
        return {
            "events": {},
            "failure_by_type": {},
            "non_progress_by_role": {},
            "guard_outcomes": {},
            "retry_triggered": 0,
        }

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            event = record.get("event", "")
            role = record.get("role", "system")
            data = record.get("data", {}) or {}
            counters[event] += 1

            if event == "turn_failed":
                failure_by_type[data.get("type", "unknown")] += 1
            if event == "turn_non_progress":
                non_progress_by_role[role] += 1
            if event in {"guard_approved", "guard_rejected", "guard_requested_changes"}:
                guard_outcomes[event] += 1
            if event == "retry_triggered":
                retries += 1

    return {
        "events": dict(counters),
        "failure_by_type": dict(failure_by_type),
        "non_progress_by_role": dict(non_progress_by_role),
        "guard_outcomes": dict(guard_outcomes),
        "retry_triggered": retries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize Orket failure and non-progress modes from logs.")
    parser.add_argument("--log", type=str, default="workspace/default/orket.log", help="Path to structured orket log.")
    parser.add_argument("--out", type=str, default="", help="Optional output JSON path.")
    args = parser.parse_args()

    report = parse_log(Path(args.log))
    blob = json.dumps(report, indent=2, ensure_ascii=False)
    print(blob)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(blob, encoding="utf-8")


if __name__ == "__main__":
    main()
