"""Public log routing and metrics over the single native publication owner."""
import contextlib
import json
from pathlib import Path
from typing import Any, TypedDict

from orket.adapters.observability import log_publication as publication
from orket.adapters.observability.log_publication import (
    DEFAULT_LOG_QUEUE_MAX as DEFAULT_LOG_QUEUE_MAX,
)
from orket.adapters.observability.log_publication import (
    LOG_QUEUE_MAX_ENV as LOG_QUEUE_MAX_ENV,
)
from orket.adapters.observability.log_publication import (
    LOG_WRITER_TERMINATED_ERROR as LOG_WRITER_TERMINATED_ERROR,
)
from orket.adapters.observability.log_publication import (
    dropped_log_entry_count as dropped_log_entry_count,
)
from orket.adapters.observability.log_publication import (
    event_subscriber_count as event_subscriber_count,
)
from orket.adapters.observability.log_publication import (
    settle_log_write_frontier as settle_log_write_frontier,
)
from orket.adapters.observability.log_publication import (
    setup_logging as setup_logging,
)
from orket.adapters.observability.log_publication import (
    subscribe_to_events as subscribe_to_events,
)
from orket.adapters.observability.log_publication import (
    unsubscribe_from_events as unsubscribe_from_events,
)
from orket.adapters.observability.logging_context import (
    bind_logging as bind_logging,
)
from orket.adapters.observability.logging_context import (
    native_logging_inputs,
    selected_logging,
)
from orket.adapters.observability.logging_context import (
    prepare_logging as prepare_logging,
)
from orket.adapters.observability.logging_context import (
    prepare_logging_native as prepare_logging_native,
)
from orket.core.contracts.log_event_inputs import LOG_EVENT_INPUT_ERROR, capture_log_event_inputs
from orket.core.contracts.logging_inputs import (
    MISSING_WORKSPACE_ERROR_CODE as MISSING_WORKSPACE_ERROR_CODE,
)
from orket.core.contracts.logging_inputs import (
    MISSING_WORKSPACE_MODE_ENV as MISSING_WORKSPACE_MODE_ENV,
)
from orket.core.contracts.logging_inputs import (
    MISSING_WORKSPACE_MODE_FAIL_FAST as MISSING_WORKSPACE_MODE_FAIL_FAST,
)
from orket.core.contracts.logging_inputs import (
    MISSING_WORKSPACE_MODE_LEGACY as MISSING_WORKSPACE_MODE_LEGACY,
)
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.core.runtime_event import RUNTIME_EVENT_ARTIFACT_EVENTS, _build_runtime_event
from orket.core.runtime_event import RUNTIME_EVENT_SCHEMA_VERSION as RUNTIME_EVENT_SCHEMA_VERSION
from orket.naming import sanitize_name
from orket.time_utils import now_local

side_effecting = True


class _MemberMetrics(TypedDict):
    tokens: int
    lines_written: int
    last_action: str
    detail: str


def _log_path(workspace: Path, role: str | None = None) -> Path:
    root_log = Path("workspace/default/orket.log")
    root_log.parent.mkdir(parents=True, exist_ok=True)
    if role:
        agent_dir = workspace / "agents"
        agent_dir.mkdir(parents=True, exist_ok=True)
        # Sanitize name for filename consistency
        safe_name = sanitize_name(role)
        return agent_dir / f"{safe_name}.log"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace / "orket.log"


def _append_runtime_event_artifact(workspace: Path, runtime_event: dict[str, Any]) -> None:
    session_id = str(runtime_event.get("session_id") or "").strip()
    if not session_id:
        return
    event_name = str(runtime_event.get("event") or "").strip()
    if event_name not in RUNTIME_EVENT_ARTIFACT_EVENTS:
        return
    path = workspace / "agent_output" / "observability" / "runtime_events.jsonl"
    publication._append_json_record(path, runtime_event)


