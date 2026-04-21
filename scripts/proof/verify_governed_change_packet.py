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
from scripts.proof.governed_change_packet_contract import (
    DEFAULT_GOVERNED_CHANGE_PACKET_OUTPUT,
    DEFAULT_GOVERNED_CHANGE_PACKET_VERIFIER_OUTPUT,
    load_json_object,
)
from scripts.proof.governed_change_packet_verifier import verify_governed_change_packet_payload
from scripts.proof.trusted_repo_change_contract import relative_to_repo


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a governed change packet without trusting the full runtime.")
    parser.add_argument("--input", default=str(DEFAULT_GOVERNED_CHANGE_PACKET_OUTPUT), help="Packet input path.")
    parser.add_argument("--output", default=str(DEFAULT_GOVERNED_CHANGE_PACKET_VERIFIER_OUTPUT), help="Stable verifier output path.")
    parser.add_argument("--json", action="store_true", help="Print the persisted verifier report JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    input_path = Path(str(args.input)).resolve()
    output_path = Path(str(args.output)).resolve()
    packet = load_json_object(input_path)
    report = verify_governed_change_packet_payload(packet, evidence_ref=relative_to_repo(input_path))
    persisted = write_payload_with_diff_ledger(output_path, report)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={persisted.get('observed_result')}",
                    f"packet_verdict={persisted.get('packet_verdict')}",
                    f"claim_tier={persisted.get('claim_tier')}",
                    f"output={relative_to_repo(output_path)}",
                ]
            )
        )
    return 0 if persisted.get("packet_verdict") == "valid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
