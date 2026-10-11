"""Native CLI-only snapshot collection from immutable, committed Git objects."""
from __future__ import annotations

import asyncio
import os
import re
import time
from pathlib import Path, PurePosixPath

from gardener_scope import byte_limits, coverage_listing, target_scopes, wanted_entry

from orket.application.services.command_process_supervisor import CommandProcessSupervisor

MAX_FILES = 10_000


class HarnessFailure(ValueError):
    def __init__(self, reason: str, *, blocked: bool = False, run_id: str | None = None):
        super().__init__(reason)
        self.blocked = blocked
        self.run_id = run_id


class Commands:
    """Use Orket's process-tree owner; never accept partial capture or cleanup."""

    def __init__(self, area: Path, environment: dict[str, str], deadline: float):
        self.area, self.environment, self.deadline = area, dict(environment), deadline
        self.owner = CommandProcessSupervisor(area, cancellation_event="gardener_command_cancelled")
        self.receipts: list[dict] = []
        self._normalization: dict[Path, list[str]] = {}

    def run(self, argv: list[str], cwd: Path, *, git: bool = False, environment: dict[str, str] | None = None):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise HarnessFailure("harness time budget exhausted", blocked=True)
        environment = dict(self.environment if environment is None else environment)
        if git:
            environment = {key: value for key, value in environment.items() if not key.upper().startswith("GIT_")}
            if cwd not in self._normalization:
                observed = self.run(["git", "config", "--get-regexp", r"^core\.(autocrlf|eol)$"], cwd,
                                    environment=environment)
                if observed.returncode not in {0, 1}:
                    raise HarnessFailure("Git text-normalization configuration could not be observed")
                options = []
                for line in observed.stdout.decode("ascii").splitlines():
                    key, value = line.split(maxsplit=1)
                    if key not in {"core.autocrlf", "core.eol"} or value not in {"true", "false", "input", "lf", "crlf", "native"}:
                        raise HarnessFailure("unsupported Git text-normalization setting")
                    options.extend(["-c", f"{key}={value}"])
                self._normalization[cwd] = options
            environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_OPTIONAL_LOCKS="0",
                               GIT_TERMINAL_PROMPT="0", GIT_NO_REPLACE_OBJECTS="1", GIT_NO_LAZY_FETCH="1")
            argv = ["git", "-c", "core.fsmonitor=false", *self._normalization[cwd], *argv]
        result = asyncio.run(self.owner.run(argv, cwd=cwd, environment=environment,
            timeout_seconds=min(30, remaining) if git else remaining, output_limit_bytes=2 * 1024 * 1024))
        self.receipts.append(result.lifetime())
        if result.reason != "completed" or not result.cleanup_confirmed or not result.capture_complete:
            raise HarnessFailure(f"command lifetime refused: {result.reason}; inspect {self.area}", blocked=True)
        if git and result.returncode != 0:
            raise HarnessFailure("Git snapshot discovery failed; no repository evidence admitted", blocked=True)
        return result


def git_bytes(commands: Commands, root: Path, *argv: str) -> bytes:
    return commands.run(list(argv), root, git=True).stdout


def observe_tree(commands: Commands, selected: Path) -> dict:
    selected = selected.resolve(strict=True)
    top = Path(git_bytes(commands, selected, "rev-parse", "--show-toplevel").decode("utf-8").strip()).resolve()
    if not selected.is_relative_to(top):
        raise HarnessFailure("selected source directory is outside its Git root")
    status = git_bytes(commands, top, "status", "--porcelain=v1", "-z", "--untracked-files=normal")
    if status:
        raise HarnessFailure(f"snapshot requires a clean committed source repository: {top}; "
                             f"Git status: {status[:1024].decode('utf-8', errors='replace')!r}")
    commit = git_bytes(commands, top, "rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip()
    if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit) is None:
        raise HarnessFailure("Git commit identity is invalid")
    prefix = PurePosixPath(selected.relative_to(top).as_posix())
    entries = []
    for raw in git_bytes(commands, top, "ls-tree", "-rlz", "--full-tree", commit).split(b"\0"):
        if not raw:
            continue
        header, path_bytes = raw.split(b"\t", 1)
        mode, kind, oid, size = header.decode("ascii").split()
        path = PurePosixPath(path_bytes.decode("utf-8"))
        if path.is_absolute() or ".." in path.parts or "\\" in str(path):
            raise HarnessFailure("Git inventory contains an ambiguous path")
        if path.is_relative_to(prefix):
            if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", oid) is None:
                raise HarnessFailure("Git blob identity is invalid")
            entries.append({"path": str(path), "mode": mode, "kind": kind, "oid": oid,
                            "size": int(size) if size != "-" else None})
    if len(entries) > MAX_FILES:
        raise HarnessFailure(f"source inventory exceeds {MAX_FILES} files; select a smaller committed directory")
    return {"root": top, "selected": selected, "commit": commit, "entries": entries}


def collect_sources(commands: Commands, prompt: str, repo: Path, extra_roots: list[Path]) -> tuple[dict, list[dict]]:
    scopes = target_scopes(commands.environment)
    max_file_bytes, max_snapshot_bytes = byte_limits(commands.environment)
    trees = [observe_tree(commands, root) for root in dict.fromkeys([repo, *extra_roots])]
    if any(commands.area.is_relative_to(tree["root"]) for tree in trees):
        raise HarnessFailure("the retained run area must be outside every source repository")
    normalized_prompt = prompt.replace("\\", "/")
    sources, used = {}, 0
    prefix = PurePosixPath(trees[0]["selected"].relative_to(trees[0]["root"]).as_posix())
    for scope in scopes:
        if not any(PurePosixPath(entry["path"]).relative_to(prefix).is_relative_to(scope)
                   for entry in trees[0]["entries"]):
            raise HarnessFailure(f"selected target scope has no committed entries: {scope}")
    for index, tree in enumerate(trees):
        for entry in tree["entries"]:
            if not wanted_entry(entry, tree, index, normalized_prompt, scopes):
                continue
            if entry["mode"] not in {"100644", "100755"} or entry["kind"] != "blob":
                raise HarnessFailure("selected snapshot input is a symlink, submodule, or non-regular Git entry")
            if entry["size"] > max_file_bytes or used + entry["size"] > max_snapshot_bytes:
                raise HarnessFailure("selected snapshot content exceeds the byte budget; reduce the source scope")
            data = git_bytes(commands, tree["root"], "cat-file", "blob", entry["oid"])
            if len(data) != entry["size"] or b"\0" in data:
                raise HarnessFailure("selected Git blob is invalid or not text")
            text = data.decode("utf-8")
            sources[f"src{len(sources) + 1:02d}"] = {
                "repository": index, "commit": tree["commit"], "path": entry["path"], "text": text,
            }
            used += len(data)
    if not sources or len(sources) > 128:
        raise HarnessFailure("snapshot requires between 1 and 128 committed text documents")
    sources["listing"] = coverage_listing(trees, sources)
    return sources, trees


def verify_unchanged(commands: Commands, trees: list[dict]) -> None:
    for tree in trees:
        current = observe_tree(commands, tree["selected"])
        if current["commit"] != tree["commit"] or current["entries"] != tree["entries"]:
            raise HarnessFailure("source repository changed during the report; retained output is not accepted")
