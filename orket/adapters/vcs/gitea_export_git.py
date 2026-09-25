"""Async Git transport for retained artifact commits and read-only confirmation."""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.execution.process_lifecycle import DIAGNOSTIC_TAIL_BYTES
from orket.core.contracts.owned_command import CommandExecutionUncertain, CommandRunner

side_effecting = True


class GiteaExportGit:
    side_effecting = True

    def __init__(self, repo_dir: Path, repo_url: str, environment: dict[str, str], *, command_runner: CommandRunner):
        self.repo_dir, self.repo_url, self.environment = repo_dir, repo_url, dict(environment)
        self._command_runner = command_runner

    async def initialize(self) -> None:
        await run_owned_thread(lambda: self.repo_dir.mkdir(parents=True, exist_ok=True), label="gitea-export-repo")
        await self.command("init", "--object-format=sha1")
        await self.command("config", "core.longpaths", "true")
        await self.command("config", "remote.origin.url", self.repo_url)

    async def fetch_head(self, branch: str) -> str | None:
        reference = "refs/heads/" + branch
        code, _ = await self.command("ls-remote", "--exit-code", "--heads", "origin", reference, allowed=(0, 2))
        if code == 2:
            return None
        await self.command("fetch", "--no-tags", "origin", reference)
        return (await self.command("rev-parse", "FETCH_HEAD"))[1]

    async def prepare(self, payload_dir: Path, run_path: str, base: str | None) -> tuple[str, str]:
        def copy_payload():
            root = self.repo_dir.resolve()
            target = (root / run_path).resolve()
            if not target.is_relative_to(root) or target == root:
                raise ValueError("E_GITEA_EXPORT_PATH_ESCAPE")
            if target.exists():
                shutil.rmtree(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(payload_dir, target)

        await run_owned_thread(copy_payload, label="gitea-export-copy")
        await self.command("read-tree", base if base else "--empty")
        await self.command("add", "--", run_path)
        root_tree = (await self.command("write-tree"))[1]
        parent = ("-p", base) if base else ()
        commit = (await self.command("commit-tree", root_tree, *parent, "-m", "Orket retained artifact export"))[1]
        tree = (await self.command("rev-parse", commit + ":" + run_path))[1]
        return commit, tree

    async def push(self, commit: str, tree: str, run_path: str, branch: str) -> None:
        if (await self.command("rev-parse", commit + ":" + run_path))[1] != tree:
            raise ValueError("E_GITEA_EXPORT_TREE_CONFLICT")
        await self.command("push", "origin", commit + ":refs/heads/" + branch)

    async def confirms(self, commit: str, tree: str, run_path: str, branch: str) -> bool:
        if await self.fetch_head(branch) is None:
            return False
        code, _ = await self.command("cat-file", "-e", commit + "^{commit}", allowed=(0, 1, 128))
        if code:
            return False
        code, _ = await self.command("merge-base", "--is-ancestor", commit, "FETCH_HEAD", allowed=(0, 1))
        if code:
            return False
        if (await self.command("rev-parse", commit + ":" + run_path))[1] != tree:
            raise ValueError("E_GITEA_EXPORT_TREE_CONFLICT")
        return True

    async def command(self, *arguments: str, allowed: tuple[int, ...] = (0,)) -> tuple[int, str]:
        try:
            # Initialization needs long paths before repository-local configuration exists.
            result = await self._command_runner.run(
                ("git", "-c", "core.longpaths=true", "-c", "core.hooksPath=",
                 "-c", "init.templateDir=", "-c", "credential.helper=", *arguments),
                cwd=self.repo_dir, environment=dict(self.environment), timeout_seconds=60,
                output_limit_bytes=DIAGNOSTIC_TAIL_BYTES)
        except asyncio.CancelledError as exc:
            # Python 3.11 timeouts require the base type; retain the owner's observation.
            raise asyncio.CancelledError("Gitea export command cancelled") from exc
        if not result.cleanup_confirmed:
            raise CommandExecutionUncertain(result)
        if result.reason == "timeout":
            raise TimeoutError("E_GITEA_GIT_COMMAND_TIMEOUT")
        if result.reason != "completed" or not result.capture_complete or result.returncode not in allowed:
            # Git diagnostics may contain authentication details from caller configuration.
            raise RuntimeError("E_GITEA_GIT_COMMAND_FAILED:" + arguments[0] + ":" + str(result.returncode))
        return result.returncode, result.stdout.decode("utf-8", errors="strict").strip()
