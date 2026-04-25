#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.trusted_terraform_plan_decision_contract import now_utc_iso, relative_to_repo

SETUP_RESULT_SCHEMA_VERSION = "trusted_terraform_disposable_aws_setup_result.v1"
DEFAULT_PACKET_DIR = REPO_ROOT / "workspace" / "trusted_terraform_live_setup"
DEFAULT_OUTPUT = DEFAULT_PACKET_DIR / "aws-setup-result.json"
WRAPPER_PACKET = "northstar-disposable-aws-smoke-packet.json"
SETUP_PACKET = "trusted_terraform_plan_decision_live_setup_packet.json"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Explicit opt-in AWS setup runner for disposable Terraform smoke resources.")
    parser.add_argument("--packet-dir", default=str(DEFAULT_PACKET_DIR))
    parser.add_argument("--execute-live-aws", action="store_true")
    parser.add_argument("--acknowledge-cost-and-mutation", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true", help="Print persisted setup result JSON.")
    return parser.parse_args(argv)


def build_setup_result(*, packet_dir: Path, execute_live_aws: bool, acknowledge_cost_and_mutation: bool) -> dict[str, Any]:
    packet = _load_packet(packet_dir)
    if not execute_live_aws or not acknowledge_cost_and_mutation:
        return _base_result(packet_dir, packet, "blocked", "environment blocker", ["live_aws_setup_opt_in_flags_missing"], [])
    if packet.get("error"):
        return _base_result(packet_dir, packet, "blocked", "failure", [str(packet["error"])], [])
    aws = shutil.which("aws")
    if not aws:
        return _base_result(packet_dir, packet, "blocked", "environment blocker", ["aws_cli_missing"], [])
    commands = _setup_commands(aws, packet)
    executed: list[dict[str, Any]] = []
    head = _run([aws, "s3api", "head-bucket", "--bucket", packet["bucket"]])
    executed.append(head)
    if head["exit_code"] == 0:
        return _base_result(packet_dir, packet, "blocked", "failure", ["bucket_exists_not_proven_smoke_owned"], executed)
    for command in commands:
        result = _run(command)
        executed.append(result)
        if result["exit_code"] != 0:
            return _base_result(packet_dir, packet, "blocked", _result_kind(result), [_failure_reason(result)], executed)
    payload = _base_result(packet_dir, packet, "primary", "success", [], executed)
    payload["live_env_values"] = _live_env_values(packet)
    payload["created_resources"] = _resource_refs(packet)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    payload = build_setup_result(
        packet_dir=Path(str(args.packet_dir)).resolve(),
        execute_live_aws=bool(args.execute_live_aws),
        acknowledge_cost_and_mutation=bool(args.acknowledge_cost_and_mutation),
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
                    f"observed_path={persisted.get('observed_path')}",
                    f"provider_calls_executed={len(persisted.get('provider_calls_executed') or [])}",
                    f"output={relative_to_repo(output)}",
                ]
            )
        )
    return 0 if persisted.get("observed_result") == "success" else 1


def _load_packet(packet_dir: Path) -> dict[str, Any]:
    wrapper = _load_json(packet_dir / WRAPPER_PACKET)
    if wrapper:
        return {
            "bucket": str(wrapper.get("bucket") or ""),
            "key": str(wrapper.get("key") or ""),
            "region": str(wrapper.get("region") or ""),
            "model_id": str(wrapper.get("model_id") or ""),
            "table_name": str(wrapper.get("table_name") or ""),
            "s3_plan_uri": str(wrapper.get("s3_plan_uri") or ""),
            "plan_path": str(packet_dir / "terraform-plan-safe-smoke.plan.json"),
            "smoke_owner_marker": str(wrapper.get("smoke_owner_marker") or ""),
            "expected_plan_hash": str(wrapper.get("expected_plan_hash") or ""),
            "packet_ref": relative_to_repo(packet_dir / WRAPPER_PACKET),
        }
    setup = _load_json(packet_dir / SETUP_PACKET)
    if setup:
        return {
            "bucket": str(setup.get("bucket") or ""),
            "key": str(setup.get("key") or ""),
            "region": str(setup.get("region") or ""),
            "model_id": str(setup.get("model_id") or ""),
            "table_name": str(setup.get("table_name") or ""),
            "s3_plan_uri": str(setup.get("s3_plan_uri") or ""),
            "plan_path": str(packet_dir / "terraform-plan-safe-smoke.plan.json"),
            "smoke_owner_marker": str(setup.get("smoke_owner_marker") or ""),
            "expected_plan_hash": str(setup.get("expected_plan_hash") or ""),
            "packet_ref": relative_to_repo(packet_dir / SETUP_PACKET),
        }
    return {"error": f"packet_missing:{relative_to_repo(packet_dir)}"}


