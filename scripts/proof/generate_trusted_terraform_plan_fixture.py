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
from scripts.proof.trusted_terraform_plan_decision_contract import now_utc_iso, relative_to_repo
from scripts.proof.trusted_terraform_plan_fixtures import (
    build_plan_fixture,
    normalize_fixture_kind,
    write_plan_fixture,
)

DEFAULT_OUTPUT_DIR = REPO_ROOT / "workspace" / "trusted_terraform_live_setup"
DEFAULT_PLAN_NAME = "terraform-plan.json"
DEFAULT_METADATA_NAME = "terraform-plan-fixture-metadata.json"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a bounded Terraform JSON plan fixture for NorthStar smoke.")
    parser.add_argument("--fixture-kind", default="safe", choices=["safe", "risky", "safe_create_update", "risky_delete_replace"])
    parser.add_argument("--fixture-seed", required=True)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--plan-output", default="")
    parser.add_argument("--metadata-output", default="")
    parser.add_argument("--json", action="store_true", help="Print persisted metadata JSON.")
    return parser.parse_args(argv)


def generate_fixture_files(
    *,
    fixture_kind: str,
    fixture_seed: str,
    output_dir: Path,
    plan_output: Path | None = None,
    metadata_output: Path | None = None,
) -> dict:
    output_dir = output_dir.resolve()
    plan_path = (plan_output or (output_dir / DEFAULT_PLAN_NAME)).resolve()
    metadata_path = (metadata_output or (output_dir / DEFAULT_METADATA_NAME)).resolve()
    fixture = build_plan_fixture(fixture_kind=fixture_kind, fixture_seed=fixture_seed)
    write_plan_fixture(plan_path, fixture.plan_payload)
    metadata = {
        **fixture.metadata,
        "recorded_at_utc": now_utc_iso(),
        "plan_path": relative_to_repo(plan_path),
        "metadata_path": relative_to_repo(metadata_path),
    }
    return write_payload_with_diff_ledger(metadata_path, metadata)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    metadata = generate_fixture_files(
        fixture_kind=normalize_fixture_kind(str(args.fixture_kind)),
        fixture_seed=str(args.fixture_seed),
        output_dir=Path(str(args.output_dir)),
        plan_output=Path(str(args.plan_output)).resolve() if str(args.plan_output).strip() else None,
        metadata_output=Path(str(args.metadata_output)).resolve() if str(args.metadata_output).strip() else None,
    )
    if args.json:
        print(json.dumps(metadata, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={metadata.get('observed_result')}",
                    f"fixture_kind={metadata.get('fixture_kind')}",
                    f"expected_verdict={metadata.get('expected_verdict')}",
                    f"plan_hash={metadata.get('plan_hash')}",
                    f"metadata={metadata.get('metadata_path')}",
                ]
            )
        )
    return 0 if metadata.get("observed_result") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
