#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.productflow.productflow_support import (
    build_productflow_engine,
    patched_productflow_provider,
    reset_productflow_runtime_state,
    resolve_productflow_paths,
)
from scripts.productflow.run_governed_write_file_flow import _run as run_productflow_live_flow
from scripts.proof.trusted_run_witness_support import (
    DEFAULT_BUNDLE_NAME,
    DEFAULT_VERIFICATION_OUTPUT,
    PROOF_RESULTS_ROOT,
    blocked_report,
    build_campaign_verification_report,
    build_witness_bundle_payload,
    relative_to_repo,
    verify_witness_bundle_payload,
)

DEFAULT_WORKSPACE_ROOT = REPO_ROOT / "workspace" / "productflow_trusted_run_witness"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the ProductFlow Trusted Run Witness campaign.")
    parser.add_argument("--workspace-root", default=str(DEFAULT_WORKSPACE_ROOT), help="Campaign workspace root.")
    parser.add_argument("--runs", type=int, default=2, help="Number of equivalent ProductFlow executions.")
    parser.add_argument("--output", default=str(DEFAULT_VERIFICATION_OUTPUT), help="Stable verifier report output path.")
    parser.add_argument("--json", action="store_true", help="Print the persisted campaign report.")
    return parser.parse_args(argv)


def _run_campaign(args: argparse.Namespace) -> dict[str, Any]:
    run_count = max(1, int(args.runs))
    base_workspace = Path(str(args.workspace_root)).resolve()
    reports: list[dict[str, Any]] = []
    bundle_refs: list[str] = []
    live_refs: list[str] = []
    original_durable_root = os.environ.get("ORKET_DURABLE_ROOT")
    os.environ.setdefault("ORKET_DISABLE_SANDBOX", "1")
    try:
        for index in range(1, run_count + 1):
            report, bundle_ref, live_ref = _run_one_campaign_execution(base_workspace, index)
            reports.append(report)
            if bundle_ref:
                bundle_refs.append(bundle_ref)
            live_refs.append(live_ref)
    finally:
        if original_durable_root is None:
            os.environ.pop("ORKET_DURABLE_ROOT", None)
        else:
            os.environ["ORKET_DURABLE_ROOT"] = original_durable_root
    return build_campaign_verification_report(reports, bundle_refs=bundle_refs, live_proof_refs=live_refs)


def _run_one_campaign_execution(base_workspace: Path, index: int) -> tuple[dict[str, Any], str, str]:
    workspace = base_workspace / f"run_{index:02d}"
    os.environ["ORKET_DURABLE_ROOT"] = str(workspace / ".orket" / "durable")
    paths = resolve_productflow_paths(workspace)
    reset_productflow_runtime_state(paths)
    with patched_productflow_provider():
        engine = build_productflow_engine(paths)
        live_payload = asyncio.run(run_productflow_live_flow(paths=paths, engine=engine))
        live_path = PROOF_RESULTS_ROOT / f"trusted_run_productflow_live_run_{index:02d}.json"
        live_persisted = write_payload_with_diff_ledger(live_path, live_payload)
        live_ref = relative_to_repo(live_path)
        if live_persisted.get("observed_result") != "success" or not live_persisted.get("run_id"):
            return blocked_report(run_index=index, reason="productflow_live_run_failed", live_payload=live_persisted), "", live_ref
        bundle = asyncio.run(
            build_witness_bundle_payload(paths=paths, engine=engine, run_id=str(live_persisted["run_id"]))
        )
    bundle_path = paths.workspace_root / "runs" / str(bundle["session_id"]) / DEFAULT_BUNDLE_NAME
    persisted_bundle = write_payload_with_diff_ledger(bundle_path, bundle)
    bundle_ref = relative_to_repo(bundle_path)
    report = verify_witness_bundle_payload(persisted_bundle, evidence_ref=bundle_ref)
    return report, bundle_ref, live_ref


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
