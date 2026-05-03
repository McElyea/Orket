#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger

DEFAULT_INPUT = Path(
    "docs/projects/archive/outward-run-proof-kernel/"
    "2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/"
    "01-assurance-case-index/ASSURANCE_CASE_INDEX_SLICE.md"
)
DEFAULT_OUTPUT = Path("benchmarks/results/proof/outward_run_assurance_case_validation.json")

_INV_PATTERN = re.compile(r"ORP-INV-[0-9]{3}")


def validate_assurance_case(path: Path = DEFAULT_INPUT) -> dict[str, Any]:
    rows = _parse_claim_rows(path.read_text(encoding="utf-8"))
    failures: list[dict[str, Any]] = []
    previous_command = ""
    for row in rows:
        command = row["Verifier Command"]
        if command.strip().lower() == "same":
            command = previous_command
        elif command.strip().lower().startswith("same plus"):
            command = f"{previous_command} {command}"
        else:
            previous_command = command
        failures.extend(_row_failures(row, command))
    return {
        "schema_version": "outward_run_assurance_case_validation.v1",
        "result": "accepted" if not failures else "rejected",
        "claim_count": len(rows),
        "failures": failures,
        "missing_evidence": list(dict.fromkeys(str(item["failure_code"]) for item in failures)),
    }


def _row_failures(row: dict[str, str], command: str) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    claim_id = row.get("Claim ID", "")
    if not _INV_PATTERN.search(row.get("Invariant IDs", "")):
        failures.append(_failure(claim_id, "missing_invariant_ids"))
    authority = row.get("Authority Evidence", "").strip()
    if not authority:
        failures.append(_failure(claim_id, "missing_authority_refs"))
    if "support-only" in authority.lower() or "projection" in authority.lower():
        failures.append(_failure(claim_id, "support_only_authority_substitution"))
    clean_command = command.lower()
    surface = row.get("Operator Surface", "")
    if "verify_outward_run_witness_bundle.py" in clean_command or "--bundle" in clean_command:
        failures.append(_failure(claim_id, "bundle_only_verifier_command"))
    elif surface == "`outward_run_witness_report.v1`" and "--package" not in clean_command:
        failures.append(_failure(claim_id, "package_verifier_required"))
    elif surface == "`outward_run_campaign_report.v1`" and "run_outward_run_witness_campaign.py" not in clean_command:
        failures.append(_failure(claim_id, "campaign_verifier_required"))
    return failures


def _parse_claim_rows(text: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    header_index = next(index for index, line in enumerate(lines) if line.startswith("| Claim ID |"))
    headers = _cells(lines[header_index])
    rows: list[dict[str, str]] = []
    for line in lines[header_index + 2 :]:
        if not line.startswith("|"):
            break
        cells = _cells(line)
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells, strict=True)))
    return rows


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _failure(claim_id: str, code: str) -> dict[str, str]:
    return {"claim_id": claim_id, "failure_code": code}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the outward-run assurance case index.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Assurance case markdown path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Stable validation output path.")
    parser.add_argument("--json", action="store_true", help="Print persisted validation JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = validate_assurance_case(Path(str(args.input)))
    persisted = write_payload_with_diff_ledger(Path(str(args.output)).resolve(), report)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(f"result={persisted.get('result')} failures={len(persisted.get('failures') or [])}")
    return 0 if persisted.get("result") == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
