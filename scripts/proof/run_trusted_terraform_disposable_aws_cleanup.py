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
from scripts.proof.run_trusted_terraform_disposable_aws_setup import WRAPPER_PACKET
from scripts.proof.trusted_terraform_plan_decision_contract import now_utc_iso, relative_to_repo

CLEANUP_RESULT_SCHEMA_VERSION = "trusted_terraform_disposable_aws_cleanup_result.v1"
DEFAULT_PACKET_DIR = REPO_ROOT / "workspace" / "trusted_terraform_live_setup"
DEFAULT_OUTPUT = DEFAULT_PACKET_DIR / "aws-cleanup-result.json"
SETUP_PACKET = "trusted_terraform_plan_decision_live_setup_packet.json"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Explicit opt-in AWS cleanup runner for disposable Terraform smoke resources.")
    parser.add_argument("--packet-dir", default=str(DEFAULT_PACKET_DIR))
    parser.add_argument("--execute-live-aws", action="store_true")
    parser.add_argument("--acknowledge-delete", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true", help="Print persisted cleanup result JSON.")
    return parser.parse_args(argv)


def build_cleanup_result(*, packet_dir: Path, execute_live_aws: bool, acknowledge_delete: bool) -> dict[str, Any]:
    packet = _load_packet(packet_dir)
    if not execute_live_aws or not acknowledge_delete:
        return _result(packet_dir, packet, "blocked", "environment blocker", "not_started", ["live_aws_cleanup_flags_missing"], [], [])
    if packet.get("error"):
        return _result(packet_dir, packet, "blocked", "failure", "blocked", [str(packet["error"])], [], [])
    aws = shutil.which("aws")
    if not aws:
        return _result(packet_dir, packet, "blocked", "environment blocker", "blocked", ["aws_cli_missing"], [], [])
    executed: list[dict[str, Any]] = []
    deleted: list[str] = []
    errors: list[str] = []
    for command, resource_ref in _cleanup_commands(aws, packet):
        call = _run(command)
        executed.append(call)
        if call["exit_code"] == 0 or _not_found(call):
            deleted.append(resource_ref)
        else:
            errors.append(f"aws_cli_call_failed:{call['command']}")
    observed = "success" if not errors else _result_kind(executed[-1])
    return _result(
        packet_dir,
        packet,
        "primary" if not errors else "blocked",
        observed,
        "cleanup_complete" if not errors else "cleanup_failed",
        errors,
        executed,
        deleted,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    payload = build_cleanup_result(
        packet_dir=Path(str(args.packet_dir)).resolve(),
        execute_live_aws=bool(args.execute_live_aws),
        acknowledge_delete=bool(args.acknowledge_delete),
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
                    f"cleanup_state={persisted.get('cleanup_state')}",
                    f"provider_calls_executed={len(persisted.get('provider_calls_executed') or [])}",
                    f"output={relative_to_repo(output)}",
                ]
            )
        )
    return 0 if persisted.get("observed_result") == "success" else 1


def _load_packet(packet_dir: Path) -> dict[str, Any]:
    wrapper = _load_json(packet_dir / WRAPPER_PACKET)
    setup = _load_json(packet_dir / SETUP_PACKET)
    source = wrapper or setup
    if not source:
        return {"error": f"packet_missing:{relative_to_repo(packet_dir)}"}
    return {
        "bucket": str(source.get("bucket") or ""),
        "key": str(source.get("key") or ""),
        "region": str(source.get("region") or ""),
        "table_name": str(source.get("table_name") or ""),
        "s3_plan_uri": str(source.get("s3_plan_uri") or ""),
        "packet_ref": relative_to_repo(packet_dir / (WRAPPER_PACKET if wrapper else SETUP_PACKET)),
    }


def _cleanup_commands(aws: str, packet: dict[str, str]) -> list[tuple[list[str], str]]:
    return [
        (
            [aws, "s3api", "delete-object", "--bucket", packet["bucket"], "--key", packet["key"]],
            str(packet["s3_plan_uri"]),
        ),
        (
            [aws, "s3api", "delete-bucket", "--bucket", packet["bucket"], "--region", packet["region"]],
            str(packet["bucket"]),
        ),
        (
            [aws, "dynamodb", "delete-table", "--table-name", packet["table_name"], "--region", packet["region"]],
            str(packet["table_name"]),
        ),
        (
            [aws, "dynamodb", "wait", "table-not-exists", "--table-name", packet["table_name"], "--region", packet["region"]],
            str(packet["table_name"]),
        ),
    ]


def _result(
    packet_dir: Path,
    packet: dict[str, Any],
    observed_path: str,
    observed_result: str,
    cleanup_state: str,
    errors: list[str],
    executed: list[dict[str, Any]],
    deleted_resources: list[str],
) -> dict[str, Any]:
    resource_refs = [str(packet.get("s3_plan_uri") or ""), str(packet.get("bucket") or ""), str(packet.get("table_name") or "")]
    return {
        "schema_version": CLEANUP_RESULT_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "live" if executed else "structural",
        "packet_dir": relative_to_repo(packet_dir),
        "packet_ref": str(packet.get("packet_ref") or ""),
        "cleanup_state": cleanup_state,
        "observed_path": observed_path,
        "observed_result": observed_result,
        "publication_decision": "not_evaluated",
        "admission_evidence": "absent",
        "provider_calls_executed": executed,
        "deleted_resources": deleted_resources,
        "remaining_resources": [item for item in resource_refs if item and item not in deleted_resources],
        "errors": errors,
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


def _not_found(call: dict[str, Any]) -> bool:
    text = f"{call.get('stdout')} {call.get('stderr')}"
    return any(token in text for token in ("NoSuchBucket", "NoSuchKey", "ResourceNotFoundException", "Not Found"))


def _result_kind(result: dict[str, Any]) -> str:
    text = f"{result.get('stdout')} {result.get('stderr')}"
    return "environment blocker" if any(token in text for token in ("AccessDenied", "ExpiredToken", "credentials")) else "failure"


if __name__ == "__main__":
    raise SystemExit(main())
