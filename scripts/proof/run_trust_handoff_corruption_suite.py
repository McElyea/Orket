#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.trust_handoff_corruptions import run_trust_handoff_corruption_suite

DEFAULT_OUTPUT = Path("benchmarks/results/proof/trust_handoff_corruption_report.json")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Packet 1 trust handoff package corruption suite.")
    parser.add_argument("--base", required=True, help="Base trust handoff envelope package.")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT), help="Stable corruption report output path.")
    parser.add_argument("--json", action="store_true", help="Print persisted corruption report JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = run_trust_handoff_corruption_suite(base=Path(str(args.base)).resolve())
    output = Path(str(args.out)).resolve()
    persisted = write_payload_with_diff_ledger(output, report)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            f"result={persisted.get('result')} failed={persisted.get('failed_count')} "
            f"accepted_corruptions={persisted.get('accepted_corruption_count')}"
        )
    return 0 if persisted.get("result") == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
