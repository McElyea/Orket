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
from scripts.proof.terraform_plan_review_live_support import (
    LiveTerraformReviewConfig,
    bedrock_smoke_runtime_operation,
    live_config_from_env,
    missing_required_env,
    parse_s3_bucket_key,
    supported_bedrock_smoke_model,
)
from orket.application.terraform_review.deterministic import digest_plan_bytes
from scripts.proof.trusted_terraform_plan_decision_contract import (
    PROOF_RESULTS_ROOT,
    TRUSTED_TERRAFORM_COMPARE_SCOPE,
    now_utc_iso,
    relative_to_repo,
)

LIVE_SETUP_PREFLIGHT_SCHEMA_VERSION = "trusted_terraform_plan_decision_live_setup_preflight.v1"
DEFAULT_LIVE_SETUP_PREFLIGHT_OUTPUT = PROOF_RESULTS_ROOT / "trusted_terraform_plan_decision_live_setup_preflight.json"
DEFAULT_PACKET_DIR = REPO_ROOT / "workspace" / "trusted_terraform_live_setup"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    env = live_config_from_env()
    parser = argparse.ArgumentParser(description="No-spend preflight for the Terraform governed-proof live setup.")
    parser.add_argument("--output", default=str(DEFAULT_LIVE_SETUP_PREFLIGHT_OUTPUT), help="Stable preflight output path.")
    parser.add_argument("--packet-dir", default=str(DEFAULT_PACKET_DIR), help="Generated disposable setup packet directory.")
    parser.add_argument("--plan-s3-uri", default=env.plan_s3_uri)
    parser.add_argument("--model-id", default=env.model_id)
    parser.add_argument("--region", default=env.region)
    parser.add_argument("--table-name", default=env.table_name)
    parser.add_argument("--created-at", default=env.created_at)
    parser.add_argument("--execution-trace-ref", default=env.execution_trace_ref)
    parser.add_argument("--policy-bundle-id", default=env.policy_bundle_id)
    parser.add_argument("--expected-plan-hash", default=env.expected_plan_hash)
    parser.add_argument("--smoke-owner-marker", default=env.smoke_owner_marker)
    parser.add_argument("--json", action="store_true", help="Print the persisted setup preflight JSON.")
    return parser.parse_args(argv)


def build_live_setup_preflight_report(*, config: LiveTerraformReviewConfig, packet_dir: Path | None = None) -> dict[str, Any]:
    missing = missing_required_env(config)
    validation_failures = _validation_failures(config)
    packet_validation = _packet_validation(packet_dir, config) if packet_dir else {"status": "not_checked", "blocking_reasons": []}
    blocking_reasons = [f"missing_required_env:{','.join(missing)}"] if missing else []
    blocking_reasons.extend(validation_failures)
    blocking_reasons.extend([str(item) for item in packet_validation.get("blocking_reasons") or []])
    success = not blocking_reasons
    return {
        "schema_version": LIVE_SETUP_PREFLIGHT_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "structural",
        "preflight_kind": "no_spend_local_configuration",
        "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
        "observed_path": "primary" if success else "blocked",
        "observed_result": "success" if success else "environment blocker",
        "publication_decision": "not_evaluated",
        "provider_calls_executed": [],
        "provider_calls_planned": _provider_calls_planned(config),
        "required_env": [
            "ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI",
            "ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID",
            "AWS_REGION or AWS_DEFAULT_REGION",
        ],
        "missing_env": missing,
        "config_summary": _config_summary(config),
        "packet_validation": packet_validation,
        "credential_handling": {
            "aws_credentials_source": "standard AWS provider chain",
            "credential_values_recorded": False,
            "credentials_inspected": False,
        },
        "least_privilege_actions": _least_privilege_actions(config),
        "blocking_reasons": blocking_reasons,
        "next_commands": [
            "python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py",
            "python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py --force-local-evidence",
        ],
        "limitations": [
            "does not call AWS",
            "does not prove the S3 object exists",
            "does not prove Bedrock model access",
            "does not prove DynamoDB table existence or write permission",
            "does not inspect or record AWS credential values",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    raw_argv = sys.argv[1:] if argv is None else argv
    args = _parse_args(raw_argv)
    packet_dir_explicit = any(item == "--packet-dir" or item.startswith("--packet-dir=") for item in raw_argv)
    packet_dir = Path(str(args.packet_dir)).resolve()
    raw_config = LiveTerraformReviewConfig(
        plan_s3_uri=str(args.plan_s3_uri),
        model_id=str(args.model_id),
        region=str(args.region),
        table_name=str(args.table_name),
        created_at=str(args.created_at),
        execution_trace_ref=str(args.execution_trace_ref),
        policy_bundle_id=str(args.policy_bundle_id),
        expected_plan_hash=str(args.expected_plan_hash),
        smoke_owner_marker=str(args.smoke_owner_marker),
    )
    config = _merge_packet_config(packet_dir=packet_dir, config=raw_config) if packet_dir_explicit else raw_config
    report = build_live_setup_preflight_report(config=config, packet_dir=packet_dir if packet_dir_explicit else None)
    output = Path(str(args.output)).resolve()
    persisted = write_payload_with_diff_ledger(output, report)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={persisted.get('observed_result')}",
                    f"provider_calls_executed={len(persisted.get('provider_calls_executed') or [])}",
                    f"output={relative_to_repo(output)}",
                ]
            )
        )
    return 0 if persisted.get("observed_result") == "success" else 1


