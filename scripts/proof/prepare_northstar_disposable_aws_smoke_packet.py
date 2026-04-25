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
from scripts.proof.check_trusted_terraform_plan_fixture import build_fixture_check_report
from scripts.proof.generate_trusted_terraform_plan_fixture import generate_fixture_files
from scripts.proof.prepare_trusted_terraform_live_setup_packet import prepare_setup_packet
from scripts.proof.trusted_terraform_plan_decision_contract import now_utc_iso, relative_to_repo
from scripts.proof.trusted_terraform_plan_fixtures import normalize_fixture_kind
from scripts.proof.trusted_terraform_smoke_names import (
    contains_placeholder,
    generate_bucket_name,
    generate_smoke_suffix,
    generate_table_name,
    smoke_owner_marker,
    validate_operator_names,
)

PACKET_SCHEMA_VERSION = "northstar_disposable_aws_smoke_packet.v1"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "workspace" / "trusted_terraform_live_setup"
DEFAULT_KEY = "proof/terraform-plan.json"
DEFAULT_REGION = "us-east-1"
DEFAULT_MODEL_ID = "us.writer.palmyra-x4-v1:0"
DEFAULT_WRAPPER_OUTPUT = "northstar-disposable-aws-smoke-packet.json"
SETUP_PACKET_OUTPUT = "trusted_terraform_plan_decision_live_setup_packet.json"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a NorthStar disposable AWS smoke packet without provider calls.")
    parser.add_argument("--seed", default="")
    parser.add_argument("--bucket", default="")
    parser.add_argument("--table-name", default="")
    parser.add_argument("--key", default=DEFAULT_KEY)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--fixture-kind", default="safe", choices=["safe", "risky"])
    parser.add_argument("--fixture-seed", default="")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true", help="Print persisted wrapper JSON.")
    return parser.parse_args(argv)


def prepare_northstar_disposable_packet(
    *,
    seed: str,
    bucket: str,
    table_name: str,
    key: str,
    region: str,
    model_id: str,
    fixture_kind: str,
    fixture_seed: str,
    output_dir: Path,
    output: Path | None = None,
) -> dict[str, Any]:
    config = _resolve_config(
        seed=seed,
        bucket=bucket,
        table_name=table_name,
        key=key,
        region=region,
        model_id=model_id,
        fixture_kind=fixture_kind,
        fixture_seed=fixture_seed,
    )
    output_dir = output_dir.resolve()
    plan_path = output_dir / "terraform-plan.json"
    metadata_path = output_dir / "terraform-plan-fixture-metadata.json"
    check_path = output_dir / "terraform-plan-fixture-check.json"
    setup_packet_path = output_dir / SETUP_PACKET_OUTPUT
    wrapper_path = (output or (output_dir / DEFAULT_WRAPPER_OUTPUT)).resolve()
    metadata = generate_fixture_files(
        fixture_kind=config["fixture_kind"],
        fixture_seed=config["fixture_seed"],
        output_dir=output_dir,
        plan_output=plan_path,
        metadata_output=metadata_path,
    )
    fixture_check = build_fixture_check_report(
        plan_fixture=plan_path,
        metadata_path=metadata_path,
        expected_verdict=str(metadata.get("expected_verdict") or ""),
    )
    persisted_check = write_payload_with_diff_ledger(check_path, fixture_check)
    if persisted_check.get("observed_result") != "success":
        return _blocked_wrapper(config, wrapper_path, metadata, persisted_check)
    setup_packet = prepare_setup_packet(
        packet_root=output_dir,
        plan_fixture=plan_path,
        bucket=config["bucket"],
        key=config["key"],
        region=config["region"],
        model_id=config["model_id"],
        table_name=config["table_name"],
        created_at="2026-04-19T00:00:00Z",
        execution_trace_ref="northstar-disposable-aws-smoke",
        policy_bundle_id="terraform_plan_reviewer_v1",
        expected_plan_hash=str(metadata.get("plan_hash") or ""),
        smoke_owner_marker=config["smoke_owner_marker"],
    )
    persisted_setup = write_payload_with_diff_ledger(setup_packet_path, setup_packet)
    wrapper = _wrapper_payload(config, wrapper_path, metadata, persisted_check, persisted_setup)
    return write_payload_with_diff_ledger(wrapper_path, wrapper)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    payload = prepare_northstar_disposable_packet(
        seed=str(args.seed),
        bucket=str(args.bucket),
        table_name=str(args.table_name),
        key=str(args.key),
        region=str(args.region),
        model_id=str(args.model_id),
        fixture_kind=str(args.fixture_kind),
        fixture_seed=str(args.fixture_seed),
        output_dir=Path(str(args.output_dir)),
        output=Path(str(args.output)).resolve() if str(args.output).strip() else None,
    )
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={payload.get('observed_result')}",
                    f"bucket={payload.get('bucket')}",
                    f"table={payload.get('table_name')}",
                    f"provider_calls_executed={len(payload.get('provider_calls_executed') or [])}",
                    f"output={payload.get('packet_output_ref')}",
                ]
            )
        )
    return 0 if payload.get("observed_result") == "success" else 1


