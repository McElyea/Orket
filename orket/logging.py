"""Public log routing and metrics over the single native publication owner."""
import contextlib
import json
import os
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


MISSING_WORKSPACE_MODE_ENV = "ORKET_LOGGING_MISSING_CONTEXT_MODE"


MISSING_WORKSPACE_MODE_LEGACY = "legacy_default"


MISSING_WORKSPACE_MODE_FAIL_FAST = "fail_fast"


MISSING_WORKSPACE_ERROR_CODE = "E_LOG_WORKSPACE_REQUIRED"


def _resolve_missing_workspace_mode() -> str:
    raw = str(os.getenv(MISSING_WORKSPACE_MODE_ENV, "")).strip().lower()
    if raw == MISSING_WORKSPACE_MODE_FAIL_FAST:
        return MISSING_WORKSPACE_MODE_FAIL_FAST
    return MISSING_WORKSPACE_MODE_LEGACY


def _resolve_workspace(workspace: Path | None) -> tuple[Path, dict[str, Any]]:
    if workspace is not None:
        return workspace, {}
    mode = _resolve_missing_workspace_mode()
    if mode == MISSING_WORKSPACE_MODE_FAIL_FAST:
        raise RuntimeError(
            f"{MISSING_WORKSPACE_ERROR_CODE}: log_event requires workspace when "
            f"{MISSING_WORKSPACE_MODE_ENV}={MISSING_WORKSPACE_MODE_FAIL_FAST}"
        )
    return (
        Path("workspace/default"),
        {
            "logging_context_mode": MISSING_WORKSPACE_MODE_LEGACY,
            "logging_context_marker": "workspace_default_fallback",
        },
    )


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
    workspace, context_marker = _resolve_workspace(workspace)
    level_name = publication._resolve_level_name(kwargs.pop("level", None))

    # Merge extra kwargs into data for observability
    full_data = {**data, **kwargs}
    if context_marker:
        full_data.update(context_marker)
    role_name = role or full_data.get("role") or "system"
    runtime_event = _build_runtime_event(event, full_data, role_name)
    full_data = {**full_data, "runtime_event": runtime_event}

    record = {
        "timestamp": now_local().isoformat(),
        "level": level_name,
        "role": role_name,
        "event": event,
        "data": full_data,
    }

    _publish_record(workspace, record, runtime_event)


def _publish_record(workspace: Path, record: dict[str, Any], runtime_event: dict[str, Any]) -> None:
    deliveries = publication.capture_event_deliveries()
    try:
        publication._emit_stdlib_record(record["level"], record["event"], record)
        log_file = setup_logging(workspace)
        publication._append_json_record(log_file, record)
        with contextlib.suppress(RuntimeError, ValueError, TypeError, OSError):
            _append_runtime_event_artifact(workspace, runtime_event)
        _notify_subscribers(log_file, record, deliveries)
    finally:
        for delivery in deliveries:
            delivery.release_untransferred()


def _notify_subscribers(log_file: Path, record: dict[str, Any], deliveries: list[publication.EventDelivery]) -> None:
    for delivery in deliveries:
        try:
            delivery.invoke(record)
        except (RuntimeError, ValueError, TypeError, OSError) as e:
            failure_record = {
                "timestamp": now_local().isoformat(),
                "level": "error",
                "role": "system",
                "event": "logging_subscriber_failed",
                "data": {"error": str(e)},
            }
            publication._emit_stdlib_record("error", "logging_subscriber_failed", failure_record)
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
