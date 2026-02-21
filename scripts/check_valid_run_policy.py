from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate default valid-run frontier/recommendation policy from quant summary.")
    parser.add_argument("--summary", required=True, help="Path to quant sweep summary JSON.")
    parser.add_argument("--out", default="", help="Optional output path for report JSON.")
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Summary must be a JSON object.")
    return payload


def main() -> int:
    args = _parse_args()
    summary = _load(Path(args.summary))
    failures: list[str] = []
    checked_sessions = 0

    sessions = summary.get("sessions") if isinstance(summary.get("sessions"), list) else []
    for s_idx, session in enumerate(sessions):
        if not isinstance(session, dict):
            failures.append(f"sessions:{s_idx}:invalid_type")
            continue
        checked_sessions += 1
        rows = session.get("per_quant") if isinstance(session.get("per_quant"), list) else []
        by_quant = {
            str(row.get("quant_tag") or "").strip(): row
            for row in rows
            if isinstance(row, dict) and str(row.get("quant_tag") or "").strip()
        }
        frontier = session.get("efficiency_frontier") if isinstance(session.get("efficiency_frontier"), dict) else {}
        min_quant = str(frontier.get("minimum_viable_quant_tag") or "").strip()
        if min_quant:
            row = by_quant.get(min_quant)
            if not isinstance(row, dict):
                failures.append(f"sessions:{s_idx}:frontier_missing_quant:{min_quant}")
            elif bool(row.get("valid")) is not True:
                failures.append(f"sessions:{s_idx}:frontier_quant_not_valid:{min_quant}")

        recommendation_detail = (
            session.get("recommendation_detail")
            if isinstance(session.get("recommendation_detail"), dict)
            else {}
        )
        rec_quant = str(recommendation_detail.get("minimum_viable_quant") or "").strip()
        if rec_quant:
            row = by_quant.get(rec_quant)
            if not isinstance(row, dict):
                failures.append(f"sessions:{s_idx}:recommendation_missing_quant:{rec_quant}")
            elif bool(row.get("valid")) is not True:
                failures.append(f"sessions:{s_idx}:recommendation_quant_not_valid:{rec_quant}")

    report = {
        "status": "PASS" if not failures else "FAIL",
        "summary": str(Path(args.summary)).replace("\\", "/"),
        "checked_sessions": checked_sessions,
        "failures": failures,
    }
    text = json.dumps(report, indent=2)
    print(text)
    out_text = str(args.out or "").strip()
    if out_text:
        out_path = Path(out_text)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())

