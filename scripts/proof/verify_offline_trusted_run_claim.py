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
from scripts.proof.offline_trusted_run_verifier import (
    CLAIM_ORDER,
    DEFAULT_OFFLINE_VERIFIER_OUTPUT,
    SUPPORTED_INPUT_MODES,
    evaluate_offline_trusted_run_claim,
)
from scripts.proof.trusted_repo_change_contract import TRUSTED_REPO_COMPARE_SCOPE
from scripts.proof.trusted_repo_change_offline import evaluate_trusted_repo_change_offline_claim
from scripts.proof.trusted_run_witness_support import relative_to_repo


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the highest truthful offline Trusted Run claim.")
    parser.add_argument("--input", required=True, help="Path to a witness bundle, verifier report, or campaign report.")
    parser.add_argument(
        "--input-mode",
        choices=sorted(SUPPORTED_INPUT_MODES),
        default="auto",
        help="Input interpretation mode.",
    )
    parser.add_argument(
        "--claim",
        choices=CLAIM_ORDER,
        action="append",
        default=[],
        help="Requested claim tier. May be repeated.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OFFLINE_VERIFIER_OUTPUT),
        help="Stable offline verifier report output path.",
    )
    parser.add_argument("--json", action="store_true", help="Print the persisted offline verifier report.")
    return parser.parse_args(argv)


def _load_json_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("offline_verifier_input_json_object_required")
    return payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    input_path = Path(str(args.input)).resolve()
    output_path = Path(str(args.output)).resolve()
    payload = _load_json_object(input_path)
    evaluator = (
        evaluate_trusted_repo_change_offline_claim
        if payload.get("compare_scope") == TRUSTED_REPO_COMPARE_SCOPE
        else evaluate_offline_trusted_run_claim
    )
    report = evaluator(
        payload,
        input_mode=str(args.input_mode),
        requested_claims=list(args.claim or []),
        evidence_ref=relative_to_repo(input_path),
    )
    persisted = write_payload_with_diff_ledger(output_path, report)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={persisted.get('observed_result')}",
                    f"claim_status={persisted.get('claim_status')}",
                    f"claim_tier={persisted.get('claim_tier')}",
                    f"output={relative_to_repo(output_path)}",
                ]
            )
        )
    return 0 if persisted.get("claim_status") == "allowed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
