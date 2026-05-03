#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY
from orket.application.services.outward_approval_service import OutwardApprovalService
from orket.application.services.outward_model_tool_call_service import OutwardModelToolCallService
from orket.application.services.outward_run_execution_service import OutwardRunExecutionService
from orket.application.services.outward_run_service import OutwardRunService
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.outward_run_witness_builder import build_outward_run_witness_package
from scripts.proof.outward_run_witness_contract import COMPARE_SCOPE_DENIED
from scripts.proof.run_outward_run_corruption_suite import run_corruption_suite
from scripts.proof.verify_outward_run_witness_package import verify_package

PROOF_ROOT = Path("benchmarks/results/proof")
PACKAGE_OUTPUT = PROOF_ROOT / "outward_run_denied_witness_package.v1"
VERIFIER_OUTPUT = PROOF_ROOT / "outward_run_denied_witness_report.json"
CORRUPTION_OUTPUT = PROOF_ROOT / "outward_run_corruption_report.json"


class _Clock:
    def __init__(self) -> None:
        self._now = datetime(2026, 5, 2, 12, 0, tzinfo=UTC)

    def __call__(self) -> str:
        value = self._now.isoformat()
        self._now += timedelta(seconds=1)
        return value


class _ProofModelClient:
    async def complete(self, messages, runtime_context=None):
        return SimpleNamespace(
            content="",
            raw={
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": {"path": "denied-proof-output.txt", "content": "denied proof content"},
                        },
                    }
                ],
                "provider_name": "proof-local",
                "provider_backend": "proof-local",
                "model": "deterministic-denial-proof-client",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                "latency_ms": 0,
                "orket_session_id": "proof-denial-session",
                "openai_compat": {"choices": [{"finish_reason": "tool_calls"}]},
            },
        )

    async def close(self) -> None:
        return None


async def run_proof(*, proof_root: Path = PROOF_ROOT, package_output: Path = PACKAGE_OUTPUT) -> dict[str, Any]:
    os.environ["ORKET_DISABLE_SANDBOX"] = "1"
    proof_root.mkdir(parents=True, exist_ok=True)
    live_root = Path(".tmp/outward-write-file-denied-proof").resolve()
    if live_root.exists():
        tmp_root = (Path.cwd() / ".tmp").resolve()
        if not live_root.is_relative_to(tmp_root):
            raise RuntimeError("refusing to clear proof workspace outside .tmp")
        shutil.rmtree(live_root)
    live_root.mkdir(parents=True)
    db_path = live_root / "outward.sqlite3"
    workspace_root = live_root / "workspace-root"
    workspace_root.mkdir()
    run_id = "run-outward-write-file-denied-proof"
    clock = _Clock()
    run_store = OutwardRunStore(db_path)
    event_store = OutwardRunEventStore(db_path)
    approval_store = OutwardApprovalStore(db_path)
    approval_service = OutwardApprovalService(
        approval_store=approval_store,
        run_store=run_store,
        event_store=event_store,
        connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        utc_now=clock,
    )
    execution_service = OutwardRunExecutionService(
        run_store=run_store,
        event_store=event_store,
        approval_service=approval_service,
        connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        workspace_root=workspace_root,
        utc_now=clock,
        model_tool_call_service=OutwardModelToolCallService(
            connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
            workspace_root=workspace_root,
            model_client_factory=_ProofModelClient,
        ),
    )
    run_service = OutwardRunService(
        run_store=run_store,
        event_store=event_store,
        run_id_factory=lambda: "outward-denial-proof",
        utc_now=clock,
    )
    run = await run_service.submit(_submission(run_id))
    paused = await execution_service.start_if_ready(run.run_id)
    proposals = await approval_store.list(status="pending", run_id=run.run_id)
    if not proposals:
        current = await run_store.get(run.run_id)
        return _blocked("approval_proposal_missing", run=current.to_status_payload() if current else {})
    denied = await approval_service.deny(proposals[0].proposal_id, operator_ref="operator:proof-runner", reason="operator denied proof")
    completed = await execution_service.continue_after_denial(denied.proposal_id)
    target = workspace_root / "denied-proof-output.txt"
    if target.exists():
        return _blocked("denied_effect_was_written", run=completed.to_status_payload())
    await build_outward_run_witness_package(
        db_path=db_path,
        workspace_root=workspace_root,
        run_id=run.run_id,
        output_dir=package_output,
        scope=COMPARE_SCOPE_DENIED,
    )
    verifier = verify_package(package_output, scope=COMPARE_SCOPE_DENIED)
    corruption = run_corruption_suite(denial_base=package_output)
    write_payload_with_diff_ledger(VERIFIER_OUTPUT, verifier)
    write_payload_with_diff_ledger(CORRUPTION_OUTPUT, corruption)
    success = completed.status == "completed" and verifier.get("result") == "accepted" and corruption.get("result") == "accepted"
    return {
        "schema_version": "outward_write_file_denied_proof_run.v1",
        "observed_path": "primary",
        "observed_result": "success" if success else "failure",
        "run_id": run.run_id,
        "package_path": str(package_output),
        "proof_model_source": "deterministic_local_model_client",
        "verifier_result": verifier.get("result"),
        "corruption_result": corruption.get("result"),
        "missing_evidence": _missing(verifier, corruption),
        "start_status": paused.status,
        "target_absent": not target.exists(),
    }


def _submission(run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "namespace": f"issue_{run_id}",
        "task": {
            "description": "Write the denied outward proof file.",
            "instruction": "Produce exactly one write_file tool call with path denied-proof-output.txt and content denied proof content.",
            "acceptance_contract": {
                "governed_tool_call": {
                    "tool": "write_file",
                    "args": {"path": "denied-proof-output.txt", "content": "contract placeholder"},
                }
            },
        },
        "policy_overrides": {"approval_required_tools": ["write_file"], "approval_timeout_seconds": 60, "max_turns": 1},
    }


def _missing(*reports: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for report in reports:
        values.extend(str(item) for item in report.get("missing_evidence") or [])
    return list(dict.fromkeys(item for item in values if item))


def _blocked(reason: str, *, run: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "outward_write_file_denied_proof_run.v1",
        "observed_path": "blocked",
        "observed_result": "failure",
        "run_id": str(run.get("run_id") or ""),
        "missing_evidence": [reason],
        "run": run,
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the outward write_file denied proof chain.")
    parser.add_argument("--package-output", default=str(PACKAGE_OUTPUT), help="Denied witness package output directory.")
    parser.add_argument("--output", default=str(PROOF_ROOT / "outward_write_file_denied_proof_run.json"))
    parser.add_argument("--json", action="store_true", help="Print persisted proof-run report.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    package_output = Path(str(args.package_output)).resolve()
    report = asyncio.run(run_proof(package_output=package_output))
    persisted = write_payload_with_diff_ledger(Path(str(args.output)).resolve(), report)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(f"observed_result={persisted.get('observed_result')} missing={persisted.get('missing_evidence')}")
    return 0 if persisted.get("observed_result") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