def _validation_failures(config: LiveTerraformReviewConfig) -> list[str]:
    failures: list[str] = []
    if str(config.plan_s3_uri).strip():
        try:
            bucket, key = parse_s3_bucket_key(str(config.plan_s3_uri))
        except ValueError:
            failures.append("invalid_s3_uri")
        else:
            if _contains_placeholder(bucket) or _contains_placeholder(key):
                failures.append("s3_uri_placeholder_not_replaced")
    if str(config.model_id).strip() and not supported_bedrock_smoke_model(str(config.model_id)):
        failures.append("unsupported_bedrock_model_for_smoke")
    if not str(config.table_name).strip():
        failures.append("dynamodb_table_name_missing")
    if not str(config.policy_bundle_id).strip():
        failures.append("policy_bundle_id_missing")
    return failures


def _provider_calls_planned(config: LiveTerraformReviewConfig) -> list[dict[str, Any]]:
    bucket = ""
    key = ""
    if str(config.plan_s3_uri).strip():
        try:
            bucket, key = parse_s3_bucket_key(str(config.plan_s3_uri))
        except ValueError:
            pass
    return [
        {"service": "s3", "operation": "GetObject", "count": 1, "resource_hint": f"s3://{bucket}/{key}" if bucket and key else "plan_s3_uri"},
        {
            "service": "bedrock-runtime",
            "operation": bedrock_smoke_runtime_operation(str(config.model_id)),
            "count": 1,
            "resource_hint": str(config.model_id or "model_id"),
        },
        {"service": "dynamodb", "operation": "PutItem", "count": 1, "resource_hint": str(config.table_name or "TerraformReviews")},
    ]


def _contains_placeholder(value: str) -> bool:
    return "<" in value or ">" in value


def _least_privilege_actions(config: LiveTerraformReviewConfig) -> list[dict[str, Any]]:
    return [
        {"action": "s3:GetObject", "resource_hint": str(config.plan_s3_uri or "s3://<bucket>/<key>")},
        {"action": "bedrock:InvokeModel", "resource_hint": str(config.model_id or "<bedrock-model-id>")},
        {"action": "dynamodb:PutItem", "resource_hint": str(config.table_name or "TerraformReviews")},
    ]


def _config_summary(config: LiveTerraformReviewConfig) -> dict[str, Any]:
    return {
        "plan_s3_uri_present": bool(str(config.plan_s3_uri).strip()),
        "model_id": str(config.model_id or ""),
        "bedrock_runtime_operation": bedrock_smoke_runtime_operation(str(config.model_id)),
        "region": str(config.region or ""),
        "table_name": str(config.table_name or ""),
        "execution_trace_ref": str(config.execution_trace_ref or ""),
        "policy_bundle_id": str(config.policy_bundle_id or ""),
        "expected_plan_hash_present": bool(str(config.expected_plan_hash or "").strip()),
        "smoke_owner_marker_present": bool(str(config.smoke_owner_marker or "").strip()),
        "forbidden_operations": list(config.forbidden_operations),
    }


