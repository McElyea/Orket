from __future__ import annotations

import asyncio
import struct

import pytest

from orket_extension_sdk.agent_broker import AgentBrokerSession
from orket_extension_sdk.agent_fixtures import (
    agent_broker_frame,
    agent_cancellation,
    agent_identity,
    agent_iteration_request,
    agent_model_call_request,
    agent_model_call_result,
)
from orket_extension_sdk.agent_ipc import (
    AgentFrameSequenceValidator,
    decode_agent_frame,
    encode_agent_frame,
    read_agent_frame,
)
from orket_extension_sdk.agent_models import AgentModelCallRequest, AgentStdioFrame
from orket_extension_sdk.agent_runtime import AgentCancellationView, AgentProgressReporter
from orket_extension_sdk.agent_types import AgentCancellation, AgentIdentity
from orket_extension_sdk.errors import AgentInvocationCancelled

pytestmark = pytest.mark.contract


class _MemoryWriter:
    def __init__(self) -> None:
        self.data = bytearray()

    def write(self, value: bytes) -> None:
        self.data.extend(value)

    async def drain(self) -> None:
        return None


def _parent_frame(
    *,
    sequence: int,
    message_type: str,
    payload: dict[str, object],
    call_id: str | None = None,
    operation: str | None = None,
) -> AgentStdioFrame:
    return AgentStdioFrame.model_validate(
        {
            "invocation_id": "invocation-1",
            "sequence": sequence,
            "direction": "parent_to_child",
            "message_type": message_type,
            "call_id": call_id,
            "operation": operation,
            "payload": payload,
        }
    )


async def _connected_session() -> tuple[AgentBrokerSession, asyncio.StreamReader, _MemoryWriter]:
    request = agent_iteration_request()
    request["deadline_utc"] = "2099-01-01T00:00:00Z"
    request["lease_expires_at_utc"] = "2098-12-31T23:59:00Z"
    bootstrap = _parent_frame(sequence=1, message_type="bootstrap", payload=request)
    reader = asyncio.StreamReader()
    reader.feed_data(encode_agent_frame(bootstrap))
    writer = _MemoryWriter()
    session = await AgentBrokerSession.connect(  # type: ignore[arg-type]
        reader,
        writer,
        bootstrap_timeout_seconds=1,
    )
    return session, reader, writer


def _ready(sequence: int = 1) -> AgentStdioFrame:
    return AgentStdioFrame.from_wire(
        {
            "object_type": "agent_stdio_frame",
            "schema_version": "agent_stdio_frame.v1",
            "protocol_version": "agent_stdio_ipc.v1",
            "invocation_id": "invocation-1",
            "sequence": sequence,
            "direction": "child_to_parent",
            "message_type": "ready",
            "call_id": None,
            "operation": None,
            "payload": {
                "supported_protocol_versions": ["agent_stdio_ipc.v1"],
                "supported_contract_versions": ["governed_agent_loop.v1"],
            },
        }
    )


def test_frame_codec_round_trips_canonical_payload() -> None:
    frame = AgentStdioFrame.from_wire(agent_broker_frame())

    decoded = decode_agent_frame(encode_agent_frame(frame))

    assert decoded.to_wire() == frame.to_wire()


def test_frame_codec_refuses_oversized_length_before_payload() -> None:
    with pytest.raises(ValueError, match="E_SDK_AGENT_FRAME_TOO_LARGE"):
        decode_agent_frame(struct.pack(">I", 1_048_577))


@pytest.mark.asyncio
async def test_async_frame_reader_reports_partial_payload() -> None:
    reader = asyncio.StreamReader()
    reader.feed_data(struct.pack(">I", 10) + b"{}")
    reader.feed_eof()

    with pytest.raises(ValueError, match="E_SDK_AGENT_FRAME_INCOMPLETE"):
        await read_agent_frame(reader, timeout_seconds=1)


def test_sequence_validator_requires_ready_and_monotonic_sequence() -> None:
    validator = AgentFrameSequenceValidator(
        invocation_id="invocation-1",
        direction="child_to_parent",
    )
    validator.accept(_ready())

    with pytest.raises(ValueError, match="E_SDK_AGENT_FRAME_SEQUENCE_INVALID"):
        validator.accept(_ready(sequence=3))


@pytest.mark.asyncio
async def test_progress_reporter_is_bounded_and_sequential() -> None:
    published = []

    async def publish(progress: object) -> None:
        published.append(progress)

    reporter = AgentProgressReporter(
        identity=AgentIdentity.model_validate(agent_identity()),
        maximum_events=1,
        publish=publish,
    )
    first = await reporter.report(summary="working")

    assert first.sequence == 1
    assert published == [first]
    with pytest.raises(ValueError, match="E_SDK_AGENT_PROGRESS_LIMIT_EXCEEDED"):
        await reporter.report(summary="too many")


@pytest.mark.asyncio
async def test_cancellation_view_rejects_stale_host_epoch() -> None:
    view = AgentCancellationView(
        AgentCancellation(requested=False, cancellation_epoch=1, reason=None)
    )

    with pytest.raises(ValueError, match="E_SDK_AGENT_CANCELLATION_EPOCH_STALE"):
        view._apply_host_cancellation(
            AgentCancellation(requested=True, cancellation_epoch=1, reason="operator")
        )


@pytest.mark.asyncio
async def test_child_broker_correlates_one_model_call_and_host_result() -> None:
    session, reader, writer = await _connected_session()
    request = AgentModelCallRequest.from_wire(agent_model_call_request())
    call = asyncio.create_task(session.model_call(request))
    await asyncio.sleep(0)
    response = _parent_frame(
        sequence=2,
        message_type="capability_result",
        call_id="call-1",
        operation="model.call.v1",
        payload=agent_model_call_result(),
    )
    reader.feed_data(encode_agent_frame(response))

    result = await call

    assert result.call_id == "call-1"
    assert len(writer.data) > 0
    await session.close()


@pytest.mark.asyncio
async def test_child_broker_observes_host_cancellation_and_denies_new_calls() -> None:
    session, reader, _writer = await _connected_session()
    cancellation = agent_cancellation(requested=True)
    cancellation["cancellation_epoch"] = 2
    reader.feed_data(
        encode_agent_frame(
            _parent_frame(sequence=2, message_type="cancel", payload=cancellation)
        )
    )

    observed = await asyncio.wait_for(session.cancellation.wait(), timeout=1)

    assert observed.requested is True
    with pytest.raises(AgentInvocationCancelled, match="E_SDK_AGENT_INVOCATION_CANCELLED"):
        await session.model_call(AgentModelCallRequest.from_wire(agent_model_call_request()))
    await session.close()
