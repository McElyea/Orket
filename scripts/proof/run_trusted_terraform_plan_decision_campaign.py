#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.trusted_terraform_plan_decision_contract import (
    DEFAULT_CAMPAIGN_OUTPUT,
    DEFAULT_SCENARIO,
    DEFAULT_WORKSPACE_ROOT,
    PROOF_RESULTS_ROOT,
    relative_to_repo,
)
from scripts.proof.trusted_terraform_plan_decision_verifier import build_trusted_terraform_plan_decision_campaign_report
from scripts.proof.trusted_terraform_plan_decision_workflow import execute_trusted_terraform_plan_decision, persist_live_run


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Trusted Terraform Plan Decision verification campaign.")
    parser.add_argument("--workspace-root", default=str(DEFAULT_WORKSPACE_ROOT), help="Workspace root for the proof run.")
    parser.add_argument("--scenario", default=DEFAULT_SCENARIO, choices=sorted({"risky_publish", "degraded_publish"}), help="Success-shaped scenario to repeat.")
    parser.add_argument("--runs", type=int, default=2, help="Number of equivalent executions.")
    parser.add_argument("--output", default=str(DEFAULT_CAMPAIGN_OUTPUT), help="Stable campaign report output path.")
    parser.add_argument("--json", action="store_true", help="Print the persisted campaign report JSON.")
    return parser.parse_args(argv)


def _run_campaign(args: argparse.Namespace) -> dict[str, Any]:
    os.environ.setdefault("ORKET_DISABLE_SANDBOX", "1")
    workspace = Path(str(args.workspace_root))
    reports: list[dict[str, Any]] = []
    bundle_refs: list[str] = []
    live_refs: list[str] = []
    for index in range(1, max(1, int(args.runs)) + 1):
        live = execute_trusted_terraform_plan_decision(workspace_root=workspace, scenario=str(args.scenario), run_index=index)
        live_path = PROOF_RESULTS_ROOT / f"trusted_terraform_plan_decision_live_run_{index:02d}.json"
        persisted_live = persist_live_run(live_path, live)
        report = persisted_live.get("witness_report") if isinstance(persisted_live.get("witness_report"), dict) else {}
        reports.append(report)
        live_refs.append(relative_to_repo(live_path))
        bundle_ref = str(persisted_live.get("witness_bundle_ref") or "")
        if bundle_ref:
            bundle_refs.append(bundle_ref)
    return build_trusted_terraform_plan_decision_campaign_report(reports, bundle_refs=bundle_refs, live_proof_refs=live_refs)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    campaign = _run_campaign(args)
    output = Path(str(args.output)).resolve()
    persisted = write_payload_with_diff_ledger(output, campaign)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={persisted.get('observed_result')}",
                    f"claim_tier={persisted.get('claim_tier')}",
                    f"run_count={persisted.get('run_count')}",
                    f"output={relative_to_repo(output)}",
                ]
            )
        )
    return 0 if persisted.get("observed_result") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
