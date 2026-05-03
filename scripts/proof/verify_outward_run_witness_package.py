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
from scripts.proof.outward_run_witness_contract import COMPARE_SCOPE, DEFAULT_PROOF_OUTPUT
from scripts.proof.outward_run_invariant_checker import evaluate_outward_run_invariants
from scripts.proof.outward_run_witness_package import load_witness_package
from scripts.proof.outward_run_witness_report import build_report, rejected_report


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify an outward run witness package offline.")
    parser.add_argument("--package", dest="package_path", help="Path to outward_run_witness_package.v1 directory.")
    parser.add_argument("--scope", default=COMPARE_SCOPE, help="Admitted outward run compare scope.")
    parser.add_argument("--output", default=str(DEFAULT_PROOF_OUTPUT), help="Stable verifier report output path.")
    parser.add_argument("--json", action="store_true", help="Print the persisted verification report.")
    return parser.parse_args(argv)


def verify_package(package_path: Path | None, *, scope: str = COMPARE_SCOPE) -> dict[str, object]:
    if package_path is None:
        return rejected_report(failure_code="package_required_for_proof", scope=scope)
    loaded = load_witness_package(package_path)
    if not loaded.ok or loaded.package is None:
        return rejected_report(failure_code=str(loaded.failure_code or "package_load_failed"), scope=scope)
    model = evaluate_outward_run_invariants(loaded.package, scope=scope)
    failures = [str(item) for item in model.get("missing_evidence") or []]
    return build_report(
        result="accepted" if model.get("result") == "pass" else "rejected",
        scope=scope,
        bundle=loaded.package.bundle,
        missing_evidence=failures,
        invariant_model={
            "schema_version": model.get("schema_version"),
            "invariants": model.get("invariants") or [],
        },
        invariant_signature=str(model.get("invariant_signature") or ""),
        claim_tier_assigned=str(model.get("claim_tier_assigned") or "none"),
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    package_path = Path(str(args.package_path)).resolve() if args.package_path else None
    output = Path(str(args.output)).resolve()
    report = verify_package(package_path, scope=str(args.scope or COMPARE_SCOPE))
    persisted = write_payload_with_diff_ledger(output, report)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"result={persisted.get('result')}",
                    f"missing_evidence={','.join(str(item) for item in persisted.get('missing_evidence') or [])}",
                    f"output={output}",
                ]
            )
        )
    return 0 if persisted.get("result") == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
