#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.outward_run_claim_tiers import assign_claim_tier, campaign_evidence

DEFAULT_OUTPUT = Path("benchmarks/results/proof/outward_run_witness_campaign_report.json")


def build_campaign_report(reports: list[dict[str, Any]], *, requested_tier: str = "outward_verifier_stable") -> dict[str, Any]:
    evidence = campaign_evidence(reports)
    assignment = assign_claim_tier(requested_tier, evidence)
    return {
        "schema_version": "outward_run_campaign_report.v1",
        "compare_scope": _compare_scope(reports),
        "run_count": len(reports),
        "accepted_count": int(evidence.get("accepted_report_count") or 0),
        "invariant_signature_stable": bool(evidence.get("invariant_signature_stable")),
        "invariant_signature": str(evidence.get("invariant_signature") or ""),
        "claim_tier_ceiling": assignment["claim_tier_ceiling"],
        "claim_tier_request": requested_tier,
        "claim_tier_assigned": assignment["claim_tier_assigned"],
        "result": assignment["result"],
        "missing_evidence_union": _missing_union(reports, assignment),
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an outward run witness campaign report from verifier reports.")
    parser.add_argument("--report", action="append", default=[], help="Verifier report JSON path. Repeat for campaigns.")
    parser.add_argument("--requested-tier", default="outward_verifier_stable", help="Requested campaign posture.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Stable campaign report path.")
    parser.add_argument("--json", action="store_true", help="Print persisted campaign report.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    reports = [_load_report(Path(path)) for path in args.report]
    report = build_campaign_report(reports, requested_tier=str(args.requested_tier))
    persisted = write_payload_with_diff_ledger(Path(str(args.output)).resolve(), report)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            f"result={persisted.get('result')} assigned={persisted.get('claim_tier_assigned')} "
            f"run_count={persisted.get('run_count')}"
        )
    return 0 if persisted.get("result") == "accepted" else 1


def _load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("campaign report input must be JSON object")
    payload.pop("diff_ledger", None)
    return payload


def _compare_scope(reports: list[dict[str, Any]]) -> str:
    scopes = {str(report.get("compare_scope") or "") for report in reports}
    scopes.discard("")
    return next(iter(scopes)) if len(scopes) == 1 else ""


def _missing_union(reports: list[dict[str, Any]], assignment: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for report in reports:
        missing.extend(str(item) for item in report.get("missing_evidence") or [])
    missing.extend(str(item) for item in assignment.get("missing_evidence") or [])
    return list(dict.fromkeys(item for item in missing if item))


if __name__ == "__main__":
    raise SystemExit(main())
