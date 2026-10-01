"""Validate source authority and exact generated output; never grant live proof."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.common.git_inventory import GitInventoryError
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.governance.current_authority import REPORT, VIEW, digest, output_path, validate
from scripts.governance.current_authority_view import render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--require-current-proof", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload, sources, bindings = validate(Path(args.repo_root))
        sources.read(VIEW)
        equal = sources.observed[VIEW] == render(payload)
        current = not args.require_current_proof
        failures = ([] if equal else ["generated authority differs"]) + ([] if current else [
            "current proof unavailable: portable runtime evidence adapters are not implemented"])
        report = {"schema_version": "current_authority_check.v1", "proof": "structural",
                  "structural_authority_valid": equal, "current_proof_established": False,
                  "requested_proof_satisfied": current, "failures": failures, "command_bindings": bindings,
                  "source_sha256": {name: digest(data) for name, data in sorted(sources.observed.items())}}
        destination = output_path(sources, REPORT)
        write_payload_with_diff_ledger(destination, report)
        print(json.dumps({key: report[key] for key in ("structural_authority_valid", "current_proof_established",
                                                      "requested_proof_satisfied", "failures")}))
        return int(bool(failures))
    except (ValueError, OSError, UnicodeError, SyntaxError, GitInventoryError) as exc:
        # Incomplete source admission cannot authorize replacing a prior report.
        print(f"authority validation refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
