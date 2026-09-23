"""Contract tests for captured memory-trace inputs, sinks and rendering."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.application.workflows.turn_artifact_destination import TurnArtifactDestination
from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
from orket.application.workflows.turn_memory_trace_artifacts import (
    MemoryTraceInputs,
    admit_memory_trace_event_sink,
    append_memory_event,
    capture_memory_trace_inputs,
    render_memory_trace_publication,
)
from orket.core.domain.execution import ExecutionTurn, ToolCall

pytestmark = pytest.mark.contract


def _destination(tmp_path: Path, *, role_id: str | None = "DEV") -> TurnArtifactDestination:
    writer = TurnArtifactWriter(tmp_path)
    return TurnArtifactDestination(
        writer=writer,
        workspace=tmp_path.resolve(),
        session_id="session-a",
        issue_id="ISSUE-A",
        role_name="developer",
        role_id=role_id,
        turn_index=2,
    )


def _inputs(*, enabled: bool = True) -> MemoryTraceInputs:
    return MemoryTraceInputs(
        enabled=enabled,
        normalization_version="json-v1",
        tool_profile_version="profile-v1",
        event_normalization_version="json-v1",
        event_tool_profile_version="profile-v1",
        workflow_id="turn_executor",
        memory_snapshot_id="snapshot-a",
        visibility_mode="read_only",
        model_config_id="model-a",
        policy_set_id="policy-a",
        output_type="",
    )


def test_memory_trace_inputs_preserve_event_version_quirks() -> None:
    inputs = capture_memory_trace_inputs({
        "visibility_mode": " read_only ",
        "normalization_version": " json-custom ",
        "tool_profile_version": " profile-custom ",
        "workflow_id": " workflow-a ",
        "memory_snapshot_id": " snapshot-a ",
        "selected_model": " model-a ",
        "policy_set_id": " policy-a ",
        "output_type": " structured ",
    })

    assert inputs.enabled is True
    assert inputs.normalization_version == "json-custom"
    assert inputs.tool_profile_version == "profile-custom"
    assert inputs.event_normalization_version == " json-custom "
    assert inputs.event_tool_profile_version == " profile-custom "
    assert inputs.workflow_id == "workflow-a"
    assert inputs.memory_snapshot_id == "snapshot-a"
    assert inputs.model_config_id == "model-a"
    assert inputs.policy_set_id == "policy-a"
    assert inputs.output_type == "structured"


@pytest.mark.parametrize("visibility", [None, False, 0])
def test_memory_trace_inputs_preserve_explicit_visibility_enablement(visibility: object) -> None:
    inputs = capture_memory_trace_inputs({"visibility_mode": visibility})

    assert inputs.enabled is True
    assert inputs.visibility_mode == "off"


def test_memory_trace_inputs_preserve_missing_and_blank_visibility_disablement() -> None:
    assert capture_memory_trace_inputs({}).enabled is False
    assert capture_memory_trace_inputs({"visibility_mode": "   "}).enabled is False


def test_disabled_memory_inputs_do_not_consume_unused_config() -> None:
    class Unused:
        def __bool__(self):
            raise AssertionError("disabled config consumed")

        def __str__(self):
            raise AssertionError("disabled config rendered")

    context = dict.fromkeys((
        "normalization_version", "tool_profile_version", "workflow_id", "memory_snapshot_id",
        "model_config_id", "selected_model", "policy_set_id", "output_type",
    ), Unused())
    inputs = capture_memory_trace_inputs(context)

    assert inputs == capture_memory_trace_inputs({})
    assert inputs.enabled is False


def test_enabled_memory_inputs_consume_visibility_after_admission() -> None:
    observed = []

    class Context(dict):
        def get(self, key, default=None):
            observed.append(key)
            return super().get(key, default)

    class InvalidVisibility:
        def __str__(self):
            raise ValueError("enabled visibility rendered")

    context = Context(memory_trace_enabled=True, visibility_mode=InvalidVisibility())
    with pytest.raises(ValueError, match="enabled visibility rendered"):
        capture_memory_trace_inputs(context)

    assert observed[0] == "memory_trace_enabled"
    assert observed.count("visibility_mode") == 1
    assert observed.index("normalization_version") < observed.index("visibility_mode")


def test_memory_event_sink_is_original_and_detaches_named_nested_values() -> None:
    context: dict[str, object] = {}
    sink = admit_memory_trace_event_sink(context=context, inputs=_inputs())
    assert sink is not None
    assert context["_memory_trace_events"] is sink
    resource = object()
    source = [{"tool_name": "read", "args": {"path": "original"}, "resource": resource}]

    append_memory_event(
        sink,
        role_name="developer",
        interceptor=" before_tool ",
        decision_type=" ready ",
        tool_calls=source,
        guardrails_triggered=["guard-a"],
        retrieval_event_ids=["ret-a"],
    )
    source[0]["args"]["path"] = "changed"

    assert sink[0]["interceptor"] == "before_tool"
    assert sink[0]["decision_type"] == "ready"
    assert sink[0]["tool_calls"][0]["args"] == {"path": "original"}
    assert sink[0]["tool_calls"][0]["resource"] is resource


def test_disabled_memory_trace_does_not_publish_or_replace_sink(tmp_path: Path) -> None:
    original = [{"event": "borrowed"}]
    context = {"_memory_trace_events": original}
    sink = admit_memory_trace_event_sink(context=context, inputs=_inputs(enabled=False))

    assert sink is None
    assert context["_memory_trace_events"] is original
    assert render_memory_trace_publication(
        destination=_destination(tmp_path),
        inputs=_inputs(enabled=False),
        event_sink=None,
        turn=None,
        guardrails_triggered=[],
        retrieval_events=[],
    ) is None


def test_memory_trace_render_freezes_terminal_values_and_format(tmp_path: Path) -> None:
    destination = _destination(tmp_path)
    sink: list[dict] = []
    event_calls = [{"tool_name": "read", "normalized_args": {"path": "event-original"}}]
    append_memory_event(
        sink,
        role_name="developer",
        interceptor="after_tool",
        decision_type="tool_call_result",
        tool_calls=event_calls,
    )
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-A",
        tool_calls=[ToolCall(tool="read", args={"path": "turn-original"}, result={"ok": True})],
        timestamp=None,
    )
    retrieval = [{"retrieval_event_id": "ret-a", "selected_records": [{"id": "original"}]}]
    publication = render_memory_trace_publication(
        destination=destination,
        inputs=_inputs(),
        event_sink=sink,
        turn=turn,
        guardrails_triggered=["guard-a"],
        retrieval_events=retrieval,
    )
    assert publication is not None
    event_calls[0]["normalized_args"]["path"] = "changed"
    sink[0]["tool_calls"][0]["normalized_args"]["path"] = "changed"
    turn.tool_calls[0].args["path"] = "changed"
    retrieval[0]["selected_records"][0]["id"] = "changed"

    trace = json.loads(publication.memory_trace)
    retrieval_trace = json.loads(publication.retrieval_trace)
    assert trace["run_id"] == "session-a"
    assert trace["issue_id"] == "ISSUE-A"
    assert trace["role_id"] == "DEV"
    assert trace["events"][0]["tool_calls"][0]["normalized_args"] == {"path": "event-original"}
    assert trace["output"]["output_type"] == "text"
    assert retrieval_trace["events"][0]["selected_records"] == [{"id": "original"}]
    assert publication.memory_trace.startswith("{\n  \"run_id\":")


def test_memory_trace_fallback_and_role_id_refusal(tmp_path: Path) -> None:
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-A",
        tool_calls=[ToolCall(tool="write", args={"path": "a"}, result={"ok": False})],
        timestamp=None,
    )
    publication = render_memory_trace_publication(
        destination=_destination(tmp_path),
        inputs=_inputs(),
        event_sink=[],
        turn=turn,
        guardrails_triggered=["guard-a"],
        retrieval_events=[{"retrieval_event_id": "ret-a"}],
        failure_reason="failed",
        failure_type="tool_error",
    )
    assert publication is not None
    trace = json.loads(publication.memory_trace)
    assert trace["events"][0]["interceptor"] == "on_turn_failure"
    assert trace["events"][0]["decision_type"] == "tool_error"
    assert trace["events"][0]["retrieval_event_ids"] == ["ret-a"]
    assert trace["output"]["output_type"] == "error"
    assert trace["output"]["output_shape_hash"]

    with pytest.raises(ValueError, match="E_TURN_MEMORY_ROLE_ID_REQUIRED"):
        render_memory_trace_publication(
            destination=_destination(tmp_path, role_id=None),
            inputs=_inputs(),
            event_sink=[],
            turn=None,
            guardrails_triggered=[],
            retrieval_events=[],
        )
