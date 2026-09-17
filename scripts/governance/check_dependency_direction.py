"""Fail closed on dependency analysis gaps and nonconforming authority edges."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.governance.dependency_policy import POLICY_PATH, PROJECT_ROOT
from scripts.governance.dependency_report import build_dependency_report, report_summary

OUTPUT_PATH = PROJECT_ROOT / "benchmarks/results/dependency_direction_check.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--policy", type=Path, default=POLICY_PATH)
    parser.add_argument("--out", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    report = build_dependency_report(root=args.root.resolve(), policy_path=args.policy.resolve())
    write_payload_with_diff_ledger(args.out.resolve(), report)
    print(json.dumps(report_summary(report), sort_keys=True))
    print(f"Wrote {args.out}")
    return 0 if report["collection_ok"] and report["verdict"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
