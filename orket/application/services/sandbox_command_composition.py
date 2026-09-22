"""Application-selected owner, process inputs and finite sandbox command budget."""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from orket.adapters.storage.async_file_tools import capture_file_roots
from orket.adapters.storage.command_runner import CommandRunner
from orket.application.services.command_process_supervisor import CommandProcessSupervisor

DEFAULT_SANDBOX_COMMAND_TIMEOUT_SECONDS = 300.0


def create_sandbox_command_runner(
    workspace_root: Path, *, cwd: Path | None = None,
    environment: Mapping[str, str] | None = None,
    timeout_seconds: float = DEFAULT_SANDBOX_COMMAND_TIMEOUT_SECONDS,
) -> CommandRunner:
    """Capture full child environment and cwd; omitted cwd binds the current directory."""
    workspace, command_root = capture_file_roots([workspace_root, Path() if cwd is None else cwd])
    return CommandRunner(
        owner=CommandProcessSupervisor(workspace, cancellation_event="sandbox_command_interrupted"),
        cwd=command_root, environment=dict(os.environ if environment is None else environment),
        timeout_seconds=timeout_seconds,
    )
