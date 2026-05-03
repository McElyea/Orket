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
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY
from orket.application.services.outward_approval_service import OutwardApprovalService
from orket.application.services.outward_run_execution_service import OutwardRunExecutionService
from orket.application.services.outward_run_service import OutwardRunService
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.outward_run_witness_builder import build_outward_run_witness_package
from scripts.proof.run_outward_run_corruption_suite import run_corruption_suite
from scripts.proof.validate_outward_write_file_committed import validate_package_artifact
from scripts.proof.verify_outward_run_witness_package import verify_package

PROOF_ROOT = Path("benchmarks/results/proof")
PACKAGE_OUTPUT = PROOF_ROOT / "outward_run_witness_package.v1"
VERIFIER_OUTPUT = PROOF_ROOT / "outward_run_witness_report.json"
ARTIFACT_OUTPUT = PROOF_ROOT / "outward_write_file_validation.json"
CORRUPTION_OUTPUT = PROOF_ROOT / "outward_run_corruption_report.json"


class _Clock:
    def __init__(self) -> None:
        self._now = datetime(2026, 5, 2, 12, 0, tzinfo=UTC)

    def __call__(self) -> str:
        value = self._now.isoformat()
        self._now += timedelta(seconds=1)
        return value


async def run_proof(*, model: str, provider: str, proof_root: Path = PROOF_ROOT) -> dict[str, Any]:
    os.environ["ORKET_DISABLE_SANDBOX"] = "1"
    os.environ["ORKET_LLM_PROVIDER"] = provider
    os.environ["ORKET_MODEL_STREAM_REAL_PROVIDER"] = provider
    os.environ["ORKET_MODEL_STREAM_REAL_MODEL_ID"] = model
    proof_root.mkdir(parents=True, exist_ok=True)
    live_root = Path(".tmp/outward-write-file-approved-proof").resolve()
    if live_root.exists():
        tmp_root = (Path.cwd() / ".tmp").resolve()
        if not live_root.is_relative_to(tmp_root):
            raise RuntimeError("refusing to clear proof workspace outside .tmp")
        shutil.rmtree(live_root)
    live_root.mkdir(parents=True)
    db_path = live_root / "outward.sqlite3"
    workspace_root = live_root / "workspace-root"
    workspace_root.mkdir()
    run_id = "run-outward-write-file-approved-proof"
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
    )
    run_service = OutwardRunService(
        run_store=run_store,
        event_store=event_store,
        run_id_factory=lambda: "outward-proof",
        utc_now=clock,
    )
    run = await run_service.submit(_submission(run_id))
    paused = await execution_service.start_if_ready(run.run_id)
    proposals = await approval_store.list(status="pending", run_id=run.run_id)
    if not proposals:
        current = await run_store.get(run.run_id)
        return _blocked("approval_proposal_missing", run=current.to_status_payload() if current else {})
    approved = await approval_service.approve(proposals[0].proposal_id, operator_ref="operator:proof-runner")
    completed = await execution_service.continue_after_approval(approved.proposal_id)
    if completed.status != "completed":
        return _blocked("run_not_completed", run=completed.to_status_payload())
    await build_outward_run_witness_package(
        db_path=db_path,
        workspace_root=workspace_root,
        run_id=run.run_id,
        output_dir=proof_root / "outward_run_witness_package.v1",
    )
    verifier = verify_package(proof_root / "outward_run_witness_package.v1")
    artifact = validate_package_artifact(proof_root / "outward_run_witness_package.v1")
    corruption = run_corruption_suite(base=proof_root / "outward_run_witness_package.v1")
    write_payload_with_diff_ledger(proof_root / "outward_run_witness_report.json", verifier)
    write_payload_with_diff_ledger(proof_root / "outward_write_file_validation.json", artifact)
    write_payload_with_diff_ledger(proof_root / "outward_run_corruption_report.json", corruption)
    success = verifier.get("result") == "accepted" and artifact.get("result") == "accepted" and corruption.get("result") == "accepted"
    return {
        "schema_version": "outward_write_file_approved_proof_run.v1",
        "observed_path": "primary",
        "observed_result": "success" if success else "failure",
        "run_id": run.run_id,
        "model": model,
        "provider": provider,
        "package_path": str(proof_root / "outward_run_witness_package.v1"),
        "verifier_result": verifier.get("result"),
        "artifact_result": artifact.get("result"),
        "corruption_result": corruption.get("result"),
        "missing_evidence": _missing(verifier, artifact, corruption),
        "start_status": paused.status,
    }


def _submission(run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "namespace": f"issue_{run_id}",
        "task": {
            "description": "Write the approved outward proof file.",
            "instruction": (
                "Produce exactly one write_file tool call with path proof-output.txt "
                "and content outward proof live content."
            ),
            "acceptance_contract": {
                "governed_tool_call": {
                    "tool": "write_file",
                    "args": {"path": "proof-output.txt", "content": "contract placeholder"},
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
        "schema_version": "outward_write_file_approved_proof_run.v1",
        "observed_path": "blocked",
        "observed_result": "failure",
        "run_id": str(run.get("run_id") or ""),
        "missing_evidence": [reason],
        "run": run,
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the outward write_file approved proof chain.")
    parser.add_argument("--provider", default="ollama", help="Local provider backend.")
    parser.add_argument("--model", default="qwen2.5-coder:7b", help="Configured local model id.")
    parser.add_argument("--output", default=str(PROOF_ROOT / "outward_write_file_approved_proof_run.json"))
    parser.add_argument("--json", action="store_true", help="Print persisted proof-run report.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = asyncio.run(run_proof(model=str(args.model), provider=str(args.provider)))
    persisted = write_payload_with_diff_ledger(Path(str(args.output)).resolve(), report)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(f"observed_result={persisted.get('observed_result')} missing={persisted.get('missing_evidence')}")
    return 0 if persisted.get("observed_result") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