def _resolve_config(**kwargs: str) -> dict[str, str]:
    seed = str(kwargs["seed"] or "").strip()
    bucket = str(kwargs["bucket"] or "").strip()
    table_name = str(kwargs["table_name"] or "").strip()
    if (not bucket or not table_name) and not seed:
        raise ValueError("seed_required_when_bucket_or_table_omitted")
    bucket = bucket or generate_bucket_name(seed)
    table_name = table_name or generate_table_name(seed)
    if any(contains_placeholder(value) for value in (bucket, table_name, kwargs["key"])):
        raise ValueError("generated_smoke_names_contain_placeholder")
    validate_operator_names(bucket=bucket, table_name=table_name)
    fixture_seed = str(kwargs["fixture_seed"] or seed).strip()
    if not fixture_seed:
        raise ValueError("fixture_seed_required")
    return {
        "seed": seed,
        "suffix": generate_smoke_suffix(seed) if seed else "",
        "bucket": bucket,
        "table_name": table_name,
        "key": str(kwargs["key"]).strip().lstrip("/"),
        "region": str(kwargs["region"]).strip(),
        "model_id": str(kwargs["model_id"]).strip(),
        "fixture_kind": normalize_fixture_kind(str(kwargs["fixture_kind"])),
        "fixture_seed": fixture_seed,
        "smoke_owner_marker": smoke_owner_marker(seed or fixture_seed),
    }


def _wrapper_payload(
    config: dict[str, str],
    wrapper_path: Path,
    metadata: dict[str, Any],
    fixture_check: dict[str, Any],
    setup_packet: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": PACKET_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "structural",
        "observed_path": "primary",
        "observed_result": "success",
        "publication_decision": "not_evaluated",
        "admission_evidence": "absent",
        "provider_calls_executed": [],
        "packet_output_ref": relative_to_repo(wrapper_path),
        "bucket": config["bucket"],
        "key": config["key"],
        "s3_plan_uri": f"s3://{config['bucket']}/{config['key']}",
        "table_name": config["table_name"],
        "region": config["region"],
        "model_id": config["model_id"],
        "smoke_owner_marker": config["smoke_owner_marker"],
        "fixture_metadata": metadata,
        "fixture_check": fixture_check,
        "expected_plan_hash": metadata.get("plan_hash"),
        "setup_packet": setup_packet,
    }


def _blocked_wrapper(
    config: dict[str, str],
    wrapper_path: Path,
    metadata: dict[str, Any],
    fixture_check: dict[str, Any],
) -> dict[str, Any]:
    return write_payload_with_diff_ledger(
        wrapper_path,
        {
            "schema_version": PACKET_SCHEMA_VERSION,
            "recorded_at_utc": now_utc_iso(),
            "proof_kind": "structural",
            "observed_path": "blocked",
            "observed_result": "failure",
            "publication_decision": "not_evaluated",
            "admission_evidence": "absent",
            "provider_calls_executed": [],
            "packet_output_ref": relative_to_repo(wrapper_path),
            "bucket": config["bucket"],
            "key": config["key"],
            "table_name": config["table_name"],
            "region": config["region"],
            "model_id": config["model_id"],
            "fixture_metadata": metadata,
            "fixture_check": fixture_check,
            "blocking_reasons": list(fixture_check.get("blocking_reasons") or []),
        },
    )


if __name__ == "__main__":
    raise SystemExit(main())
