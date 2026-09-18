"""Capture result publication inputs and retain each admitted file worker."""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from functools import partial
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.turn_tool_control_plane_resource_lifecycle import (
    lease_id_for_run,
    namespace_resource_id_for_scope,
    reservation_id_for_run,
)
from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneService
from orket.core.contracts.protocol_receipt_timing import protocol_receipt_timing
from orket.core.contracts.tool_invocation_contracts import build_tool_invocation_manifest, compute_tool_call_hash

from .turn_tool_dispatcher_control_plane import publish_step_if_needed
from .turn_tool_dispatcher_support import resolved_declared_namespace_scopes, resolved_tool_namespace_scope


def _manifest(*, session_id, issue_id, tool_name, binding, context, operation_id, run_id, attempt_id):
    namespace_scope = resolved_tool_namespace_scope(binding=binding, context=context, issue_id=issue_id)
    return build_tool_invocation_manifest(
        run_id=session_id, tool_name=tool_name,
        ring=str((binding or {}).get("ring") or "core"),
        schema_version=str((binding or {}).get("schema_version") or "1.0.0"),
        determinism_class=str((binding or {}).get("determinism_class") or "workspace"),
        capability_profile=str((binding or {}).get("capability_profile") or "workspace"),
        tool_contract_version=str((binding or {}).get("tool_contract_version") or "1.0.0"),
        namespace_scope=namespace_scope,
        namespace_scope_rule=str((binding or {}).get("namespace_scope_rule") or "run_scope_only"),
        declared_namespace_scopes=resolved_declared_namespace_scopes(binding=binding, context=context, issue_id=issue_id),
        control_plane_run_id=run_id, control_plane_attempt_id=attempt_id,
        control_plane_step_id=operation_id if run_id is not None else None,
        control_plane_reservation_id=None if run_id is None else reservation_id_for_run(run_id=run_id),
        control_plane_lease_id=None if run_id is None else lease_id_for_run(run_id=run_id),
        control_plane_resource_id=None if run_id is None else namespace_resource_id_for_scope(namespace_scope=namespace_scope),
    )


def _receipt(*, session_id, step_id, receipt_seq, operation_id, proposal_hash, validator_version,
             protocol_hash, tool_schema_hash, index, tool_name, tool_args, result, manifest,
             retry_count, validator_duration_ms, execution_capsule, replayed):
    return {
        "run_id": session_id, "step_id": step_id, "receipt_seq": receipt_seq, "operation_id": operation_id,
        "proposal_hash": proposal_hash, "validator_version": validator_version, "protocol_hash": protocol_hash,
        "tool_schema_hash": tool_schema_hash, "tool_index": index, "tool": tool_name,
        "tool_args": tool_args, "execution_result": result, "tool_invocation_manifest": manifest,
        "tool_call_hash": compute_tool_call_hash(
            tool_name=tool_name, tool_args=tool_args,
            tool_contract_version=str(manifest.get("tool_contract_version") or ""),
            capability_profile=str(manifest.get("capability_profile") or ""),
        ),
        "artifact_digests": [], "retry_count": max(0, int(retry_count)),
        **protocol_receipt_timing(validator_duration_ms).model_dump(mode="json"),
        "execution_capsule": execution_capsule, "replayed": bool(replayed),
        **({"compat_translation": dict(result.get("compat_translation") or {})}
           if isinstance(result.get("compat_translation"), dict) else {}),
    }


async def persist_protocol_operation(
    *, session_id: str, issue_id: str, role_name: str, turn_index: int, index: int,
    step_id: str, receipt_seq: int, proposal_hash: str, validator_version: str,
    protocol_hash: str, tool_schema_hash: str, execution_capsule: dict[str, Any],
    context: dict[str, Any], tool_name: str, tool_args: dict[str, Any], result: dict[str, Any],
    binding: dict[str, Any] | None, operation_id: str, replayed: bool,
    persist_operation_result: Callable[..., None], append_protocol_receipt: Callable[..., dict[str, Any]],
    control_plane_enabled: bool, control_plane_service: TurnToolControlPlaneService | None,
    control_plane_run_id: str | None, control_plane_attempt_id: str | None, retry_count: int,
) -> str | None:
    tool_args, result, binding, execution_capsule = deepcopy((tool_args, result, binding, execution_capsule))
    identity = dict(session_id=session_id, issue_id=issue_id, role_name=role_name, turn_index=turn_index)
    manifest = _manifest(session_id=session_id, issue_id=issue_id, tool_name=tool_name, binding=binding,
        context=context, operation_id=operation_id, run_id=control_plane_run_id, attempt_id=control_plane_attempt_id)
    # Resolve only the context values this publication needs; context also contains live owners.
    receipt = _receipt(session_id=session_id, step_id=step_id, receipt_seq=receipt_seq, operation_id=operation_id,
        proposal_hash=proposal_hash, validator_version=validator_version, protocol_hash=protocol_hash,
        tool_schema_hash=tool_schema_hash, index=index, tool_name=tool_name, tool_args=tool_args, result=result,
        manifest=manifest, retry_count=retry_count, validator_duration_ms=context.get("validator_duration_ms"),
        execution_capsule=execution_capsule, replayed=replayed)
    await run_owned_thread(partial(persist_operation_result, **identity, operation_id=operation_id,
        tool_name=tool_name, tool_args=tool_args, result=result), label="turn-operation-result")
    await run_owned_thread(partial(append_protocol_receipt, **identity, receipt=receipt), label="turn-protocol-receipt")
    return await publish_step_if_needed(
        control_plane_enabled=control_plane_enabled, control_plane_service=control_plane_service,
        control_plane_run_id=control_plane_run_id, control_plane_attempt_id=control_plane_attempt_id,
        tool_name=tool_name, tool_args=tool_args, result=result, binding=binding,
        operation_id=operation_id, replayed=bool(replayed),
    )


async def persist_non_protocol_tool_result_if_needed(
    *, persist_tool_result: Callable[..., None], persist_operation_result: Callable[..., None],
    session_id: str, issue_id: str, role_name: str, turn_index: int, tool_name: str,
    tool_args: dict[str, Any], result: dict[str, Any], control_plane_enabled: bool,
    control_plane_service: TurnToolControlPlaneService | None, control_plane_run_id: str | None,
    control_plane_attempt_id: str | None, binding: dict[str, Any] | None, operation_id: str, replayed: bool,
) -> str | None:
    tool_args, result, binding = deepcopy((tool_args, result, binding))
    payload = dict(session_id=session_id, issue_id=issue_id, role_name=role_name, turn_index=turn_index,
                   tool_name=tool_name, tool_args=tool_args, result=result)
    if control_plane_enabled:
        await run_owned_thread(partial(persist_operation_result, **payload, operation_id=operation_id),
                               label="turn-operation-result")
    await run_owned_thread(partial(persist_tool_result, **payload), label="turn-tool-result")
    return await publish_step_if_needed(
        control_plane_enabled=control_plane_enabled, control_plane_service=control_plane_service,
        control_plane_run_id=control_plane_run_id, control_plane_attempt_id=control_plane_attempt_id,
        tool_name=tool_name, tool_args=tool_args, result=result, binding=binding,
        operation_id=operation_id, replayed=bool(replayed),
    )
