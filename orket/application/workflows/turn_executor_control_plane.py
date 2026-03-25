from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneService
from orket.application.services.turn_tool_control_plane_resource_lifecycle import (
    lease_id_for_run,
    reservation_id_for_run,
)
from orket.application.services.turn_tool_control_plane_support import (
    digest,
    resource_refs,
    run_namespace_scope,
    utc_now,
)
from orket.application.workflows.protocol_hashing import hash_canonical_json
from orket.core.contracts import CheckpointRecord
from orket.core.domain import (
    CheckpointReobservationClass,
    CheckpointResumabilityClass,
)
from orket.domain.execution import ExecutionTurn


def _tool_calls_payload(turn: ExecutionTurn) -> list[dict[str, Any]]:
    return [
        {
            "tool": str(call.tool or ""),
            "args": dict(call.args or {}),
        }
        for call in list(turn.tool_calls or [])
    ]


def _proposal_hash(turn: ExecutionTurn) -> str:
    raw = turn.raw if isinstance(turn.raw, dict) else {}
    proposal_hash = str(raw.get("proposal_hash") or "").strip()
    if proposal_hash:
        return proposal_hash
    return hash_canonical_json(
        {
            "content": str(turn.content or ""),
            "tool_calls": _tool_calls_payload(turn),
        }
    )


def _checkpoint_snapshot_payload(
    *,
    session_id: str,
    issue_id: str,
    role_name: str,
    turn_index: int,
    prompt_hash: str,
    selected_model: Any,
    tool_calls: list[dict[str, Any]],
    state_delta: dict[str, Any],
    prompt_metadata: dict[str, Any] | None,
    captured_at: str,
    resume_mode: bool,
    protocol_replay_mode: bool,
    namespace_scope: str,
) -> dict[str, Any]:
    return {
        "run_id": session_id,
        "issue_id": issue_id,
        "turn_index": turn_index,
        "role": role_name,
        "namespace_scope": namespace_scope,
        "prompt_hash": prompt_hash,
        "model": selected_model,
        "tool_calls": tool_calls,
        "state_delta": state_delta,
        "prompt_metadata": prompt_metadata or {},
        "captured_at": captured_at,
        "control_plane": {
            "checkpoint_contract": "turn_executor.control_plane_checkpoint.v1",
            "resume_mode_requested": resume_mode,
            "protocol_replay_mode": protocol_replay_mode,
            "resumability_class": CheckpointResumabilityClass.RESUME_SAME_ATTEMPT.value,
            "recovery_mode": "pre_effect_same_attempt_only",
        },
    }


