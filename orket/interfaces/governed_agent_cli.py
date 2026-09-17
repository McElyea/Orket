from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from orket.application.services.governed_agent_commands import GovernedAgentCommands
from orket.application.services.governed_agent_execution_composition import PROVIDER_CHOICES
from orket.application.services.governed_agent_submission_service import (
    GovernedAgentProviderOptions,
    GovernedAgentSubmission,
    submit_governed_agent,
)
from orket.application.services.governed_agent_wake_commands import build_governed_agent_wake_commands
from orket.interfaces.governed_agent_wake_cli import (
    add_governed_agent_wake_subparser,
    run_governed_agent_wake_command,
)


def add_governed_agent_subparser(subparsers: Any) -> None:
    parser = subparsers.add_parser("agent", help="Submit, wake, inspect, replay, or cancel a governed agent run.")
    commands = parser.add_subparsers(dest="agent_command", required=True)
    add_governed_agent_wake_subparser(commands)
    for command in ("pause", "stop"):
        control = commands.add_parser(command, help="Request control at the current iteration boundary.")
        control.add_argument("run_id")
        for flag in ("db", "action-id", "actor-ref", "timestamp-utc", "invocation-id"):
            control.add_argument(f"--{flag}", required=True)
        control.add_argument("--json", action="store_true")
    for command in ("inspect", "replay"):
        child = commands.add_parser(command, help=f"{command.title()} durable governed-agent state.")
        child.add_argument("run_id")
        child.add_argument("--db", required=True, help="Governed control-plane SQLite path.")
        child.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    cancel = commands.add_parser("cancel", help="Publish an operator cancellation for a governed agent run.")
    cancel.add_argument("run_id")
    cancel.add_argument("--db", required=True, help="Governed control-plane SQLite path.")
    cancel.add_argument("--action-id", required=True)
    cancel.add_argument("--actor-ref", required=True)
    cancel.add_argument("--timestamp-utc", required=True)
    cancel.add_argument("--reason", required=True)
    cancel.add_argument("--cancellation-epoch", required=True, type=int)
    cancel.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    submit = commands.add_parser("submit", help="Run a bounded governed-agent workload.")
    submit.add_argument("workload_id")
    submit.add_argument("--db", required=True, help="Governed control-plane SQLite path.")
    submit.add_argument("--catalog", required=True, help="Extension catalog containing the agent workload.")
    submit.add_argument("--request", required=True, help="Validated initial iteration request JSON.")
    submit.add_argument("--continuation-inputs", help="Host-only JSON mapping of iteration ordinals to context inputs.")
    submit.add_argument("--creation-timestamp-utc", required=True)
    submit.add_argument("--decision-timestamp-utc", action="append", required=True)
    submit.add_argument("--next-lease-expires-at-utc", action="append", default=[])
    provider = submit.add_mutually_exclusive_group(required=True)
    provider.add_argument("--deterministic-fixture", action="store_true")
    provider.add_argument("--model", help="Exact served model; defaults to the llama.cpp provider.")
    submit.add_argument("--provider", choices=PROVIDER_CHOICES, default=None)
    submit.add_argument("--provider-base-url", default="", help="Optional selected-provider endpoint override.")
    provider.add_argument("--ollama-model", help="Exact installed Ollama model for every role by default.")
    for role in ("planner", "actor", "critic"):
        submit.add_argument(f"--{role}-model", help=f"Exact served model override for {role}.")
    submit.add_argument("--ollama-base-url", default="", help="Optional Ollama base URL override.")
    submit.add_argument("--inventory-timeout-seconds", type=float, default=30.0)
    submit.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")


def handle_governed_agent_command(args: argparse.Namespace) -> int:
    try:
        db_path = Path(str(args.db)).resolve()
        project_root = Path.cwd().resolve()
        catalog_path = Path(str(args.catalog)).resolve() if hasattr(args, "catalog") else None
        request_path = Path(str(args.request)).resolve() if hasattr(args, "request") else None
        result = asyncio.run(_run_command(args, db_path, project_root, catalog_path, request_path))
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        result = {"ok": False, "error": str(exc)}
    if bool(getattr(args, "json", False)):
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif result.get("ok") or result.get("object_type") == "governed_agent_replay":
        print(_render_human(result))
    else:
        print(f"FAIL: {result.get('error', 'unknown governed-agent error')}")
    return 0 if result.get("ok") else 1


