from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from orket.core.domain.outward_runs import OutwardRunRecord

EXPLICIT_TOOL_CALL_KEY = "governed_tool_call"
EXPLICIT_TOOL_SEQUENCE_KEY = "governed_tool_sequence"
MODEL_TOOL_CALL_KEY = "model_governed_tool_call"
EXECUTION_STATE_KEY = "_outward_execution_state"


class OutwardRunExecutionPlanError(ValueError):
    pass


def acceptance_tool_steps(run: OutwardRunRecord) -> list[dict[str, Any]]:
    acceptance_contract = run.task.get("acceptance_contract")
    if not isinstance(acceptance_contract, Mapping):
        return []
    raw_sequence = acceptance_contract.get(EXPLICIT_TOOL_SEQUENCE_KEY)
    if raw_sequence is not None:
        if not isinstance(raw_sequence, list) or not raw_sequence:
            raise OutwardRunExecutionPlanError("task.acceptance_contract.governed_tool_sequence must be a non-empty array")
        return [_normalized_tool_step(item, f"task.acceptance_contract.governed_tool_sequence[{index}]") for index, item in enumerate(raw_sequence)]
    raw_call = acceptance_contract.get(EXPLICIT_TOOL_CALL_KEY)
    if raw_call is None:
        return []
    return [_normalized_tool_step(raw_call, "task.acceptance_contract.governed_tool_call")]


def current_step_index(run: OutwardRunRecord) -> int:
    raw_state = run.task.get(EXECUTION_STATE_KEY)
    if not isinstance(raw_state, Mapping):
        return 0
    value = raw_state.get("step_index")
    return int(value) if isinstance(value, int) and value >= 0 else 0


def current_step(run: OutwardRunRecord, steps: list[dict[str, Any]]) -> dict[str, Any] | None:
    index = current_step_index(run)
    if index < 0 or index >= len(steps):
        return None
    return steps[index]


def is_last_step(run: OutwardRunRecord, steps: list[dict[str, Any]]) -> bool:
    return current_step_index(run) >= len(steps) - 1


def model_tool_call(run: OutwardRunRecord) -> dict[str, Any] | None:
    state = _state(run)
    raw_calls = state.get("model_tool_calls")
    raw = raw_calls[-1] if isinstance(raw_calls, list) and raw_calls else run.task.get(MODEL_TOOL_CALL_KEY)
    return _normalized_model_call(raw)


def task_with_model_tool_call(
    run: OutwardRunRecord,
    *,
    tool_call: dict[str, Any],
    model_invocation_ref: str,
    proposal_id: str | None = None,
) -> dict[str, Any]:
    task = dict(run.task)
    state = _state(run)
    calls = list(state.get("model_tool_calls") or [])
    entry = {
        "turn": int(run.current_turn or 1),
        "step_index": current_step_index(run),
        "tool": tool_call["tool"],
        "args": dict(tool_call["args"]),
        "source": "model_output",
        "model_invocation_ref": model_invocation_ref,
    }
    if proposal_id:
        entry["proposal_id"] = proposal_id
    calls.append(entry)
    state["model_tool_calls"] = calls
    task[MODEL_TOOL_CALL_KEY] = {
        "tool": tool_call["tool"],
        "args": dict(tool_call["args"]),
        "source": "model_output",
        "model_invocation_ref": model_invocation_ref,
    }
    task[EXECUTION_STATE_KEY] = state
    return task


def task_with_tool_result(run: OutwardRunRecord, *, proposal_id: str, tool: str, result: dict[str, Any]) -> dict[str, Any]:
    task = dict(run.task)
    state = _state(run)
    results = list(state.get("tool_results") or [])
    results.append(
        {
            "turn": int(run.current_turn or 1),
            "step_index": current_step_index(run),
            "proposal_id": proposal_id,
            "tool": tool,
            "result": dict(result),
        }
    )
    state["tool_results"] = results
    state["step_index"] = current_step_index(run) + 1
    task[EXECUTION_STATE_KEY] = state
    return task


def previous_tool_results(run: OutwardRunRecord) -> list[dict[str, Any]]:
    raw_results = _state(run).get("tool_results")
    return [dict(item) for item in raw_results if isinstance(item, Mapping)] if isinstance(raw_results, list) else []


def step_event_id(run_id: str, turn: int, order: int, name: str) -> str:
    return f"run:{run_id}:{turn:02d}:{order:04d}:{name}"


def args_hash(args: dict[str, Any]) -> str:
    payload = json.dumps(args, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def proposal_suffix(proposal_id: str) -> str:
    return str(proposal_id or "").rsplit(":", maxsplit=1)[-1] or "0000"


def invalid_args_event_payload(tool: str, args: dict[str, Any], errors: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "connector_name": tool,
        "args_hash": args_hash(args),
        "result_summary": {"ok": False, "error": "invalid_args", "errors": errors},
        "duration_ms": 0,
        "outcome": "failed",
    }


def failed_tool_event_payload(tool: str, args: dict[str, Any], error: str) -> dict[str, Any]:
    return {
        "connector_name": tool,
        "args_hash": args_hash(args),
        "result_summary": {"ok": False, "error": error},
        "duration_ms": 0,
        "outcome": "failed",
    }


def failure_reason(tool_event_payload: dict[str, Any]) -> str:
    summary = tool_event_payload.get("result_summary")
    if isinstance(summary, dict) and str(summary.get("error") or "").strip():
        return str(summary["error"])
    return f"connector invocation {tool_event_payload.get('outcome') or 'failed'}"


def _normalized_tool_step(raw: Any, field: str) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise OutwardRunExecutionPlanError(f"{field} must be an object")
    tool = str(raw.get("tool") or "").strip()
    args = raw.get("args")
    if not tool:
        raise OutwardRunExecutionPlanError(f"{field}.tool is required")
    if not isinstance(args, Mapping):
        raise OutwardRunExecutionPlanError(f"{field}.args must be an object")
    return {"tool": tool, "args": dict(args)}


def _normalized_model_call(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None
    tool = str(raw.get("tool") or "").strip()
    args = raw.get("args")
    if not tool or not isinstance(args, Mapping):
        return None
    return {"tool": tool, "args": dict(args)}


def _state(run: OutwardRunRecord) -> dict[str, Any]:
    raw = run.task.get(EXECUTION_STATE_KEY)
    return dict(raw) if isinstance(raw, Mapping) else {"step_index": 0}


__all__ = [
    "EXPLICIT_TOOL_CALL_KEY",
    "EXPLICIT_TOOL_SEQUENCE_KEY",
    "MODEL_TOOL_CALL_KEY",
    "OutwardRunExecutionPlanError",
    "acceptance_tool_steps",
    "args_hash",
    "current_step",
    "current_step_index",
    "failed_tool_event_payload",
    "failure_reason",
    "invalid_args_event_payload",
    "is_last_step",
    "model_tool_call",
    "previous_tool_results",
    "proposal_suffix",
    "step_event_id",
    "task_with_model_tool_call",
    "task_with_tool_result",
]
