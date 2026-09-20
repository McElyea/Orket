"""Application ownership of extension Git commands and synchronous worker observations."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path

from orket.application.services.command_process_supervisor import CommandProcessCancelled, CommandProcessSupervisor
from orket.core.contracts.owned_command import OwnedCommandResult


class ExtensionGitError(RuntimeError):
    def __init__(self, code: str, observation: OwnedCommandResult):
        # Remote diagnostics can contain credentials; retain lifetime without echoing argv/output.
        super().__init__(f"{code}: {observation.reason}; exit={observation.returncode}")
        self.observation = observation


async def run_git(arguments: list[str], *, cwd: Path, environment: Mapping[str, str],
                  timeout_seconds: float = 30, code: str = "E_EXT_GIT_FAILED") -> bytes:
    selected = {k: v for k, v in environment.items() if k not in {
        "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE",
    }}
    selected["GIT_TERMINAL_PROMPT"] = "0"
    owner = CommandProcessSupervisor(cwd, cancellation_event="extension_git_command_cancelled")
    try:
        observed = await owner.run(["git", *arguments], cwd=cwd, environment=selected,
                                   timeout_seconds=timeout_seconds)
    except CommandProcessCancelled as exc:
        if not exc.lifetime.cleanup_confirmed or not exc.lifetime.capture_complete:
            raise ExtensionGitError("E_EXT_GIT_INTERRUPTION_UNCERTAIN", exc.lifetime) from exc
        if exc.__cause__ is not None:
            raise ExtensionGitError("E_EXT_GIT_CANCEL_RECORD_FAILED", exc.lifetime) from exc
        # Python 3.12 timeout scopes convert the exact base cancellation type.
        # Preserve native observations in the cause and retained cancellation event.
        raise asyncio.CancelledError from exc
    if (observed.reason != "completed" or observed.returncode != 0
            or not observed.cleanup_confirmed or not observed.capture_complete):
        raise ExtensionGitError(code, observed)
    return observed.stdout


async def resolve_commit(repo_path: Path, ref: str, *, environment: Mapping[str, str]) -> str:
    target = str(ref or "").strip() or "HEAD"
    raw = await run_git([f"--git-dir={repo_path / '.git'}", f"--work-tree={repo_path}",
                         "rev-parse", "--verify", "--end-of-options", f"{target}^{{commit}}"],
                        cwd=repo_path, environment=environment, code="E_EXT_REF_RESOLVE_FAILED")
    result = raw.decode("ascii").strip()
    if len(result) not in {40, 64} or any(c not in "0123456789abcdef" for c in result):
        raise RuntimeError("E_EXT_COMMIT_INVALID")
    return result


def observe_commit_in_worker(repo_path: Path, ref: str, *, environment: Mapping[str, str]) -> str:
    """The synchronous catalog admission worker owns this native supervisor to settlement."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(resolve_commit(repo_path, ref, environment=environment))
    raise RuntimeError("E_EXT_INTEGRITY_REQUIRES_WORKER")