def _setup_commands(aws: str, packet: dict[str, str]) -> list[list[str]]:
    create_bucket = [aws, "s3api", "create-bucket", "--bucket", packet["bucket"], "--region", packet["region"]]
    if packet["region"] != "us-east-1":
        create_bucket.extend(["--create-bucket-configuration", f"LocationConstraint={packet['region']}"])
    return [
        create_bucket,
        [
            aws,
            "s3api",
            "put-public-access-block",
            "--bucket",
            packet["bucket"],
            "--public-access-block-configuration",
            "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true",
        ],
        [
            aws,
            "s3api",
            "put-object",
            "--bucket",
            packet["bucket"],
            "--key",
            packet["key"],
            "--body",
            packet["plan_path"],
            "--metadata",
            f"orket-smoke-owner={packet['smoke_owner_marker']}",
        ],
        [
            aws,
            "dynamodb",
            "create-table",
            "--table-name",
            packet["table_name"],
            "--region",
            packet["region"],
            "--billing-mode",
            "PAY_PER_REQUEST",
            "--attribute-definitions",
            "AttributeName=plan_hash,AttributeType=S",
            "--key-schema",
            "AttributeName=plan_hash,KeyType=HASH",
        ],
        [aws, "dynamodb", "wait", "table-exists", "--table-name", packet["table_name"], "--region", packet["region"]],
    ]


def _base_result(
    packet_dir: Path,
    packet: dict[str, Any],
    observed_path: str,
    observed_result: str,
    reasons: list[str],
    executed: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": SETUP_RESULT_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "live" if executed else "structural",
        "packet_dir": relative_to_repo(packet_dir),
        "packet_ref": str(packet.get("packet_ref") or ""),
        "observed_path": observed_path,
        "observed_result": observed_result,
        "publication_decision": "not_evaluated",
        "admission_evidence": "absent",
        "provider_calls_executed": executed,
        "blocking_reasons": reasons,
        "resource_refs": _resource_refs(packet),
        "live_env_values": _live_env_values(packet),
    }


def _resource_refs(packet: dict[str, Any]) -> dict[str, str]:
    return {
        "s3_plan_uri": str(packet.get("s3_plan_uri") or ""),
        "bucket": str(packet.get("bucket") or ""),
        "key": str(packet.get("key") or ""),
        "dynamodb_table": str(packet.get("table_name") or ""),
        "bedrock_model_id": str(packet.get("model_id") or ""),
        "aws_region": str(packet.get("region") or ""),
        "plan_hash": str(packet.get("expected_plan_hash") or ""),
    }


def _live_env_values(packet: dict[str, Any]) -> dict[str, str]:
    return {
        "AWS_REGION": str(packet.get("region") or ""),
        "AWS_DEFAULT_REGION": str(packet.get("region") or ""),
        "ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI": str(packet.get("s3_plan_uri") or ""),
        "ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID": str(packet.get("model_id") or ""),
        "ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_TABLE": str(packet.get("table_name") or ""),
        "ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_EXPECTED_PLAN_HASH": str(packet.get("expected_plan_hash") or ""),
    }


def _run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    return {
        "command": _display_command(command),
        "exit_code": completed.returncode,
        "stdout": _safe_text(completed.stdout),
        "stderr": _safe_text(completed.stderr),
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _display_command(command: list[str]) -> str:
    return " ".join("aws" if index == 0 else item for index, item in enumerate(command))


def _safe_text(value: str) -> str:
    return " ".join(str(value or "").strip().split())[:500]


def _failure_reason(result: dict[str, Any]) -> str:
    return f"aws_cli_call_failed:{result.get('command')}"


def _result_kind(result: dict[str, Any]) -> str:
    text = f"{result.get('stdout')} {result.get('stderr')}"
    return "environment blocker" if any(token in text for token in ("AccessDenied", "ExpiredToken", "credentials")) else "failure"


if __name__ == "__main__":
    raise SystemExit(main())