def _resource_dependencies(tool_calls: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for tool_call in tool_calls:
        refs.extend(
            resource_refs(
                tool_name=str(tool_call.get("tool") or ""),
                tool_args=dict(tool_call.get("args") or {}),
                result={},
            )
        )
    deduped: list[str] = []
    for ref in refs:
        if ref not in deduped:
            deduped.append(ref)
    return deduped


def _checkpoint_turn_metadata(
    *,
    executor: Any,
    turn: ExecutionTurn,
    context: dict[str, Any],
) -> tuple[Any, dict[str, Any] | None, dict[str, Any]]:
    raw = turn.raw if isinstance(turn.raw, dict) else {}
    selected_model = raw.get("model", context.get("selected_model"))
    prompt_metadata = raw.get("prompt_metadata")
    if not isinstance(prompt_metadata, dict):
        fallback_prompt_metadata = context.get("prompt_metadata")
        prompt_metadata = fallback_prompt_metadata if isinstance(fallback_prompt_metadata, dict) else None
    state_delta = raw.get("state_delta")
    if not isinstance(state_delta, dict):
        state_delta = executor._state_delta_from_tool_calls(context, turn)
    return selected_model, prompt_metadata, state_delta


async def write_turn_checkpoint_and_publish_if_needed(
    *,
    executor: Any,
    turn: ExecutionTurn,
    context: dict[str, Any],
    prompt_hash: str,
) -> None:
    session_id = str(context.get("session_id", "unknown-session"))
    issue_id = turn.issue_id
    role_name = turn.role
    turn_index = int(context.get("turn_index", 0))
    raw = turn.raw if isinstance(turn.raw, dict) else {}
    selected_model, prompt_metadata, state_delta = _checkpoint_turn_metadata(
        executor=executor,
        turn=turn,
        context=context,
    )
    tool_calls = _tool_calls_payload(turn)
    captured_at = utc_now()
    namespace_scope = run_namespace_scope(issue_id=issue_id, context=context)
    await ensure_turn_control_plane_reentry_allowed_if_needed(
        executor=executor,
        issue_id=issue_id,
        role_name=role_name,
        context=context,
    )

    await asyncio.to_thread(
        executor._write_turn_checkpoint,
        session_id=session_id,
        issue_id=issue_id,
        role_name=role_name,
        turn_index=turn_index,
        prompt_hash=prompt_hash,
        selected_model=selected_model,
        tool_calls=tool_calls,
        state_delta=state_delta,
        prompt_metadata=prompt_metadata,
    )

    control_plane_service = _control_plane_service(executor)
    if control_plane_service is None or not tool_calls or bool(context.get("protocol_replay_mode")):
        return

    run, attempt = await control_plane_service.begin_execution(
        session_id=session_id,
        issue_id=issue_id,
        role_name=role_name,
        turn_index=turn_index,
        proposal_hash=_proposal_hash(turn),
        resume_mode=bool(context.get("resume_mode"))
        and not bool((raw.get("control_plane_resume") or {}).get("artifact_reused")),
    )
    checkpoint_id = f"turn-tool-checkpoint:{attempt.attempt_id}"
    existing = await control_plane_service.publication.repository.get_checkpoint(checkpoint_id=checkpoint_id)
    if existing is None:
        snapshot_payload = _checkpoint_snapshot_payload(
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            prompt_hash=prompt_hash,
            selected_model=selected_model,
            tool_calls=tool_calls,
            state_delta=state_delta,
            prompt_metadata=prompt_metadata if isinstance(prompt_metadata, dict) else None,
            captured_at=captured_at,
            resume_mode=bool(context.get("resume_mode")),
            protocol_replay_mode=bool(context.get("protocol_replay_mode")),
            namespace_scope=namespace_scope,
        )
        snapshot_compact = json.dumps(
            snapshot_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=str,
        )
        snapshot_hash = hashlib.sha256(snapshot_compact.encode("ascii")).hexdigest()
        snapshot_ref = f"turn-tool-checkpoint-snapshot:{run.run_id}:{snapshot_hash[:16]}"
        integrity_ref = f"turn-tool-checkpoint-integrity:sha256:{snapshot_hash}"
        await asyncio.to_thread(
            executor._write_turn_artifact,
            session_id,
            issue_id,
            role_name,
            turn_index,
            f"control_plane_checkpoint_snapshot_{snapshot_hash[:16]}.json",
            json.dumps(snapshot_payload, indent=2, ensure_ascii=False, default=str),
        )
        checkpoint = await control_plane_service.publication.publish_checkpoint(
            checkpoint=CheckpointRecord(
                checkpoint_id=checkpoint_id,
                parent_ref=attempt.attempt_id,
                creation_timestamp=captured_at,
                state_snapshot_ref=snapshot_ref,
                resumability_class=CheckpointResumabilityClass.RESUME_SAME_ATTEMPT,
                invalidation_conditions=[
                    "policy_digest_mismatch",
                    "tool_plan_diverged",
                    "checkpoint_snapshot_missing",
                ],
                dependent_resource_ids=_resource_dependencies(tool_calls) + [f"namespace:{namespace_scope}"],
                dependent_effect_refs=[],
                policy_digest=run.policy_digest,
                integrity_verification_ref=integrity_ref,
            )
        )
    else:
        checkpoint = existing
        integrity_ref = checkpoint.integrity_verification_ref

    acceptance = await control_plane_service.publication.repository.get_checkpoint_acceptance(
        checkpoint_id=checkpoint.checkpoint_id
    )
    if acceptance is not None:
        return

    await control_plane_service.publication.accept_checkpoint(
        acceptance_id=f"turn-tool-checkpoint-acceptance:{attempt.attempt_id}",
        checkpoint=checkpoint,
        supervisor_authority_ref=f"turn-tool-supervisor:{run.run_id}",
        decision_timestamp=checkpoint.creation_timestamp,
        required_reobservation_class=CheckpointReobservationClass.FULL,
        integrity_verification_ref=integrity_ref,
        dependent_reservation_refs=[reservation_id_for_run(run_id=run.run_id)],
        dependent_lease_refs=[lease_id_for_run(run_id=run.run_id)],
        reservation_ids=[reservation_id_for_run(run_id=run.run_id)],
        lease_ids=[lease_id_for_run(run_id=run.run_id)],
    )


def _control_plane_service(executor: Any) -> TurnToolControlPlaneService | None:
    dispatcher = getattr(executor, "tool_dispatcher", None)
    service = getattr(dispatcher, "control_plane_service", None)
    if isinstance(service, TurnToolControlPlaneService):
        return service
    return None


async def ensure_turn_control_plane_reentry_allowed_if_needed(
    *,
    executor: Any,
    issue_id: str,
    role_name: str,
    context: dict[str, Any],
) -> None:
    service = _control_plane_service(executor)
    if service is None:
        return
    await service.ensure_reentry_allowed(
        session_id=str(context.get("session_id", "unknown-session")),
        issue_id=issue_id,
        role_name=role_name,
        turn_index=int(context.get("turn_index", 0)),
    )


__all__ = [
    "ensure_turn_control_plane_reentry_allowed_if_needed",
    "write_turn_checkpoint_and_publish_if_needed",
]
