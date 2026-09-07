from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Any, Literal, TypeVar, cast

from .agent_ipc import AgentFrameSequenceValidator, encode_agent_frame, read_agent_frame
from .agent_models import (
    AgentIterationRequest,
    AgentIterationResult,
    AgentMemoryQueryRequest,
    AgentMemoryQueryResult,
    AgentModelCallRequest,
    AgentModelCallResult,
    AgentStdioFrame,
)
from .agent_runtime import (
    AgentCancellationView,
    AgentMemoryCapability,
    AgentModelCapability,
    AgentProgressReporter,
    AgentWorkloadContext,
    AsyncAgentWorkload,
)
from .agent_types import AgentCancellation, AgentProgress, AgentWireModel, FrozenJson
from .errors import AgentBrokerDisconnected, AgentInvocationCancelled, AgentProtocolError

_PROTOCOL_VERSION = "agent_stdio_ipc.v1"
_CONTRACT_VERSION = "governed_agent_loop.v1"
_ResultT = TypeVar("_ResultT", AgentModelCallResult, AgentMemoryQueryResult)
_MessageType = Literal["ready", "capability_call", "progress", "iteration_result"]
_Operation = Literal["model.call.v1", "memory.query.v1"]


class AgentBrokerSession:
    """Child-side session for one host-issued governed-agent invocation."""

    def __init__(
        self,
        *,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        request: AgentIterationRequest,
        maximum_child_output_bytes: int,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self.request = request
        self.cancellation = AgentCancellationView(request.cancellation)
        self._inbound = AgentFrameSequenceValidator(
            invocation_id=request.identity.invocation_id,
            direction="parent_to_child",
        )
        self._outbound = AgentFrameSequenceValidator(
            invocation_id=request.identity.invocation_id,
            direction="child_to_parent",
        )
        self._outbound_sequence = 1
        self._maximum_child_output_bytes = maximum_child_output_bytes
        self._child_output_bytes = 0
        self._used_call_ids: set[str] = set()
        self._call_lock = asyncio.Lock()
        self._send_lock = asyncio.Lock()
        self._pending: tuple[str, str, asyncio.Future[AgentWireModel]] | None = None
        self._receiver: asyncio.Task[None] | None = None
        self._closed = False
        self._disconnect_error: AgentBrokerDisconnected | None = None

    @classmethod
    async def connect(
        cls,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        bootstrap_timeout_seconds: float,
    ) -> AgentBrokerSession:
        frame = await read_agent_frame(reader, timeout_seconds=bootstrap_timeout_seconds)
        if frame.message_type != "bootstrap":
            raise AgentProtocolError("E_SDK_AGENT_BOOTSTRAP_REQUIRED")
        request = AgentIterationRequest.from_wire(cast(dict[str, Any], frame.payload.thaw()))
        session = cls(
            reader=reader,
            writer=writer,
            request=request,
            maximum_child_output_bytes=request.remaining_iteration_budget.output_bytes,
        )
        session._inbound.accept(frame)
        await session._send_ready()
        session._receiver = asyncio.create_task(session._receive_loop(), name="orket-agent-broker-receiver")
        return session

    def workload_context(self) -> AgentWorkloadContext:
        return AgentWorkloadContext(
            request=self.request,
            model=_SessionModelCapability(self),
            memory=_SessionMemoryCapability(self),
            cancellation=self.cancellation,
            progress=AgentProgressReporter(
                identity=self.request.identity,
                maximum_events=256,
                publish=self.publish_progress,
            ),
        )

    async def model_call(self, request: AgentModelCallRequest) -> AgentModelCallResult:
        return await self._capability_call("model.call.v1", request, AgentModelCallResult)

    async def memory_query(self, request: AgentMemoryQueryRequest) -> AgentMemoryQueryResult:
        return await self._capability_call("memory.query.v1", request, AgentMemoryQueryResult)

    async def publish_progress(self, progress: AgentProgress) -> None:
        self._ensure_available()
        if self._pending is not None:
            raise AgentProtocolError("E_SDK_AGENT_PROGRESS_DURING_CALL")
        self._require_bound_identity(progress.identity.model_dump(mode="json"))
        await self._send("progress", progress)

    async def publish_result(self, result: AgentIterationResult) -> None:
        self._ensure_available()
        if self._pending is not None:
            raise AgentProtocolError("E_SDK_AGENT_RESULT_DURING_CALL")
        self._require_bound_identity(result.identity.model_dump(mode="json"))
        await self._send("iteration_result", result)

    async def close(self) -> None:
        self._closed = True
        receiver = self._receiver
        if receiver is not None and receiver is not asyncio.current_task():
            receiver.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await receiver

    async def __aenter__(self) -> AgentBrokerSession:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def _capability_call(
        self,
        operation: _Operation,
        request: AgentModelCallRequest | AgentMemoryQueryRequest,
        result_type: type[_ResultT],
    ) -> _ResultT:
        async with self._call_lock:
            self._ensure_available()
            call_id = str(request.call_id)
            self._require_bound_identity(request.identity.model_dump(mode="json"))
            if call_id in self._used_call_ids:
                raise AgentProtocolError("E_SDK_AGENT_CALL_ID_REUSED")
            self._used_call_ids.add(call_id)
            loop = asyncio.get_running_loop()
            future: asyncio.Future[AgentWireModel] = loop.create_future()
            self._pending = (call_id, operation, future)
            try:
                await self._send("capability_call", request, call_id=call_id, operation=operation)
                value = await future
            finally:
                self._pending = None
            if not isinstance(value, result_type):
                raise AgentProtocolError("E_SDK_AGENT_CAPABILITY_RESULT_TYPE_INVALID")
            return value

    async def _send_ready(self) -> None:
        await self._send(
            "ready",
            {
                "supported_protocol_versions": [_PROTOCOL_VERSION],
                "supported_contract_versions": [_CONTRACT_VERSION],
            },
        )

    async def _send(
        self,
        message_type: _MessageType,
        payload: AgentWireModel | dict[str, Any],
        *,
        call_id: str | None = None,
        operation: _Operation | None = None,
    ) -> None:
        async with self._send_lock:
            frame = AgentStdioFrame(
                invocation_id=self.request.identity.invocation_id,
                sequence=self._outbound_sequence,
                direction="child_to_parent",
                message_type=message_type,
                call_id=call_id,
                operation=operation,
                payload=FrozenJson.freeze(payload.to_wire() if isinstance(payload, AgentWireModel) else payload),
            )
            self._outbound.accept(frame)
            encoded = await asyncio.to_thread(encode_agent_frame, frame)
            self._child_output_bytes += len(encoded) - 4
            if self._child_output_bytes > self._maximum_child_output_bytes:
                raise AgentProtocolError("E_SDK_AGENT_AGGREGATE_OUTPUT_EXCEEDED")
            self._writer.write(encoded)
            await self._writer.drain()
            self._outbound_sequence += 1

    async def _receive_loop(self) -> None:
        try:
            while not self._closed:
                frame = await read_agent_frame(self._reader, timeout_seconds=self._remaining_seconds())
                self._inbound.accept(frame)
                if frame.message_type == "cancel":
                    self.cancellation._apply_host_cancellation(
                        AgentCancellation.from_wire(cast(dict[str, Any], frame.payload.thaw()))
                    )
                    self._fail_pending(AgentInvocationCancelled("E_SDK_AGENT_INVOCATION_CANCELLED"))
                elif frame.message_type == "capability_result":
                    self._accept_capability_result(frame)
                else:
                    raise AgentProtocolError("E_SDK_AGENT_PARENT_FRAME_UNEXPECTED")
        except asyncio.CancelledError:
            raise
        except (ValueError, AgentProtocolError) as exc:
            self._disconnect_error = AgentBrokerDisconnected(f"E_SDK_AGENT_BROKER_DISCONNECTED: {exc}")
            self._fail_pending(self._disconnect_error)

    def _accept_capability_result(self, frame: AgentStdioFrame) -> None:
        if self._pending is None:
            raise AgentProtocolError("E_SDK_AGENT_CAPABILITY_RESULT_UNSOLICITED")
        call_id, operation, future = self._pending
        if frame.call_id != call_id or frame.operation != operation:
            raise AgentProtocolError("E_SDK_AGENT_CAPABILITY_RESULT_MISMATCH")
        payload = cast(dict[str, Any], frame.payload.thaw())
        result: AgentWireModel
        if operation == "model.call.v1":
            result = AgentModelCallResult.from_wire(payload)
        else:
            result = AgentMemoryQueryResult.from_wire(payload)
        if not future.done():
            future.set_result(result)

    def _fail_pending(self, error: Exception) -> None:
        if self._pending is not None and not self._pending[2].done():
            self._pending[2].set_exception(error)

    def _ensure_available(self) -> None:
        if self._disconnect_error is not None:
            raise self._disconnect_error
        if self._closed:
            raise AgentBrokerDisconnected("E_SDK_AGENT_BROKER_CLOSED")
        if self.cancellation.snapshot().requested:
            raise AgentInvocationCancelled("E_SDK_AGENT_INVOCATION_CANCELLED")

    def _require_bound_identity(self, identity: dict[str, Any]) -> None:
        if identity != self.request.identity.model_dump(mode="json"):
            raise AgentProtocolError("E_SDK_AGENT_INVOCATION_IDENTITY_MISMATCH")

    def _remaining_seconds(self) -> float:
        deadline = datetime.fromisoformat(self.request.deadline_utc.replace("Z", "+00:00"))
        return max(0.001, (deadline - datetime.now(UTC)).total_seconds())


class _SessionModelCapability(AgentModelCapability):
    def __init__(self, session: AgentBrokerSession) -> None:
        self._session = session

    async def call(self, request: AgentModelCallRequest) -> AgentModelCallResult:
        return await self._session.model_call(request)


class _SessionMemoryCapability(AgentMemoryCapability):
    def __init__(self, session: AgentBrokerSession) -> None:
        self._session = session

    async def query(self, request: AgentMemoryQueryRequest) -> AgentMemoryQueryResult:
        return await self._session.memory_query(request)


async def run_agent_workload(
    workload: AsyncAgentWorkload,
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    *,
    bootstrap_timeout_seconds: float,
) -> AgentIterationResult:
    """Run one child iteration over the canonical broker session."""
    async with await AgentBrokerSession.connect(
        reader,
        writer,
        bootstrap_timeout_seconds=bootstrap_timeout_seconds,
    ) as session:
        result = await workload.run(session.workload_context())
        await session.publish_result(result)
        return result
