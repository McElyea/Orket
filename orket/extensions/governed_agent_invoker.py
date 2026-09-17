from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.adapters.execution.process_lifecycle import await_process_stopped
from orket.application.services.governed_agent_process_owner import AgentInvocationOwner
from orket.core.contracts.governed_agent_ports import (
    GovernedAgentCapabilityBroker,
    GovernedAgentInvocationBinding,
    GovernedAgentInvocationOutcome,
    InvocationStatus,
)
from orket.core.contracts.protocol_error_codes import E_AGENT_INVOCATION_OWNER_PREFIX, format_protocol_error
from orket.extensions.governed_agent_process import sanitized_agent_environment
from orket_extension_sdk import (
    AgentFrameSequenceValidator,
    AgentIterationRequest,
    AgentStdioFrame,
    FrozenJson,
    canonical_digest_sha256,
    read_agent_frame,
    validate_agent_iteration_result_against_request,
    write_agent_frame,
)
from orket_extension_sdk.manifest import AGENT_MODEL_RECEIPT_FEATURE

_PROTOCOL_VERSION = "agent_stdio_ipc.v1"
_CONTRACT_VERSION = "governed_agent_loop.v1"


class GovernedAgentSubprocessInvoker:
    """One-shot host adapter for the framed governed-agent child protocol."""

    def __init__(
        self,
        *,
        extension_root: Path,
        entrypoint: str,
        allowed_stdlib_modules: tuple[str, ...],
        broker: GovernedAgentCapabilityBroker,
        handshake_timeout_seconds: float = 10,
    ) -> None:
        if handshake_timeout_seconds <= 0:
            raise ValueError("E_AGENT_HANDSHAKE_TIMEOUT_INVALID")
        self._extension_root = extension_root.resolve()
        self._entrypoint = entrypoint
        self._allowed_stdlib_modules = tuple(sorted(set(allowed_stdlib_modules)))
        self._broker = broker
        self._handshake_timeout_seconds = handshake_timeout_seconds
        self._active: dict[str, AgentInvocationOwner] = {}
        self._owner_loop: asyncio.AbstractEventLoop | None = None
        self.last_diagnostic_tail = ""

    async def invoke_once(
        self, *, binding: GovernedAgentInvocationBinding, request_payload: Mapping[str, Any],
    ) -> GovernedAgentInvocationOutcome:
        self._require_owner_loop()
        request = AgentIterationRequest.from_wire(dict(request_payload))
        self._validate_binding(binding, request)
        return await run_owned_io(lambda: self._invoke_owned(binding, request),
                                  label="governed-agent-invocation", preserve_failure=True, cancel_on_interrupt=True)

    def _require_owner_loop(self):
        loop = asyncio.get_running_loop()
        if self._owner_loop is None:
            self._owner_loop = loop
        elif loop is not self._owner_loop:
            raise ValueError(format_protocol_error(E_AGENT_INVOCATION_OWNER_PREFIX, "event_loop_mismatch"))

    async def _invoke_owned(self, binding, request):
        # Async callers share one loop: admission has no await between lookup and
        # insertion. The owner is visible to cancellation before native launch.
        if binding.invocation_id in self._active:
            return self._failure("protocol_failed", binding, "E_AGENT_INVOCATION_ALREADY_ACTIVE", False)
        active = AgentInvocationOwner(binding=binding)
        active.parent_frames = AgentFrameSequenceValidator(
            invocation_id=binding.invocation_id, direction="parent_to_child")
        self._active[binding.invocation_id] = active
        try:
            await active.launch(self._start_child)
            outcome = await self._invoke_active(active, request)
        finally:
            await run_owned_io(lambda: self._finish_active(active),
                               label="governed-agent-teardown", preserve_failure=True)
        return self._with_stopped(outcome, active.finished.is_set())

    async def _invoke_active(self, active, request):
        if active.cancelled:
            return self._failure("cancelled", active.binding, "E_AGENT_BROKER_CANCELLED", False)
        try:
            await self._send_bootstrap(active, request)
            outcome = await self._exchange(active, request)
            active.process.stdin.close()
            await active.process.stdin.wait_closed()
            await await_process_stopped(active.process, timeout_seconds=5)
            return outcome
        except asyncio.IncompleteReadError:
            status: InvocationStatus = "cancelled" if active.cancelled else "protocol_failed"
            return self._failure(status, active.binding, "E_AGENT_CHILD_DISCONNECTED", False)
        except (ValueError, OSError) as exc:
            status = "cancelled" if active.cancelled else self._failure_status(exc)
            reason = "E_AGENT_CHILD_DISCONNECTED" if str(exc) == "E_SDK_AGENT_FRAME_INCOMPLETE" else str(exc)
            return self._failure(status, active.binding, reason, False)

    async def _finish_active(self, active):
        await active.close()
        self.last_diagnostic_tail = active.diagnostic_tail
        if self._active.get(active.binding.invocation_id) is active:
            self._active.pop(active.binding.invocation_id)

    async def cancel_and_reap(
        self, *, binding: GovernedAgentInvocationBinding, cancellation_payload: Mapping[str, Any],
        grace_period_seconds: float,
    ) -> bool:
        if grace_period_seconds < 0 or grace_period_seconds > 30:
            raise ValueError("E_AGENT_CANCELLATION_GRACE_INVALID")
        self._require_owner_loop()
        cancellation = deepcopy(dict(cancellation_payload))
        active = self._active.get(binding.invocation_id)
        if active is None:
            return True
        if active.binding != binding:
            raise ValueError("E_AGENT_CANCELLATION_BINDING_MISMATCH")
        active.cancelled = True

        async def stop():
            if (active.process is not None and active.bootstrap_sent
                    and not active.cancel_sent and active.process.returncode is None):
                active.cancel_sent = True
                await self._send_parent_frame(active, "cancel", cancellation)
            return await active.stop(grace_period_seconds)
        return await run_owned_io(stop, label="governed-agent-operator-stop", preserve_failure=True)

    async def _exchange(
        self,
        active: AgentInvocationOwner,
        request: AgentIterationRequest,
    ) -> GovernedAgentInvocationOutcome:
        child_frames = AgentFrameSequenceValidator(
            invocation_id=active.binding.invocation_id,
            direction="child_to_parent",
        )
        call_ids: set[str] = set()
        aggregate_bytes = 0
        ready_seen = False
        while True:
            if active.process.stdout is None:
                raise OSError("E_AGENT_CHILD_STDOUT_UNAVAILABLE")
            timeout = self._remaining_seconds(request)
            if not ready_seen:
                timeout = min(timeout, self._handshake_timeout_seconds)
            frame = await read_agent_frame(active.process.stdout, timeout_seconds=timeout)
            child_frames.accept(frame)
            aggregate_bytes += len(frame.model_dump_json().encode("utf-8"))
            if aggregate_bytes > request.remaining_iteration_budget.output_bytes:
                raise ValueError("E_AGENT_CHILD_AGGREGATE_OUTPUT_EXCEEDED")
            if frame.message_type == "ready":
                self._validate_ready(frame)
                ready_seen = True
            elif frame.message_type == "capability_call":
                await self._handle_call(active, request, frame, call_ids)
            elif frame.message_type == "progress":
                continue
            elif frame.message_type == "iteration_result":
                result_payload = self._payload_dict(frame)
                validate_agent_iteration_result_against_request(
                    request=request.to_wire(),
                    result=result_payload,
                )
                digest = "sha256:" + canonical_digest_sha256(result_payload)
                return GovernedAgentInvocationOutcome(
                    status="returned",
                    binding=active.binding,
                    result_payload=result_payload,
                    result_digest=digest,
                    normalized_reason=None,
                    child_confirmed_stopped=False,
                )
            else:
                raise ValueError("E_AGENT_CHILD_FRAME_UNEXPECTED")

    async def _handle_call(
        self,
        active: AgentInvocationOwner,
        request: AgentIterationRequest,
        frame: AgentStdioFrame,
        call_ids: set[str],
    ) -> None:
        call_id = str(frame.call_id or "")
        if call_id in call_ids:
            raise ValueError("E_AGENT_BROKER_CALL_ID_REUSED")
        call_ids.add(call_id)
        call_payload = self._payload_dict(frame)
        self._validate_call_identity(request, call_payload)
        if active.cancelled:
            raise ValueError("E_AGENT_BROKER_CANCELLED")
        if frame.operation not in {"model.call.v1", "memory.query.v1"}:
            raise ValueError("E_AGENT_BROKER_OPERATION_INVALID")
        result = await self._broker.dispatch_call(
            binding=active.binding,
            operation=frame.operation,
            call_payload=call_payload,
        )
        await self._send_parent_frame(
            active,
            "capability_result",
            dict(result),
            call_id=call_id,
            operation=frame.operation,
        )

    async def _send_bootstrap(self, active: AgentInvocationOwner, request: AgentIterationRequest) -> None:
        frame = AgentStdioFrame(
            invocation_id=active.binding.invocation_id,
            sequence=1,
            direction="parent_to_child",
            message_type="bootstrap",
            call_id=None,
            operation=None,
            payload=FrozenJson.freeze(request.to_wire()),
        )
        if active.parent_frames is None:
            raise ValueError("E_AGENT_PARENT_FRAME_STATE_MISSING")
        active.parent_frames.accept(frame)
        if active.process.stdin is None:
            raise OSError("E_AGENT_CHILD_STDIN_UNAVAILABLE")
        await write_agent_frame(active.process.stdin, frame)
        active.bootstrap_sent = True

    async def _send_parent_frame(
        self,
        active: AgentInvocationOwner,
        message_type: str,
        payload: dict[str, Any],
        *,
        call_id: str | None = None,
        operation: str | None = None,
    ) -> None:
        async with active.write_lock:
            frame = AgentStdioFrame.model_validate(
                {
                    "invocation_id": active.binding.invocation_id,
                    "sequence": active.parent_sequence,
                    "direction": "parent_to_child",
                    "message_type": message_type,
                    "call_id": call_id,
                    "operation": operation,
                    "payload": payload,
                }
            )
            if active.parent_frames is None:
                raise ValueError("E_AGENT_PARENT_FRAME_STATE_MISSING")
            active.parent_frames.accept(frame)
            if active.process.stdin is None:
                raise OSError("E_AGENT_CHILD_STDIN_UNAVAILABLE")
            await write_agent_frame(active.process.stdin, frame)
            active.parent_sequence += 1

    async def _start_child(self) -> asyncio.subprocess.Process:
        if not await run_owned_thread(self._extension_root.is_dir, label="governed-agent-root-check"):
            raise FileNotFoundError(f"E_AGENT_EXTENSION_ROOT_MISSING: {self._extension_root}")
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "orket.extensions.agent_workload_subprocess",
            str(self._extension_root),
            self._entrypoint,
            json.dumps(list(self._allowed_stdlib_modules), separators=(",", ":")),
            cwd=str(self._extension_root),
            env=sanitized_agent_environment(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        return process

    @staticmethod
    def _validate_binding(binding: GovernedAgentInvocationBinding, request: AgentIterationRequest) -> None:
        identity = request.identity
        expected_digest = "sha256:" + canonical_digest_sha256(request.to_wire())
        if expected_digest != binding.request_digest:
            raise ValueError("E_AGENT_REQUEST_DIGEST_MISMATCH")
        if (
            identity.run_id != binding.run_id
            or identity.attempt_id != binding.attempt_id
            or identity.step_id != binding.step_id
            or identity.iteration_ordinal != binding.iteration_ordinal
            or identity.invocation_id != binding.invocation_id
            or identity.fencing_generation != binding.fencing_generation
            or request.cancellation.cancellation_epoch != binding.cancellation_epoch
            or request.deadline_utc != binding.deadline_utc
        ):
            raise ValueError("E_AGENT_INVOCATION_BINDING_MISMATCH")

    @staticmethod
    def _validate_call_identity(request: AgentIterationRequest, payload: dict[str, Any]) -> None:
        if payload.get("identity") != request.identity.model_dump(mode="json"):
            raise ValueError("E_AGENT_BROKER_CALL_IDENTITY_MISMATCH")

    @staticmethod
    def _validate_ready(frame: AgentStdioFrame) -> None:
        payload = frame.payload.thaw()
        if payload != {
            "supported_contract_versions": [_CONTRACT_VERSION],
            "supported_protocol_versions": [_PROTOCOL_VERSION],
            "supported_model_receipt_versions": [AGENT_MODEL_RECEIPT_FEATURE],
        }:
            raise ValueError("E_AGENT_READY_FEATURE_MISMATCH")

    @staticmethod
    def _payload_dict(frame: AgentStdioFrame) -> dict[str, Any]:
        payload = frame.payload.thaw()
        if not isinstance(payload, dict):
            raise ValueError("E_AGENT_FRAME_PAYLOAD_OBJECT_REQUIRED")
        return payload

    @staticmethod
    def _remaining_seconds(request: AgentIterationRequest) -> float:
        deadline = datetime.fromisoformat(request.deadline_utc.replace("Z", "+00:00"))
        return max(0.001, (deadline - datetime.now(UTC)).total_seconds())

    @staticmethod
    def _failure_status(exc: Exception) -> InvocationStatus:
        return "timed_out" if "TIMEOUT" in str(exc).upper() else "protocol_failed"

    @staticmethod
    def _failure(
        status: InvocationStatus,
        binding: GovernedAgentInvocationBinding,
        reason: str,
        stopped: bool,
    ) -> GovernedAgentInvocationOutcome:
        return GovernedAgentInvocationOutcome(
            status=status,
            binding=binding,
            result_payload=None,
            result_digest=None,
            normalized_reason=reason or status,
            child_confirmed_stopped=stopped,
        )

    @staticmethod
    def _with_stopped(
        outcome: GovernedAgentInvocationOutcome,
        stopped: bool,
    ) -> GovernedAgentInvocationOutcome:
        return GovernedAgentInvocationOutcome(
            status=outcome.status,
            binding=outcome.binding,
            result_payload=outcome.result_payload,
            result_digest=outcome.result_digest,
            normalized_reason=outcome.normalized_reason,
            child_confirmed_stopped=stopped,
        )