def log_event(
    event: str,
    data: dict[str, Any] | None = None,
    workspace: Path | None = None,
    role: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Unified log router.
    Supports:
    - log_event("event_name", data_dict, workspace, role="X")
    - log_event("event_name", data_dict, workspace=workspace)
    - log_event(level, component, event, payload) [Legacy Compat]
    """
    if publication._running_on_event_loop():
        _enqueue_optional_event(event, data, workspace, role, kwargs)
        return
    # 1. Handle legacy signature if 'event' looks like a level and data is component-like
    if (
        event in {"debug", "info", "warn", "warning", "error", "critical"}
        and isinstance(data, str)
        and len(kwargs) == 0
    ):
        # Shift args: event -> level, data -> component, workspace -> event, role -> payload
        level = event
        component = data
        actual_event = workspace if isinstance(workspace, str) else "generic_event"
        actual_data = role if isinstance(role, dict) else {}
        # Recurse with unified signature
        return log_event(actual_event, actual_data, role=component, level=level)
    if data is None:
        data = {}
    prepared = selected_logging(required=False)
    inputs = prepared.inputs if prepared is not None else native_logging_inputs()
    workspace, context_marker = inputs.workspace(Path(workspace) if isinstance(workspace, Path) else workspace)
    level_name = publication._resolve_level_name(kwargs.pop("level", None))

    # Merge extra kwargs into data for observability
    full_data = {**data, **kwargs}
    if context_marker:
        full_data.update(context_marker)
    role_name = role or full_data.get("role") or "system"
    record, runtime_event = _build_log_record(event, full_data, role_name, level_name, inputs.timezone_name)
    _publish_record(workspace, record, runtime_event, timezone_name=inputs.timezone_name)


def _build_log_record(event: str, full_data: dict[str, Any], role_name: Any, level_name: str,
                      timezone_name: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime_event = _build_runtime_event(event, full_data, role_name)
    record = {
        "timestamp": now_local(timezone_name).isoformat(),
        "level": level_name,
        "role": role_name,
        "event": event,
        "data": {**full_data, "runtime_event": runtime_event},
    }
    return record, runtime_event


def _capture_event(event: str, data: Any, workspace: Any, role: Any, options: dict[str, Any],
                   inputs: LoggingInputs) -> tuple:
    if type(event) is not str:
        raise TypeError(LOG_EVENT_INPUT_ERROR)
    if event in publication._LOG_LEVELS and type(data) is str and not options:
        event, data, workspace, role, options = (
            workspace if type(workspace) is str else "generic_event",
            role if type(role) is dict else {}, None, data, {"level": event})
    if role is not None and type(role) is not str:
        raise TypeError(LOG_EVENT_INPUT_ERROR)
    if workspace is not None and type(workspace) is not type(Path()):
        raise TypeError(LOG_EVENT_INPUT_ERROR)
    event, captured = capture_log_event_inputs(event, {
        "data": {} if data is None else data, "options": options})
    if type(captured["data"]) is not dict:
        raise TypeError(LOG_EVENT_INPUT_ERROR)
    workspace, marker = inputs.workspace(workspace)
    level = captured["options"].pop("level", None)
    values = {**captured["data"], **captured["options"]}
    values.update(marker)
    role_name = role or values.get("role") or "system"
    return event, values, workspace, role_name, level, inputs.timezone_name


def _enqueue_optional_event(event: str, data: Any, workspace: Any, role: Any, options: dict[str, Any]) -> None:
    prepared = selected_logging()
    captured = _capture_event(event, data, workspace, role, options, prepared.inputs)
    event, values, workspace, _role, _level, _timezone = captured
    native = _OptionalEvent(*captured)
    operations = [(workspace / "orket.log", native.main)]
    if event.strip() in RUNTIME_EVENT_ARTIFACT_EVENTS and values.get("session_id"):
        operations.append((workspace / "agent_output/observability/runtime_events.jsonl", native.artifact))
    batch = publication.OptionalPublication(operations, native.complete)
    native.batch = batch
    publication.admit_optional_publication(batch)




class _OptionalEvent:
    """Per-event native stages; all process-wide ownership stays in publication."""

    def __init__(self, event: str, data: dict[str, Any], workspace: Path, role: Any,
                 level: Any, timezone_name: str) -> None:
        self.event, self.data, self.workspace = event, data, workspace
        self.role, self.level, self.timezone_name = role, level, timezone_name
        self.record: dict[str, Any] = {}
        self.runtime_event: dict[str, Any] = {}
        self.batch: publication.OptionalPublication

    def materialize(self) -> None:
        if not self.record:
            self.record, self.runtime_event = _build_log_record(
                self.event, self.data, self.role, publication._resolve_level_name(self.level), self.timezone_name)

    def main(self) -> None:
        self.materialize()
        publication._emit_stdlib_record(self.record["level"], self.event, self.record)
        log_file = setup_logging(self.workspace)
        # Optional native append retains the existing best-effort OSError posture.
        with contextlib.suppress(OSError):
            publication._append_json_record(log_file, self.record)

    def artifact(self) -> None:
        self.materialize()
        with contextlib.suppress(OSError):
            _append_runtime_event_artifact(self.workspace, self.runtime_event)

    def complete(self) -> None:
        _notify_subscribers(self.workspace / "orket.log", self.record, self.batch.deliveries,
                            timezone_name=self.timezone_name, optional_append=True)


def _publish_record(workspace: Path, record: dict[str, Any], runtime_event: dict[str, Any], *,
                    timezone_name: str | None = None) -> None:
    deliveries = publication.capture_event_deliveries()
    try:
        publication._emit_stdlib_record(record["level"], record["event"], record)
        log_file = setup_logging(workspace)
        publication._append_json_record(log_file, record)
        with contextlib.suppress(RuntimeError, ValueError, TypeError, OSError):
            _append_runtime_event_artifact(workspace, runtime_event)
        _notify_subscribers(log_file, record, deliveries, timezone_name=timezone_name)
    finally:
        for delivery in deliveries:
            delivery.release_untransferred()


def _notify_subscribers(log_file: Path, record: dict[str, Any], deliveries: list[publication.EventDelivery],
                        *, timezone_name: str | None = None, optional_append: bool = False) -> None:
    for delivery in deliveries:
        try:
            delivery.invoke(record)
        except (RuntimeError, ValueError, TypeError, OSError) as e:
            failure_record = {
                "timestamp": now_local(timezone_name).isoformat(),
                "level": "error",
                "role": "system",
                "event": "logging_subscriber_failed",
                "data": {"error": str(e)},
            }
            publication._emit_stdlib_record("error", "logging_subscriber_failed", failure_record)
            with contextlib.suppress(OSError) if optional_append else contextlib.nullcontext():
                publication._append_json_record(log_file, failure_record)


def log_model_selected(
    role: str,
    model: str,
    temperature: float,
    seed: int | None,
    epic: str,
    workspace: Path,
) -> None:
    log_event(
        "model_selected",
        {
            "role": role,
            "model": model,
            "temperature": temperature,
            "seed": seed,
            "epic": epic,
        },
        workspace=workspace,
    )


def log_model_usage(role: str, model: str, tokens: dict[str, Any], step_index: int, epic: str, workspace: Path) -> None:
    log_event(
        "model_usage",
        {
            "role": role,
            "model": model,
            "epic": epic,
            "step_index": step_index,
            "input_tokens": tokens.get("input_tokens"),
            "output_tokens": tokens.get("output_tokens"),
            "total_tokens": tokens.get("total_tokens"),
        },
        workspace=workspace,
    )


def get_member_metrics(workspace: Path) -> dict[str, _MemberMetrics]:
    """
    Aggregates stats per role from the workspace/orket.log.
    """
    log_path = workspace / "orket.log"
    if not log_path.exists():
        return {}

    metrics: dict[str, _MemberMetrics] = {}
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    continue
                role_value = record.get("role")
                if not isinstance(role_value, str) or not role_value:
                    continue
                role = role_value

                if role not in metrics:
                    metrics[role] = {"tokens": 0, "lines_written": 0, "last_action": "Idle", "detail": ""}

                event = record.get("event")
                data = record.get("data")
                data_dict = data if isinstance(data, dict) else {}

                if event == "model_usage":
                    total_tokens = data_dict.get("total_tokens")
                    if isinstance(total_tokens, int):
                        metrics[role]["tokens"] += total_tokens
                elif event == "tool_call":
                    tool = data_dict.get("tool")
                    metrics[role]["last_action"] = f"Executing {tool}"
                    if tool == "write_file":
                        args_payload = data_dict.get("args")
                        args_dict = args_payload if isinstance(args_payload, dict) else {}
                        content = args_dict.get("content")
                        content_text = content if isinstance(content, str) else ""
                        metrics[role]["lines_written"] += len(content_text.splitlines())
                        metrics[role]["detail"] = f"Wrote {args_dict.get('path')}"
                elif event == "auto_persist":
                    metrics[role]["detail"] = f"Persisted {data_dict.get('path')}"
            except (json.JSONDecodeError, KeyError):
                continue
    return metrics
