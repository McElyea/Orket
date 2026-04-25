#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.trusted_terraform_plan_decision_contract import now_utc_iso, relative_to_repo
from scripts.proof.trusted_terraform_plan_fixtures import plan_digest_from_path, validate_plan_fixture_payload

CHECK_SCHEMA_VERSION = "trusted_terraform_plan_fixture_check.v1"
DEFAULT_PACKET_DIR = REPO_ROOT / "workspace" / "trusted_terraform_live_setup"
DEFAULT_PLAN_PATH = DEFAULT_PACKET_DIR / "terraform-plan.json"
DEFAULT_METADATA_PATH = DEFAULT_PACKET_DIR / "terraform-plan-fixture-metadata.json"
DEFAULT_OUTPUT = DEFAULT_PACKET_DIR / "terraform-plan-fixture-check.json"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a generated Terraform plan fixture before upload.")
    parser.add_argument("--plan-fixture", default=str(DEFAULT_PLAN_PATH))
    parser.add_argument("--metadata", default=str(DEFAULT_METADATA_PATH))
    parser.add_argument("--expected-verdict", default="")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true", help="Print persisted check JSON.")
    return parser.parse_args(argv)


def build_fixture_check_report(*, plan_fixture: Path, metadata_path: Path, expected_verdict: str = "") -> dict[str, Any]:
    metadata, metadata_error = _load_metadata(metadata_path)
    expected = str(expected_verdict or metadata.get("expected_verdict") or "").strip()
    if metadata_error:
        return _report(plan_fixture, metadata_path, "blocked", "failure", [metadata_error], expected, "", {})
    if not plan_fixture.exists():
        return _report(plan_fixture, metadata_path, "blocked", "failure", ["plan_fixture_missing"], expected, "", {})
    try:
        plan_bytes = plan_fixture.read_bytes()
    except OSError as exc:
        return _report(plan_fixture, metadata_path, "blocked", "environment blocker", [f"plan_fixture_read_failed:{exc}"], expected, "", {})
    validation = validate_plan_fixture_payload(plan_bytes=plan_bytes, expected_verdict=expected)
    failures = list(validation.get("blocking_reasons") or [])
    metadata_hash = str(metadata.get("plan_hash") or "")
    actual_hash = plan_digest_from_path(plan_fixture)
    if metadata_hash and metadata_hash != actual_hash:
        failures.append("metadata_plan_hash_mismatch")
    observed_result = "success" if not failures else "failure"
    return _report(
        plan_fixture,
        metadata_path,
        "primary" if not failures else "blocked",
        observed_result,
        failures,
        expected,
        str(validation.get("actual_verdict") or ""),
        {
            "plan_hash": actual_hash,
            "metadata": metadata,
            "unsupported_actions": validation.get("unsupported_actions") or [],
            "deterministic_analysis": validation.get("deterministic_analysis") or {},
        },
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = build_fixture_check_report(
        plan_fixture=Path(str(args.plan_fixture)).resolve(),
        metadata_path=Path(str(args.metadata)).resolve(),
        expected_verdict=str(args.expected_verdict),
    )
    output = Path(str(args.output)).resolve()
    persisted = write_payload_with_diff_ledger(output, report)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={persisted.get('observed_result')}",
                    f"observed_path={persisted.get('observed_path')}",
                    f"expected_verdict={persisted.get('expected_verdict')}",
                    f"actual_verdict={persisted.get('actual_verdict')}",
                    f"output={relative_to_repo(output)}",
                ]
            )
        )
    return 0 if persisted.get("observed_result") == "success" else 1


def _load_metadata(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, "fixture_metadata_missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"fixture_metadata_invalid_json:{exc.msg}"
    if not isinstance(payload, dict):
        return {}, "fixture_metadata_json_object_required"
    payload.pop("diff_ledger", None)
    return payload, ""


def _report(
    plan_fixture: Path,
    metadata_path: Path,
    observed_path: str,
    observed_result: str,
    blocking_reasons: list[str],
    expected_verdict: str,
    actual_verdict: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": CHECK_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "structural",
        "observed_path": observed_path,
        "observed_result": observed_result,
        "plan_fixture": relative_to_repo(plan_fixture),
        "metadata": relative_to_repo(metadata_path),
        "expected_verdict": expected_verdict,
        "actual_verdict": actual_verdict,
        "blocking_reasons": blocking_reasons,
        **details,
    }


if __name__ == "__main__":
    raise SystemExit(main())
