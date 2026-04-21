#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.terraform_plan_review_live_support import (
    bedrock_smoke_resource_arn,
    bedrock_smoke_runtime_operation,
    supported_bedrock_smoke_model,
)
from scripts.proof.trusted_terraform_plan_decision_contract import (
    PROOF_RESULTS_ROOT,
    TRUSTED_TERRAFORM_COMPARE_SCOPE,
    now_utc_iso,
    relative_to_repo,
)

SETUP_PACKET_SCHEMA_VERSION = "trusted_terraform_plan_decision_live_setup_packet.v1"
DEFAULT_PACKET_ROOT = REPO_ROOT / "workspace" / "trusted_terraform_live_setup"
DEFAULT_SETUP_PACKET_OUTPUT = PROOF_RESULTS_ROOT / "trusted_terraform_plan_decision_live_setup_packet.json"
DEFAULT_PLAN_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "terraform_plan_reviewer_v1" / "create_update_only.plan.json"
DEFAULT_BUCKET = "<replace-with-globally-unique-smoke-bucket>"
DEFAULT_KEY = "orket/trusted-terraform-plan-decision/terraform-plan-safe-smoke.plan.json"
DEFAULT_REGION = "us-east-1"
DEFAULT_MODEL_ID = "us.amazon.nova-lite-v1:0"
DEFAULT_TABLE_NAME = "TerraformReviews"
DEFAULT_TRACE_REF = "trusted-terraform-plan-decision-live-runtime"
DEFAULT_CREATED_AT = "2026-04-19T00:00:00Z"
DEFAULT_POLICY_BUNDLE_ID = "terraform_plan_reviewer_v1"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare the no-spend setup packet for the Trusted Terraform provider-backed proof run."
    )
    parser.add_argument("--packet-root", default=str(DEFAULT_PACKET_ROOT), help="Directory for generated setup files.")
    parser.add_argument("--output", default=str(DEFAULT_SETUP_PACKET_OUTPUT), help="Stable setup-packet report path.")
    parser.add_argument("--plan-fixture", default=str(DEFAULT_PLAN_FIXTURE), help="Local Terraform JSON plan fixture to copy.")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET, help="Target S3 bucket name or placeholder.")
    parser.add_argument("--key", default=DEFAULT_KEY, help="Target S3 object key for the plan fixture.")
    parser.add_argument("--region", default=DEFAULT_REGION, help="AWS region for generated commands and env templates.")
    parser.add_argument(
        "--model-id",
        default=DEFAULT_MODEL_ID,
        help="Bedrock model or inference-profile id for the advisory summary path.",
    )
    parser.add_argument("--table-name", default=DEFAULT_TABLE_NAME, help="DynamoDB table name for audit publication.")
    parser.add_argument("--created-at", default=DEFAULT_CREATED_AT, help="Fixed smoke request timestamp.")
    parser.add_argument("--execution-trace-ref", default=DEFAULT_TRACE_REF, help="Live proof execution trace ref.")
    parser.add_argument("--policy-bundle-id", default=DEFAULT_POLICY_BUNDLE_ID, help="Terraform reviewer policy bundle id.")
    parser.add_argument("--json", action="store_true", help="Print the persisted setup-packet report JSON.")
    return parser.parse_args(argv)


def prepare_setup_packet(
    *,
    packet_root: Path,
    plan_fixture: Path,
    bucket: str,
    key: str,
    region: str,
    model_id: str,
    table_name: str,
    created_at: str,
    execution_trace_ref: str,
    policy_bundle_id: str,
) -> dict[str, Any]:
    packet_root = packet_root.resolve()
    plan_fixture = plan_fixture.resolve()
    if not plan_fixture.exists():
        raise FileNotFoundError(f"plan_fixture_missing:{plan_fixture}")
    packet_root.mkdir(parents=True, exist_ok=True)

    plan_file = packet_root / "terraform-plan-safe-smoke.plan.json"
    plan_payload = json.loads(plan_fixture.read_text(encoding="utf-8"))
    _write_json(plan_file, plan_payload)

    config = {
        "bucket": bucket.strip(),
        "key": key.strip().lstrip("/"),
        "region": region.strip(),
        "model_id": model_id.strip(),
        "table_name": table_name.strip(),
        "created_at": created_at.strip(),
        "execution_trace_ref": execution_trace_ref.strip(),
        "policy_bundle_id": policy_bundle_id.strip(),
    }
    files = _write_packet_files(packet_root=packet_root, plan_file=plan_file, config=config)
    file_refs = [_file_ref(path) for path in [plan_file, *files]]
    blockers = _live_execution_blockers(config)
    return _setup_packet_report(config=config, packet_root=packet_root, file_refs=file_refs, blockers=blockers)


