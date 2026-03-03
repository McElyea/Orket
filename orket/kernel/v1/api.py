from __future__ import annotations

from typing import Any

from .validator import (
    authorize_tool_call_v1,
    compare_runs_v1,
    execute_turn_v1,
    finish_run_v1,
    replay_run_v1,
    resolve_capability_v1,
    start_run_v1,
)
from .nervous_system_runtime import (
    admit_proposal_v1,
    commit_proposal_v1,
    end_session_v1,
    projection_pack_v1,
)
from .experiments.runner import run_experiment_v1


def start_run(request: dict[str, Any]) -> dict[str, Any]:
    return start_run_v1(request)


def execute_turn(request: dict[str, Any]) -> dict[str, Any]:
    return execute_turn_v1(request)


def finish_run(request: dict[str, Any]) -> dict[str, Any]:
    return finish_run_v1(request)


def resolve_capability(request: dict[str, Any]) -> dict[str, Any]:
    return resolve_capability_v1(request)


def authorize_tool_call(request: dict[str, Any]) -> dict[str, Any]:
    return authorize_tool_call_v1(request)


def replay_run(request: dict[str, Any]) -> dict[str, Any]:
    return replay_run_v1(request)


def compare_runs(request: dict[str, Any]) -> dict[str, Any]:
    return compare_runs_v1(request)


def projection_pack(request: dict[str, Any]) -> dict[str, Any]:
    return projection_pack_v1(request)


def admit_proposal(request: dict[str, Any]) -> dict[str, Any]:
    return admit_proposal_v1(request)


def commit_proposal(request: dict[str, Any]) -> dict[str, Any]:
    return commit_proposal_v1(request)


def end_session(request: dict[str, Any]) -> dict[str, Any]:
    return end_session_v1(request)


def run_experiment(request: dict[str, Any]) -> dict[str, Any]:
    return run_experiment_v1(request)


__all__ = [
    "authorize_tool_call",
    "compare_runs",
    "projection_pack",
    "admit_proposal",
    "commit_proposal",
    "end_session",
    "execute_turn",
    "finish_run",
    "replay_run",
    "resolve_capability",
    "run_experiment",
    "start_run",
]
