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
from scripts.proof.outward_run_witness_contract import COMPARE_SCOPE_DENIED, COMPARE_SCOPE_POLICY_REJECTED
from scripts.proof.verify_outward_run_witness_package import verify_package

DEFAULT_BASE = Path("tests/proof_fixtures/outward_run/base_approved_package")
DEFAULT_DENIAL_BASE = Path("tests/proof_fixtures/outward_run/base_denied_package")
DEFAULT_POLICY_REJECTED_BASE = Path("tests/proof_fixtures/outward_run/base_policy_rejected_package")
DEFAULT_OUTPUT = Path("benchmarks/results/proof/outward_run_corruption_report.json")
DENIAL_CORRUPTIONS = frozenset({"ORP-CORR-030", "ORP-CORR-068"})
POLICY_REJECTED_CORRUPTIONS = frozenset({"ORP-CORR-031"})


def run_corruption_suite(
    *,
    base: Path = DEFAULT_BASE,
    denial_base: Path = DEFAULT_DENIAL_BASE,
    policy_rejected_base: Path = DEFAULT_POLICY_REJECTED_BASE,
) -> dict[str, Any]:
    base_report = verify_package(base)
    denial_base_report = verify_package(denial_base, scope=COMPARE_SCOPE_DENIED) if denial_base.exists() else {"result": "blocked"}
    policy_rejected_base_report = (
        verify_package(policy_rejected_base, scope=COMPARE_SCOPE_POLICY_REJECTED)
        if policy_rejected_base.exists()
        else {"result": "blocked"}
    )
    rows: list[dict[str, Any]] = []
    with TemporaryDirectory(prefix="orket-outward-corruptions-") as raw_tmp:
        tmp = Path(raw_tmp)
        for corruption_id, expected in sorted(EXPECTED_FAILURES.items()):
            source_base = _source_base(
                corruption_id,
                base=base,
                denial_base=denial_base,
                policy_rejected_base=policy_rejected_base,
            )
            scope = _scope_for_corruption(corruption_id)
            if corruption_id in DENIAL_CORRUPTIONS and denial_base_report.get("result") != "accepted":
                rows.append(_blocked_row(corruption_id, "base_denied_package_missing"))
                continue
            if corruption_id in POLICY_REJECTED_CORRUPTIONS and policy_rejected_base_report.get("result") != "accepted":
                rows.append(_blocked_row(corruption_id, "base_policy_rejected_package_missing"))
                continue
            output = tmp / corruption_id
            created = corrupt_package(base=source_base, output=output, corruption_id=corruption_id)
            report = verify_package(output, scope=scope) if scope else verify_package(output)
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
            rows.append(_blocked_row(corruption_id, blocker))
    failed = [row for row in rows if row["status"] == "fail"]
    blockers = [row for row in rows if row["status"] == "blocked"]
    return {
        "schema_version": "outward_run_corruption_suite_report.v1",
        "base_package": str(base),
        "denial_base_package": str(denial_base),
        "policy_rejected_base_package": str(policy_rejected_base),
        "base_result": base_report.get("result"),
        "denial_base_result": denial_base_report.get("result"),
        "policy_rejected_base_result": policy_rejected_base_report.get("result"),
        "result": (
            "accepted"
            if base_report.get("result") == "accepted"
            and denial_base_report.get("result") == "accepted"
            and policy_rejected_base_report.get("result") == "accepted"
            and not failed
            and not blockers
            else "rejected"
        ),
        "implemented_count": len(rows) - len(blockers),
        "blocked_count": len(blockers),
        "failed_count": len(failed),
        "rows": rows,
    }


def _blocked_row(corruption_id: str, blocker: str) -> dict[str, Any]:
    return {
        "corruption_id": corruption_id,
        "status": "blocked",
        "expected_failure_code": blocker,
        "observed_result": "blocked",
        "observed_missing_evidence": [blocker],
        "created": "blocked",
    }


def _source_base(
    corruption_id: str,
    *,
    base: Path,
    denial_base: Path,
    policy_rejected_base: Path,
) -> Path:
    if corruption_id in DENIAL_CORRUPTIONS:
        return denial_base
    if corruption_id in POLICY_REJECTED_CORRUPTIONS:
        return policy_rejected_base
    return base


def _scope_for_corruption(corruption_id: str) -> str | None:
    if corruption_id in DENIAL_CORRUPTIONS:
        return COMPARE_SCOPE_DENIED
    if corruption_id in POLICY_REJECTED_CORRUPTIONS:
        return COMPARE_SCOPE_POLICY_REJECTED
    return None


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the outward run witness package corruption suite.")
    parser.add_argument("--base", default=str(DEFAULT_BASE), help="Base approved package fixture.")
    parser.add_argument("--denial-base", default=str(DEFAULT_DENIAL_BASE), help="Base denied package fixture.")
    parser.add_argument(
        "--policy-rejected-base",
        default=str(DEFAULT_POLICY_REJECTED_BASE),
        help="Base policy-rejected package fixture.",
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Stable corruption report path.")
    parser.add_argument("--json", action="store_true", help="Print persisted report JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = run_corruption_suite(
        base=Path(str(args.base)),
        denial_base=Path(str(args.denial_base)),
        policy_rejected_base=Path(str(args.policy_rejected_base)),
    )
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
