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
from scripts.proof.trusted_terraform_plan_decision_contract import PROOF_RESULTS_ROOT, now_utc_iso, relative_to_repo

HANDOFF_SCHEMA_VERSION = "northstar_trusted_terraform_smoke_handoff.v1"
DEFAULT_PACKET_DIR = REPO_ROOT / "workspace" / "trusted_terraform_live_setup"
DEFAULT_OUTPUT = DEFAULT_PACKET_DIR / "northstar-handoff.json"
DEFAULT_MARKDOWN_OUTPUT = DEFAULT_PACKET_DIR / "NORTHSTAR_HANDOFF.md"
DEFAULT_RUNTIME_OUTPUT = PROOF_RESULTS_ROOT / "trusted_terraform_plan_decision_live_runtime.json"
DEFAULT_GATE_OUTPUT = PROOF_RESULTS_ROOT / "trusted_terraform_plan_decision_publication_gate.json"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write NorthStar handoff for disposable Terraform smoke evidence.")
    parser.add_argument("--packet-dir", default=str(DEFAULT_PACKET_DIR))
    parser.add_argument("--runtime-smoke-output", default=str(DEFAULT_RUNTIME_OUTPUT))
    parser.add_argument("--publication-gate-output", default=str(DEFAULT_GATE_OUTPUT))
    parser.add_argument("--setup-result", default="")
    parser.add_argument("--cleanup-result", default="")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN_OUTPUT))
    parser.add_argument("--json", action="store_true", help="Print persisted handoff JSON.")
    return parser.parse_args(argv)


def build_handoff(
    *,
    packet_dir: Path,
    runtime_smoke_output: Path,
    publication_gate_output: Path,
    setup_result: Path | None = None,
    cleanup_result: Path | None = None,
) -> dict[str, Any]:
    packet = _load_packet(packet_dir)
    runtime = _load_json(runtime_smoke_output)
    gate = _load_json(publication_gate_output)
    setup = _load_json(setup_result or (packet_dir / "aws-setup-result.json"))
    cleanup = _load_json(cleanup_result or (packet_dir / "aws-cleanup-result.json"))
    status, reason = _reopen_status(runtime, cleanup)
    return {
        "schema_version": HANDOFF_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "observed_path": "primary" if status.startswith("ready") else "blocked",
        "observed_result": "success" if status.startswith("ready") else "environment blocker",
        "publication_decision": "not_evaluated",
        "admission_status": "not_admitted",
        "s3_proof_input_ref": _first(packet, runtime, "s3_plan_uri", "plan_s3_uri"),
        "bedrock_model_id": _first(packet, runtime, "model_id", "bedrock_model_id"),
        "aws_region": _first(packet, runtime, "region", "aws_region"),
        "dynamodb_table": _first(packet, runtime, "table_name", "dynamodb_table"),
        "plan_hash": _first(packet, runtime, "expected_plan_hash", "plan_hash"),
        "fixture_seed": str(_nested(packet, "fixture_metadata", "fixture_seed") or ""),
        "fixture_kind": str(_nested(packet, "fixture_metadata", "fixture_kind") or ""),
        "expected_verdict": str(_nested(packet, "fixture_metadata", "expected_verdict") or ""),
        "runtime_smoke_output": relative_to_repo(runtime_smoke_output),
        "setup_result": _summarize_result(setup, setup_result or (packet_dir / "aws-setup-result.json")),
        "cleanup_state": str(cleanup.get("cleanup_state") or "missing"),
        "cleanup_result": _summarize_result(cleanup, cleanup_result or (packet_dir / "aws-cleanup-result.json")),
        "publication_gate_readiness_status": str(gate.get("publication_decision") or "missing"),
        "northstar_reopen_status": status,
        "blocked_reason": reason,
        "next_action": _next_action(status),
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    output = Path(str(args.output)).resolve()
    payload = build_handoff(
        packet_dir=Path(str(args.packet_dir)).resolve(),
        runtime_smoke_output=Path(str(args.runtime_smoke_output)).resolve(),
        publication_gate_output=Path(str(args.publication_gate_output)).resolve(),
        setup_result=Path(str(args.setup_result)).resolve() if str(args.setup_result).strip() else None,
        cleanup_result=Path(str(args.cleanup_result)).resolve() if str(args.cleanup_result).strip() else None,
    )
    persisted = write_payload_with_diff_ledger(output, payload)
    markdown_output = Path(str(args.markdown_output)).resolve()
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(_markdown(persisted), encoding="utf-8")
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={persisted.get('observed_result')}",
                    f"northstar_reopen_status={persisted.get('northstar_reopen_status')}",
                    f"output={relative_to_repo(output)}",
                ]
            )
        )
    return 0 if persisted.get("northstar_reopen_status", "").startswith("ready") else 1


def _reopen_status(runtime: dict[str, Any], cleanup: dict[str, Any]) -> tuple[str, str]:
    if runtime.get("observed_result") != "success":
        return "blocked", f"runtime_smoke_{runtime.get('observed_result') or 'missing'}"
    if cleanup.get("observed_result") != "success" or cleanup.get("cleanup_state") != "cleanup_complete":
        return "blocked", f"cleanup_{cleanup.get('cleanup_state') or cleanup.get('observed_result') or 'missing'}"
    return "ready_for_same_change_admission_rerun", ""


def _next_action(status: str) -> str:
    if status == "ready_for_same_change_admission_rerun":
        return "rerun the dependent NorthStar Workstream 2 proof envelope in the same change before any admission wording"
    return "resolve blocked_reason, rerun live smoke, prove cleanup, then write a new handoff"


def _load_packet(packet_dir: Path) -> dict[str, Any]:
    return _load_json(packet_dir / "northstar-disposable-aws-smoke-packet.json") or _load_json(
        packet_dir / "trusted_terraform_plan_decision_live_setup_packet.json"
    )


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    payload.pop("diff_ledger", None)
    return payload


def _first(primary: dict[str, Any], secondary: dict[str, Any], primary_key: str, secondary_key: str) -> str:
    return str(primary.get(primary_key) or secondary.get(secondary_key) or "")


def _nested(payload: dict[str, Any], key: str, nested_key: str) -> Any:
    value = payload.get(key)
    return value.get(nested_key) if isinstance(value, dict) else ""


def _summarize_result(payload: dict[str, Any], path: Path) -> dict[str, Any]:
    return {
        "ref": relative_to_repo(path),
        "observed_path": str(payload.get("observed_path") or "missing"),
        "observed_result": str(payload.get("observed_result") or "missing"),
    }


def _markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# NorthStar Trusted Terraform Smoke Handoff",
            "",
            f"- NorthStar reopen status: `{payload.get('northstar_reopen_status')}`",
            f"- Blocked reason: `{payload.get('blocked_reason') or ''}`",
            f"- S3 proof input: `{payload.get('s3_proof_input_ref')}`",
            f"- Bedrock model: `{payload.get('bedrock_model_id')}`",
            f"- DynamoDB table: `{payload.get('dynamodb_table')}`",
            f"- Plan hash: `{payload.get('plan_hash')}`",
            f"- Next action: {payload.get('next_action')}",
            "",
            "This handoff is not public admission evidence by itself.",
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
