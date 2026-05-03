#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.corrupt_outward_run_witness_package import (
    EXPECTED_FAILURES,
    MISSING_FIXTURE_CORRUPTIONS,
    corrupt_package,
)
from scripts.proof.verify_outward_run_witness_package import verify_package

DEFAULT_BASE = Path("tests/proof_fixtures/outward_run/base_approved_package")
DEFAULT_OUTPUT = Path("benchmarks/results/proof/outward_run_corruption_report.json")


def run_corruption_suite(*, base: Path = DEFAULT_BASE) -> dict[str, Any]:
    base_report = verify_package(base)
    rows: list[dict[str, Any]] = []
    with TemporaryDirectory(prefix="orket-outward-corruptions-") as raw_tmp:
        tmp = Path(raw_tmp)
        for corruption_id, expected in sorted(EXPECTED_FAILURES.items()):
            output = tmp / corruption_id
            created = corrupt_package(base=base, output=output, corruption_id=corruption_id)
            report = verify_package(output)
            missing = [str(item) for item in report.get("missing_evidence") or []]
            rows.append(
                {
                    "corruption_id": corruption_id,
                    "status": "pass" if expected in missing and report.get("result") == "rejected" else "fail",
                    "expected_failure_code": expected,
                    "observed_result": report.get("result"),
                    "observed_missing_evidence": missing,
                    "created": created.get("result"),
                }
            )
        for corruption_id, blocker in sorted(MISSING_FIXTURE_CORRUPTIONS.items()):
            rows.append(
                {
                    "corruption_id": corruption_id,
                    "status": "blocked",
                    "expected_failure_code": blocker,
                    "observed_result": "blocked",
                    "observed_missing_evidence": [blocker],
                    "created": "blocked",
                }
            )
    failed = [row for row in rows if row["status"] == "fail"]
    blockers = [row for row in rows if row["status"] == "blocked"]
    return {
        "schema_version": "outward_run_corruption_suite_report.v1",
        "base_package": str(base),
        "base_result": base_report.get("result"),
        "result": "accepted" if base_report.get("result") == "accepted" and not failed else "rejected",
        "implemented_count": len(rows) - len(blockers),
        "blocked_count": len(blockers),
        "failed_count": len(failed),
        "rows": rows,
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the outward run witness package corruption suite.")
    parser.add_argument("--base", default=str(DEFAULT_BASE), help="Base approved package fixture.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Stable corruption report path.")
    parser.add_argument("--json", action="store_true", help="Print persisted report JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = run_corruption_suite(base=Path(str(args.base)))
    persisted = write_payload_with_diff_ledger(Path(str(args.output)).resolve(), report)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            f"result={persisted.get('result')} implemented={persisted.get('implemented_count')} "
            f"blocked={persisted.get('blocked_count')} failed={persisted.get('failed_count')}"
        )
    return 0 if persisted.get("result") == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
