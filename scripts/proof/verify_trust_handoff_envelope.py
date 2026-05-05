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

from orket.application.services.trust_handoff_verifier import verify_trust_handoff_package

DEFAULT_OUTPUT = Path("benchmarks/results/proof/trust_handoff_verifier_report.json")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a Packet 1 trust handoff envelope package offline.")
    parser.add_argument("--package", dest="package_path", required=True, help="Path to trust handoff package directory.")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT), help="Stable verifier report output path.")
    parser.add_argument("--json", action="store_true", help="Print persisted verifier report JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    output = Path(str(args.out)).resolve()
    report = verify_trust_handoff_package(Path(str(args.package_path)))
    persisted = write_payload_with_diff_ledger(output, report)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"result={persisted.get('result')}",
                    f"rejection_reason={persisted.get('rejection_reason')}",
                    f"output={output}",
                ]
            )
        )
    return 0 if persisted.get("result") == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