def _setup_packet_report(
    *,
    config: dict[str, str],
    packet_root: Path,
    file_refs: list[dict[str, Any]],
    blockers: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": SETUP_PACKET_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "structural",
        "packet_kind": "no_spend_live_run_setup",
        "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
        "observed_path": "primary",
        "observed_result": "success",
        "publication_decision": "not_evaluated",
        "provider_calls_executed": [],
        "live_execution_ready": not blockers,
        "live_execution_blockers": blockers,
        "credential_handling": {
            "credential_values_recorded": False,
            "credentials_inspected": False,
            "credentials_written_to_packet": False,
            "credentials_expected_source": "standard AWS provider chain outside generated packet files",
        },
        "s3_plan_uri": _s3_uri(config),
        "packet_root": relative_to_repo(packet_root),
        "packet_files": file_refs,
        "provider_calls_planned_for_setup_commands": _setup_calls(config),
        "provider_calls_planned_for_live_governed_proof": _live_calls(config),
        "least_privilege_runtime_actions": _least_privilege_runtime_actions(config),
        "setup_action_checklist": _setup_action_checklist(config),
        "next_commands": [
            f"python scripts/proof/check_trusted_terraform_live_setup_preflight.py --plan-s3-uri {_s3_uri(config)} --model-id {config['model_id']} --region {config['region']} --table-name {config['table_name']}",
            "python scripts/proof/run_trusted_terraform_plan_decision_runtime_smoke.py --output benchmarks/results/proof/trusted_terraform_plan_decision_live_runtime.json",
            "python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py",
        ],
        "limitations": [
            "generates local setup files only",
            "does not call AWS",
            "does not create or verify S3, DynamoDB, Bedrock, or IAM resources",
            "does not prove credential validity or provider access",
            "does not provide publication evidence by itself",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    payload = prepare_setup_packet(
        packet_root=Path(str(args.packet_root)),
        plan_fixture=Path(str(args.plan_fixture)),
        bucket=str(args.bucket),
        key=str(args.key),
        region=str(args.region),
        model_id=str(args.model_id),
        table_name=str(args.table_name),
        created_at=str(args.created_at),
        execution_trace_ref=str(args.execution_trace_ref),
        policy_bundle_id=str(args.policy_bundle_id),
    )
    output = Path(str(args.output)).resolve()
    persisted = write_payload_with_diff_ledger(output, payload)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={persisted.get('observed_result')}",
                    f"live_execution_ready={persisted.get('live_execution_ready')}",
                    f"provider_calls_executed={len(persisted.get('provider_calls_executed') or [])}",
                    f"output={relative_to_repo(output)}",
                ]
            )
        )
    return 0


def _write_packet_files(*, packet_root: Path, plan_file: Path, config: dict[str, str]) -> list[Path]:
    env_template = packet_root / "live-run.env.template"
    powershell_env = packet_root / "live-run-env.ps1.template"
    setup_commands = packet_root / "aws-cli-setup-commands.ps1"
    cleanup_commands = packet_root / "aws-cli-cleanup-commands.ps1"
    iam_policy = packet_root / "least-privilege-runtime-policy.json"
    checklist = packet_root / "live-run-checklist.md"

    _write_text(env_template, _env_template(config))
    _write_text(powershell_env, _powershell_env_template(config))
    _write_text(setup_commands, _setup_commands(plan_file=plan_file, config=config))
    _write_text(cleanup_commands, _cleanup_commands(config))
    _write_json(iam_policy, _runtime_policy(config))
    _write_text(checklist, _checklist_markdown(config))
    return [env_template, powershell_env, setup_commands, cleanup_commands, iam_policy, checklist]