async def _run_command(
    args: argparse.Namespace, db_path: Path, project_root: Path,
    catalog_path: Path | None, request_path: Path | None,
) -> dict[str, Any]:
    command = str(args.agent_command)
    if command == "wake":
        return await run_governed_agent_wake_command(args, build_governed_agent_wake_commands(db_path))
    if command == "submit":
        return await submit_governed_agent(
            db_path=db_path, submission=_submission(args, project_root, catalog_path, request_path),
        )
    commands = GovernedAgentCommands(db_path)
    if command in {"inspect", "replay"}:
        return await commands.inspect(run_id=str(args.run_id), replay=command == "replay")
    if command in {"pause", "stop"}:
        return await commands.request_control(
            run_id=str(args.run_id), command=command, payload={
                "action_id": args.action_id, "actor_ref": args.actor_ref,
                "timestamp_utc": args.timestamp_utc, "invocation_id": args.invocation_id,
            },
        )
    if command == "cancel":
        return await commands.cancel(
            run_id=str(args.run_id), action_id=str(args.action_id), actor_ref=str(args.actor_ref),
            timestamp_utc=str(args.timestamp_utc), reason=str(args.reason),
            cancellation_epoch=int(args.cancellation_epoch),
        )
    raise ValueError("E_AGENT_COMMAND_UNKNOWN")


def _submission(
    args: argparse.Namespace, project_root: Path, catalog_path: Path | None, request_path: Path | None,
) -> GovernedAgentSubmission:
    if catalog_path is None or request_path is None:
        raise ValueError("E_AGENT_SUBMIT_PATHS_REQUIRED")
    return GovernedAgentSubmission(
        workload_id=str(args.workload_id), project_root=project_root, catalog_path=catalog_path,
        request_path=request_path,
        continuation_inputs_path=Path(args.continuation_inputs) if args.continuation_inputs else None,
        creation_timestamp_utc=str(args.creation_timestamp_utc),
        decision_timestamps_utc=tuple(args.decision_timestamp_utc),
        next_lease_expiries_utc=tuple(args.next_lease_expires_at_utc),
        provider=GovernedAgentProviderOptions(
            deterministic_fixture=bool(args.deterministic_fixture), provider_name=getattr(args, "provider", None),
            model=str(getattr(args, "model", "") or ""), ollama_model=str(args.ollama_model or ""),
            provider_base_url=str(getattr(args, "provider_base_url", "") or ""),
            ollama_base_url=str(args.ollama_base_url or ""),
            role_models=tuple((role, str(getattr(args, f"{role}_model", "") or ""))
                              for role in ("planner", "actor", "critic")),
            inventory_timeout_seconds=float(args.inventory_timeout_seconds),
        ),
    )


def _render_human(result: dict[str, Any]) -> str:
    object_type = str(result.get("object_type") or "")
    if object_type == "governed_agent_replay":
        reasons = list(result.get("diagnostics", []))
        reasons.extend(f"{item['invocation_id']}:{item.get('reason')}" for item in result.get("decisions", [])
                       if not item["matched"])
        return (f"agent replay: run={result['run_id']} status={result['status']} "
                f"compared={result['compared_count']}/{result['expected_count']}"
                + (" diagnostics=" + "; ".join(reasons[:5]) if reasons else ""))
    wake = result.get("wake")
    if isinstance(wake, dict):
        return f"agent wake: id={wake.get('wake_id')} state={wake.get('state')}"
    if object_type == "governed_agent_wake_list":
        return f"agent wakes: count={len(result.get('items', []))}"
    run = result.get("run")
    if isinstance(run, dict):
        return f"agent {object_type}: run={run.get('run_id')} state={run.get('lifecycle_state')}"
    return f"agent {object_type}: ok"
