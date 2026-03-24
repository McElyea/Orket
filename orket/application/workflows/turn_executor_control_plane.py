from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from orket.application.services.turn_tool_control_plane_service import (
    TurnToolControlPlaneError,
    TurnToolControlPlaneService,
)
from orket.application.services.turn_tool_control_plane_support import (
    attempt_id_for,
    digest,
    resource_refs,
    run_id_for,
    run_namespace_scope,
    utc_now,
)
from orket.application.workflows.protocol_hashing import hash_canonical_json
from orket.core.contracts import CheckpointRecord
from orket.core.domain import (
    AttemptState,
    CheckpointReobservationClass,
    CheckpointResumabilityClass,
    ResultClass,
    RunState,
)
from orket.domain.execution import ExecutionTurn, ToolCall


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
            "resumability_class": CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT.value,
            "recovery_mode": "pre_effect_new_attempt_only",
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


async def load_completed_turn_replay_if_needed(
    *,
    executor: Any,
    issue_id: str,
    role_name: str,
    context: dict[str, Any],
) -> ExecutionTurn | None:
    control_plane_service = _control_plane_service(executor)
    if control_plane_service is None or bool(context.get("protocol_replay_mode")):
        return None
    run_id = run_id_for(
        session_id=str(context.get("session_id", "unknown-session")),
        issue_id=issue_id,
        role_name=role_name,
        turn_index=int(context.get("turn_index", 0)),
    )
    run = await control_plane_service.execution_repository.get_run_record(run_id=run_id)
    if run is None:
        return None
    truth = await _load_successful_completed_truth(control_plane_service=control_plane_service, run=run)
    if truth is None:
        return None
    attempt = await _load_completed_attempt(control_plane_service=control_plane_service, run_id=run_id, run=run)
    steps = await control_plane_service.execution_repository.list_step_records(attempt_id=attempt.attempt_id)
    if not steps:
        raise TurnToolControlPlaneError(
            f"completed governed turn {run.run_id} is missing durable step truth for artifact replay"
        )
    tool_calls = await _load_replayed_tool_calls(
        executor=executor,
        issue_id=issue_id,
        role_name=role_name,
        context=context,
        steps=steps,
    )
    return ExecutionTurn(
        role=role_name,
        issue_id=issue_id,
        content="",
        tool_calls=tool_calls,
        tokens_used=0,
        raw={
            "control_plane_replay": {
                "artifact_reused": True,
                "run_id": run.run_id,
                "attempt_id": attempt.attempt_id,
                "final_truth_record_id": truth.final_truth_record_id,
                "authoritative_result_ref": truth.authoritative_result_ref,
                "closure_basis": truth.closure_basis.value,
            }
        },
        note="control_plane_completed_replay",
    )


async def _load_successful_completed_truth(
    *,
    control_plane_service: TurnToolControlPlaneService,
    run: Any,
):
    if run.final_truth_record_id is None:
        if run.lifecycle_state is RunState.COMPLETED:
            raise TurnToolControlPlaneError(
                f"completed governed turn {run.run_id} is missing durable final truth for artifact replay"
            )
        return None
    truth = await control_plane_service.publication.repository.get_final_truth(run_id=run.run_id)
    if truth is None:
        raise TurnToolControlPlaneError(
            f"governed turn run {run.run_id} carries final_truth_record_id without durable final truth"
        )
    if truth.result_class is ResultClass.SUCCESS and run.lifecycle_state is RunState.COMPLETED:
        return truth
    raise TurnToolControlPlaneError(
        f"governed turn run {run.run_id} already closed with "
        f"{truth.result_class.value} via {truth.closure_basis.value}; execution cannot continue"
    )


async def _load_completed_attempt(
    *,
    control_plane_service: TurnToolControlPlaneService,
    run_id: str,
    run: Any,
):
    attempt = await control_plane_service.execution_repository.get_attempt_record(
        attempt_id=run.current_attempt_id or attempt_id_for(run_id=run_id)
    )
    if attempt is None:
        raise TurnToolControlPlaneError(f"completed governed turn is missing current attempt: {run.run_id}")
    if attempt.attempt_state is not AttemptState.COMPLETED:
        raise TurnToolControlPlaneError(
            f"completed governed turn {run.run_id} has non-completed attempt {attempt.attempt_id}"
        )
    return attempt


async def _load_replayed_tool_calls(
    *,
    executor: Any,
    issue_id: str,
    role_name: str,
    context: dict[str, Any],
    steps: list[Any],
) -> list[ToolCall]:
    tool_calls: list[ToolCall] = []
    session_id = str(context.get("session_id", "unknown-session"))
    turn_index = int(context.get("turn_index", 0))
    for step in steps:
        operation_record = await asyncio.to_thread(
            executor._load_operation_result,
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            operation_id=_operation_id_for_step(step),
        )
        if not isinstance(operation_record, dict):
            raise TurnToolControlPlaneError(
                f"completed governed turn step {step.step_id} is missing durable operation truth for artifact replay"
            )
        tool_name = str(operation_record.get("tool") or "").strip()
        tool_args = operation_record.get("args")
        result = operation_record.get("result")
        if not tool_name or not isinstance(tool_args, dict) or not isinstance(result, dict):
            raise TurnToolControlPlaneError(
                f"completed governed turn step {step.step_id} has malformed operation truth for artifact replay"
            )
        tool_calls.append(
            ToolCall(
                tool=tool_name,
                args=tool_args,
                result=result,
                error=str(result.get("error") or "").strip() or None,
            )
        )
    return tool_calls


def _operation_id_for_step(step: Any) -> str:
    output_ref = str(getattr(step, "output_ref", "") or "").strip()
    prefix = "turn-tool-result:"
    if output_ref.startswith(prefix):
        return output_ref[len(prefix) :]
    return str(getattr(step, "step_id", "") or "").strip()


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
    selected_model = context.get("selected_model")
    prompt_metadata = context.get("prompt_metadata")
    state_delta = executor._state_delta_from_tool_calls(context, turn)
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
        resume_mode=bool(context.get("resume_mode")),
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
                resumability_class=CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT,
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
    "load_completed_turn_replay_if_needed",
    "write_turn_checkpoint_and_publish_if_needed",
]