def _env_template(config: dict[str, str]) -> str:
    return "\n".join(
        [
            "# Generated local template. Do not put AWS secret values in this file.",
            f"AWS_REGION={config['region']}",
            f"AWS_DEFAULT_REGION={config['region']}",
            f"ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI={_s3_uri(config)}",
            f"ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID={config['model_id']}",
            f"ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_TABLE={config['table_name']}",
            f"ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_CREATED_AT={config['created_at']}",
            f"ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_TRACE_REF={config['execution_trace_ref']}",
            f"ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_POLICY_BUNDLE_ID={config['policy_bundle_id']}",
            "",
        ]
    )


def _powershell_env_template(config: dict[str, str]) -> str:
    rows = [
        "# Generated local template. Do not put AWS secret values in this file.",
        f"$env:AWS_REGION = \"{config['region']}\"",
        f"$env:AWS_DEFAULT_REGION = \"{config['region']}\"",
        f"$env:ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI = \"{_s3_uri(config)}\"",
        f"$env:ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID = \"{config['model_id']}\"",
        f"$env:ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_TABLE = \"{config['table_name']}\"",
        f"$env:ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_CREATED_AT = \"{config['created_at']}\"",
        f"$env:ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_TRACE_REF = \"{config['execution_trace_ref']}\"",
        f"$env:ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_POLICY_BUNDLE_ID = \"{config['policy_bundle_id']}\"",
        "",
    ]
    return "\n".join(rows)


def _setup_commands(*, plan_file: Path, config: dict[str, str]) -> str:
    return "\n".join(
        [
            "$ErrorActionPreference = \"Stop\"",
            f"$Region = \"{config['region']}\"",
            f"$Bucket = \"{config['bucket']}\"",
            f"$Key = \"{config['key']}\"",
            f"$TableName = \"{config['table_name']}\"",
            f"$PlanPath = \"{plan_file}\"",
            "",
            "if ($Bucket -like \"<*\") { throw \"Replace the bucket placeholder before running setup.\" }",
            "if ($Region -eq \"us-east-1\") {",
            "  aws s3api create-bucket --bucket $Bucket --region $Region",
            "} else {",
            "  aws s3api create-bucket --bucket $Bucket --region $Region --create-bucket-configuration \"LocationConstraint=$Region\"",
            "}",
            "aws s3api put-public-access-block --bucket $Bucket --public-access-block-configuration \"BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true\"",
            "aws s3 cp $PlanPath \"s3://$Bucket/$Key\"",
            "aws dynamodb create-table --table-name $TableName --region $Region --billing-mode PAY_PER_REQUEST --attribute-definitions AttributeName=plan_hash,AttributeType=S --key-schema AttributeName=plan_hash,KeyType=HASH",
            "aws dynamodb wait table-exists --table-name $TableName --region $Region",
            "",
        ]
    )


def _cleanup_commands(config: dict[str, str]) -> str:
    return "\n".join(
        [
            "$ErrorActionPreference = \"Stop\"",
            f"$Region = \"{config['region']}\"",
            f"$Bucket = \"{config['bucket']}\"",
            f"$Key = \"{config['key']}\"",
            f"$TableName = \"{config['table_name']}\"",
            "",
            "if ($Bucket -like \"<*\") { throw \"Replace the bucket placeholder before running cleanup.\" }",
            "aws s3 rm \"s3://$Bucket/$Key\"",
            "aws s3api delete-bucket --bucket $Bucket --region $Region",
            "aws dynamodb delete-table --table-name $TableName --region $Region",
            "aws dynamodb wait table-not-exists --table-name $TableName --region $Region",
            "",
        ]
    )


def _checklist_markdown(config: dict[str, str]) -> str:
    return "\n".join(
        [
            "# Trusted Terraform Live Setup Checklist",
            "",
            "This packet is setup assistance only. It is not provider-backed proof evidence.",
            "",
            "1. Replace the bucket placeholder with a globally unique bucket name.",
            "2. Configure AWS credentials outside the repository using the standard AWS provider chain.",
            "3. Run `aws-cli-setup-commands.ps1` only when you are ready to create the low-cost S3 and DynamoDB resources.",
            "4. Load `live-run-env.ps1.template` values into the shell that will run Orket proof commands.",
            "5. Run `python scripts/proof/check_trusted_terraform_live_setup_preflight.py` before the live smoke; unreplaced S3 placeholders must stay blocked.",
            "6. Run `python scripts/proof/run_trusted_terraform_plan_decision_runtime_smoke.py --output benchmarks/results/proof/trusted_terraform_plan_decision_live_runtime.json` only after preflight passes.",
            "7. Run `python scripts/proof/run_trusted_terraform_plan_decision_publication_gate.py` after a successful provider-backed governed proof run.",
            "8. Run `aws-cli-cleanup-commands.ps1` after the live attempt unless you intentionally keep the resources.",
            "",
            f"Planned S3 URI: `{_s3_uri(config)}`",
            f"Planned DynamoDB table: `{config['table_name']}`",
            f"Planned Bedrock model or inference-profile id: `{config['model_id']}`",
            f"Planned Bedrock inference operation: `{bedrock_smoke_runtime_operation(config['model_id'])}`",
            "",
        ]
    )


