"""Async Git transport for retained artifact commits and read-only confirmation."""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from pathlib import Path

from orket.adapters.execution.process_lifecycle import drain_diagnostic_tail, terminate_process_tree

side_effecting = True


class GiteaExportGit:
    side_effecting = True

    def __init__(self, repo_dir: Path, repo_url: str, environment: dict[str, str]):
        self.repo_dir, self.repo_url, self.environment = repo_dir, repo_url, environment

    async def initialize(self) -> None:
        await asyncio.to_thread(self.repo_dir.mkdir, parents=True, exist_ok=True)
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
        target = (self.repo_dir / run_path).resolve()
        if not target.is_relative_to(self.repo_dir.resolve()) or target == self.repo_dir.resolve():
            raise ValueError("E_GITEA_EXPORT_PATH_ESCAPE")
        if await asyncio.to_thread(target.exists):
            await asyncio.to_thread(shutil.rmtree, target)
        await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copytree, payload_dir, target)
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
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        process = await asyncio.create_subprocess_exec(
            "git", "-c", "core.hooksPath=", "-c", "init.templateDir=", "-c", "credential.helper=",
            *arguments, cwd=self.repo_dir, env=self.environment,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, **options)
        drains = [asyncio.create_task(drain_diagnostic_tail(stream)) for stream in (process.stdout, process.stderr)]
        try:
            await asyncio.wait_for(process.wait(), timeout=60)
        finally:
            cleanup = asyncio.create_task(self._finish_process(process, drains))
            cancelled = False
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    cancelled = True
                    continue  # Drain the owned process even if cancellation is repeated.
            results = cleanup.result()
            if cancelled:
                raise asyncio.CancelledError
        if process.returncode not in allowed or any(truncated for _, truncated in results):
            # Git diagnostics may contain authentication details from caller configuration.
            raise RuntimeError("E_GITEA_GIT_COMMAND_FAILED:" + arguments[0] + ":" + str(process.returncode))
        return process.returncode, results[0][0].decode("utf-8", errors="strict").strip()

    @staticmethod
    async def _finish_process(process, drains):
        await terminate_process_tree(process)
        return await asyncio.gather(*drains)