def _merge_packet_config(*, packet_dir: Path, config: LiveTerraformReviewConfig) -> LiveTerraformReviewConfig:
    values = _load_packet_env(packet_dir)
    table_value = str(config.table_name or "")
    if table_value == "TerraformReviews" and values.get("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_TABLE"):
        table_value = str(values["ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_TABLE"])
    return LiveTerraformReviewConfig(
        plan_s3_uri=str(config.plan_s3_uri or values.get("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI") or ""),
        model_id=str(config.model_id or values.get("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID") or ""),
        region=str(config.region or values.get("AWS_REGION") or values.get("AWS_DEFAULT_REGION") or ""),
        table_name=table_value or "TerraformReviews",
        created_at=str(config.created_at or values.get("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_CREATED_AT") or ""),
        execution_trace_ref=str(config.execution_trace_ref or values.get("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_TRACE_REF") or ""),
        policy_bundle_id=str(config.policy_bundle_id or values.get("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_POLICY_BUNDLE_ID") or ""),
        expected_plan_hash=str(config.expected_plan_hash or values.get("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_EXPECTED_PLAN_HASH") or ""),
        smoke_owner_marker=str(config.smoke_owner_marker or values.get("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_OWNER_MARKER") or ""),
    )


def _load_packet_env(packet_dir: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for path in [packet_dir / "live-run-env.ps1.template", packet_dir / "live-run.env.template"]:
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            key, value = _parse_env_line(raw)
            if key:
                values[key] = value
    return values


def _parse_env_line(raw: str) -> tuple[str, str]:
    line = raw.strip()
    if not line or line.startswith("#"):
        return "", ""
    if line.startswith("$env:") and "=" in line:
        key, value = line.split("=", 1)
        return key.replace("$env:", "").strip(), value.strip().strip('"')
    if "=" in line:
        key, value = line.split("=", 1)
        return key.strip(), value.strip().strip('"')
    return "", ""


def _packet_validation(packet_dir: Path | None, config: LiveTerraformReviewConfig) -> dict[str, Any]:
    if packet_dir is None or not packet_dir.exists():
        return {"status": "not_checked", "blocking_reasons": []}
    packet = _load_packet_json(packet_dir)
    failures: list[str] = []
    if packet:
        failures.extend(_packet_value_mismatches(packet, config))
    cleanup = packet_dir / "aws-cli-cleanup-commands.ps1"
    if not cleanup.exists():
        failures.append("cleanup_command_file_missing")
    if str(config.expected_plan_hash or "").strip():
        plan_file = packet_dir / "terraform-plan-safe-smoke.plan.json"
        if not plan_file.exists():
            failures.append("plan_fixture_copy_missing")
        elif digest_plan_bytes(plan_file.read_bytes()) != str(config.expected_plan_hash).strip():
            failures.append("fixture_hash_mismatch")
    return {
        "status": "pass" if not failures else "blocked",
        "packet_dir": relative_to_repo(packet_dir),
        "packet_ref": str(packet.get("packet_ref") or "") if packet else "",
        "cleanup_command_ref": relative_to_repo(cleanup) if cleanup.exists() else "",
        "blocking_reasons": failures,
    }


def _load_packet_json(packet_dir: Path) -> dict[str, Any]:
    for name in ["northstar-disposable-aws-smoke-packet.json", "trusted_terraform_plan_decision_live_setup_packet.json"]:
        path = packet_dir / name
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"packet_ref": relative_to_repo(path), "error": "packet_json_invalid"}
        if isinstance(payload, dict):
            payload["packet_ref"] = relative_to_repo(path)
            return payload
    return {}


def _packet_value_mismatches(packet: dict[str, Any], config: LiveTerraformReviewConfig) -> list[str]:
    failures: list[str] = []
    expected = {
        "s3_plan_uri": str(config.plan_s3_uri or ""),
        "model_id": str(config.model_id or ""),
        "region": str(config.region or ""),
        "table_name": str(config.table_name or ""),
    }
    for key, value in expected.items():
        if value and str(packet.get(key) or "") and str(packet.get(key) or "") != value:
            failures.append(f"packet_{key}_mismatch")
    if packet.get("error"):
        failures.append(str(packet["error"]))
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
