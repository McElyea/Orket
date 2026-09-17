from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from orket.application.services.governed_agent_wake_commands import GovernedAgentWakeCommands


def add_governed_agent_wake_subparser(commands: Any) -> None:
    parser = commands.add_parser("wake", help="Enqueue or inspect durable manual governed-agent wakes.")
    actions = parser.add_subparsers(dest="agent_wake_command", required=True)

    enqueue = actions.add_parser("enqueue", help="Persist a manual wake for the continuous supervisor.")
    target = enqueue.add_mutually_exclusive_group(required=True)
    target.add_argument("--workload-id", help="Catalog workload for a new run.")
    target.add_argument("--run-id", help="Existing nonterminal run to wake.")
    enqueue.add_argument("--occurrence-id", required=True, help="Caller-stable manual occurrence identity.")
    enqueue.add_argument("--request", required=True, help="Validated initial iteration request JSON.")
    enqueue.add_argument("--creation-timestamp-utc", required=True)
    enqueue.add_argument("--decision-timestamp-utc", action="append", required=True)
    enqueue.add_argument("--next-lease-expires-at-utc", action="append", default=[])
    _add_common_arguments(enqueue)

    list_parser = actions.add_parser("list", help="List durable governed-agent wakes.")
    list_parser.add_argument("--run-id", help="Optional run identity filter.")
    _add_common_arguments(list_parser)

    inspect = actions.add_parser("inspect", help="Inspect one durable governed-agent wake.")
    inspect.add_argument("wake_id")
    _add_common_arguments(inspect)

    cancel = actions.add_parser("cancel", help="Publish a durable cancellation for one wake.")
    cancel.add_argument("wake_id")
    _add_control_identity_arguments(cancel)
    cancel.add_argument("--expected-cancellation-epoch", required=True, type=int)
    cancel.add_argument("--cancellation-epoch", required=True, type=int)
    _add_common_arguments(cancel)

    recover = actions.add_parser("recover", help="Resolve a stopped wake after reconciliation.")
    recover.add_argument("wake_id")
    _add_control_identity_arguments(recover)
    recover.add_argument("--expected-fencing-generation", required=True, type=int)
    recover.add_argument("--resolution", choices=("requeue", "confirm_cancelled"), required=True)
    recover.add_argument("--child-confirmed-stopped", action="store_true", required=True)
    recover.add_argument("--effect-uncertainty-cleared", action="store_true", required=True)
    recover.add_argument("--evidence-ref", action="append", required=True)
    _add_common_arguments(recover)

    action_list = actions.add_parser("actions", help="List durable controls for one wake.")
    action_list.add_argument("wake_id")
    _add_common_arguments(action_list)


async def run_governed_agent_wake_command(
    args: argparse.Namespace, commands: GovernedAgentWakeCommands,
) -> dict[str, Any]:
    command = str(args.agent_wake_command)
    if command == "enqueue":
        return await _enqueue_manual_wake(args, commands)
    if command == "list":
        return await commands.list_wakes(target_run_id=_optional_text(args.run_id))
    if command == "actions":
        return await commands.list_actions(wake_id=str(args.wake_id))
    if command in {"cancel", "recover"}:
        payload = _cancellation_payload(args) if command == "cancel" else _recovery_payload(args)
        return await commands.control(command, wake_id=str(args.wake_id), payload=payload)
    return await commands.inspect(wake_id=str(args.wake_id))



def _cancellation_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        **_control_identity_payload(args),
        "expected_cancellation_epoch": args.expected_cancellation_epoch,
        "cancellation_epoch": args.cancellation_epoch,
    }


def _recovery_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        **_control_identity_payload(args),
        "expected_fencing_generation": args.expected_fencing_generation,
        "resolution": args.resolution,
        "child_confirmed_stopped": args.child_confirmed_stopped,
        "effect_uncertainty_cleared": args.effect_uncertainty_cleared,
        "evidence_refs": list(args.evidence_ref),
    }


def _control_identity_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "action_id": args.action_id,
        "actor_ref": args.actor_ref,
        "timestamp_utc": args.timestamp_utc,
        "reason": args.reason,
    }


async def _enqueue_manual_wake(
    args: argparse.Namespace,
    commands: GovernedAgentWakeCommands,
) -> dict[str, Any]:
    request = await asyncio.to_thread(_read_json_object, str(args.request))
    run_id = _optional_text(args.run_id)
    workload_id = _optional_text(args.workload_id)
    payload = {
        "occurrence_id": str(args.occurrence_id),
        "target_kind": "existing_run" if run_id is not None else "new_run",
        "target_run_id": run_id,
        "workload_id": workload_id,
        "dispatch": {
            "schema_version": "governed_agent_wake_dispatch.v1",
            "request": request,
            "creation_timestamp_utc": str(args.creation_timestamp_utc),
            "decision_timestamps_utc": list(args.decision_timestamp_utc),
            "next_lease_expiries_utc": list(args.next_lease_expires_at_utc),
        },
    }
    return await commands.enqueue(payload)


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", required=True, help="Governed control-plane SQLite path.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")


def _add_control_identity_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--action-id", required=True)
    parser.add_argument("--actor-ref", required=True)
    parser.add_argument("--timestamp-utc", required=True)
    parser.add_argument("--reason", required=True)


def _read_json_object(raw_path: str) -> dict[str, Any]:
    path = Path(raw_path).resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("E_AGENT_REQUEST_OBJECT_REQUIRED")
    return payload


def _optional_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None
