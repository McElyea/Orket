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
from scripts.proof.trusted_run_proof_foundation import (
    DEFAULT_PROOF_FOUNDATION_OUTPUT,
    build_trusted_run_proof_foundation_report,
)
from scripts.proof.trusted_run_witness_contract import relative_to_repo


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the trusted-run proof foundation Workstream 1 artifact.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_PROOF_FOUNDATION_OUTPUT),
        help="Stable proof-foundation output path.",
    )
    parser.add_argument("--json", action="store_true", help="Print the persisted proof-foundation report.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    output_path = Path(str(args.output)).resolve()
    report = build_trusted_run_proof_foundation_report()
    persisted = write_payload_with_diff_ledger(output_path, report)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={persisted.get('observed_result')}",
                    f"target_count={len(persisted.get('foundation_targets') or [])}",
                    f"output={relative_to_repo(output_path)}",
                ]
            )
        )
    return 0 if persisted.get("observed_result") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