def _runtime_policy(config: dict[str, str]) -> dict[str, Any]:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "ReadSmokeTerraformPlan",
                "Effect": "Allow",
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{config['bucket']}/{config['key']}"],
            },
            {
                "Sid": "InvokeConfiguredBedrockModel",
                "Effect": "Allow",
                "Action": ["bedrock:InvokeModel"],
                "Resource": [bedrock_smoke_resource_arn(config["model_id"], config["region"])],
            },
            {
                "Sid": "WriteTerraformReviewAudit",
                "Effect": "Allow",
                "Action": ["dynamodb:PutItem"],
                "Resource": [f"arn:aws:dynamodb:{config['region']}:<account-id>:table/{config['table_name']}"],
            },
        ],
    }


def _setup_calls(config: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {"service": "s3", "operation": "CreateBucket", "count": 1, "resource_hint": config["bucket"]},
        {"service": "s3", "operation": "PutPublicAccessBlock", "count": 1, "resource_hint": config["bucket"]},
        {"service": "s3", "operation": "PutObject", "count": 1, "resource_hint": _s3_uri(config)},
        {"service": "dynamodb", "operation": "CreateTable", "count": 1, "resource_hint": config["table_name"]},
        {"service": "dynamodb", "operation": "DescribeTable", "count": "waiter", "resource_hint": config["table_name"]},
    ]


def _live_calls(config: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {"service": "s3", "operation": "GetObject", "count": 1, "resource_hint": _s3_uri(config)},
        {
            "service": "bedrock-runtime",
            "operation": bedrock_smoke_runtime_operation(config["model_id"]),
            "count": 1,
            "resource_hint": config["model_id"],
        },
        {"service": "dynamodb", "operation": "PutItem", "count": 1, "resource_hint": config["table_name"]},
    ]


def _least_privilege_runtime_actions(config: dict[str, str]) -> list[dict[str, str]]:
    return [
        {"action": "s3:GetObject", "resource_hint": _s3_uri(config)},
        {"action": "bedrock:InvokeModel", "resource_hint": config["model_id"]},
        {"action": "dynamodb:PutItem", "resource_hint": config["table_name"]},
    ]


def _setup_action_checklist(config: dict[str, str]) -> list[str]:
    checklist = ["choose_unique_s3_bucket", "configure_aws_credentials_outside_repo"]
    if _is_placeholder(config["bucket"]):
        checklist.append("replace_bucket_placeholder")
    checklist.extend(["create_s3_bucket", "upload_plan_fixture", "create_pay_per_request_dynamodb_table", "run_no_spend_preflight"])
    return checklist


def _live_execution_blockers(config: dict[str, str]) -> list[str]:
    blockers: list[str] = []
    if _is_placeholder(config["bucket"]):
        blockers.append("bucket_placeholder_not_replaced")
    if not config["key"]:
        blockers.append("s3_key_missing")
    if not config["region"]:
        blockers.append("region_missing")
    if not supported_bedrock_smoke_model(config["model_id"]):
        blockers.append("unsupported_bedrock_model_for_smoke")
    if not config["table_name"]:
        blockers.append("dynamodb_table_name_missing")
    return blockers


def _s3_uri(config: dict[str, str]) -> str:
    return f"s3://{config['bucket']}/{config['key']}"


def _is_placeholder(value: str) -> bool:
    return value.strip().startswith("<") and value.strip().endswith(">")


def _file_ref(path: Path) -> dict[str, Any]:
    return {
        "path": relative_to_repo(path),
        "digest": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        "size_bytes": path.stat().st_size,
    }


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _write_text(path, json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
