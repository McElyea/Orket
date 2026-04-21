#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.proof.governed_change_packet_contract import (
    DEFAULT_GOVERNED_CHANGE_PACKET_KERNEL_MODEL_OUTPUT,
    DEFAULT_GOVERNED_CHANGE_PACKET_OUTPUT,
    DEFAULT_GOVERNED_CHANGE_PACKET_VERIFIER_OUTPUT,
)
from scripts.proof.governed_change_packet_workflow import run_governed_repo_change_packet_flow
from scripts.proof.trusted_repo_change_contract import DEFAULT_WORKSPACE_ROOT


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the governed repo change packet path end to end.")
    parser.add_argument("--workspace-root", default=str(DEFAULT_WORKSPACE_ROOT), help="Fixture workspace root.")
    parser.add_argument("--output", default=str(DEFAULT_GOVERNED_CHANGE_PACKET_OUTPUT), help="Stable packet output path.")
    parser.add_argument(
        "--kernel-output",
        default=str(DEFAULT_GOVERNED_CHANGE_PACKET_KERNEL_MODEL_OUTPUT),
        help="Stable trusted-kernel model output path.",
    )
    parser.add_argument(
        "--verifier-output",
        default=str(DEFAULT_GOVERNED_CHANGE_PACKET_VERIFIER_OUTPUT),
        help="Stable packet-verifier output path.",
    )
    parser.add_argument("--json", action="store_true", help="Print the persisted packet JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    result = run_governed_repo_change_packet_flow(
        workspace_root=Path(str(args.workspace_root)),
        packet_output=Path(str(args.output)),
        kernel_model_output=Path(str(args.kernel_output)),
        verify_output=Path(str(args.verifier_output)),
    )
    packet = result.get("packet") if isinstance(result.get("packet"), dict) else {}
    if args.json:
        print(json.dumps(packet, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={packet.get('observed_result')}",
                    f"claim_ceiling={packet.get('claim_summary', {}).get('current_truthful_claim_ceiling')}",
                    f"packet={result.get('packet_ref')}",
                    f"verifier={result.get('packet_verifier_ref')}",
                ]
            )
        )
    return 0 if packet.get("observed_result") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
