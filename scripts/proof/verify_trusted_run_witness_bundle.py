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
from scripts.proof.trusted_run_witness_support import (
    DEFAULT_VERIFICATION_OUTPUT,
    relative_to_repo,
    verify_witness_bundle_payload,
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a Trusted Run Witness bundle without rerunning the workflow.")
    parser.add_argument("--bundle", required=True, help="Path to trusted_run_witness_bundle.json.")
    parser.add_argument("--output", default=str(DEFAULT_VERIFICATION_OUTPUT), help="Stable verifier report output path.")
    parser.add_argument("--json", action="store_true", help="Print the persisted verification report.")
    return parser.parse_args(argv)


def _load_bundle(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("trusted_run_bundle_json_object_required")
    return payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    bundle_path = Path(str(args.bundle)).resolve()
    output = Path(str(args.output)).resolve()
    report = verify_witness_bundle_payload(_load_bundle(bundle_path), evidence_ref=relative_to_repo(bundle_path))
    persisted = write_payload_with_diff_ledger(output, report)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={persisted.get('observed_result')}",
                    f"claim_tier={persisted.get('claim_tier')}",
                    f"output={relative_to_repo(output)}",
                ]
            )
        )
    return 0 if persisted.get("observed_result") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
