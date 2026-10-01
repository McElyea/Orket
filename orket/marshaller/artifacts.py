from __future__ import annotations

import json
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.async_file_tools import capture_file_roots

from .canonical import canonical_json


class MarshallerArtifacts:
    """Async-safe writer for Marshaller v0 artifact layout."""

    def __init__(self, workspace_root: Path, run_id: str) -> None:
        workspace_root, = capture_file_roots([workspace_root])
        self.run_root = workspace_root / "workspace" / "default" / "stabilizer" / "run" / run_id

    async def ensure_layout(self) -> None:
        path, = capture_file_roots([self.run_root / "attempts"])
        await run_owned_thread(partial(path.mkdir, parents=True, exist_ok=True), label="marshaller-layout")

    def attempt_dir(self, attempt_index: int) -> Path:
        return self.run_root / "attempts" / str(attempt_index)

    async def write_run_json(self, payload: dict[str, Any]) -> None:
        await self._write_json(self.run_root / "run.json", payload)

    async def write_summary(self, payload: dict[str, Any]) -> None:
        await self._write_json(self.run_root / "summary.json", payload)

    async def write_triage(self, payload: dict[str, Any]) -> None:
        await self._write_json(self.run_root / "triage.json", payload)

    async def write_proposal(self, attempt_index: int, payload: dict[str, Any]) -> None:
        await self._write_json(self.attempt_dir(attempt_index) / "proposal.json", payload)

    async def write_patch(self, attempt_index: int, patch_text: str) -> Path:
        path = self.attempt_dir(attempt_index) / "patch.diff"
        normalized = patch_text if patch_text.endswith("\n") else f"{patch_text}\n"
        await write_text_file(path, normalized)
        return path

    async def write_apply_result(self, attempt_index: int, payload: dict[str, Any]) -> None:
        await self._write_json(self.attempt_dir(attempt_index) / "apply_result.json", payload)

    async def write_check(
        self,
        attempt_index: int,
        check_name: str,
        summary_payload: dict[str, Any],
        log_text: str,
    ) -> None:
        checks_dir, = capture_file_roots([self.attempt_dir(attempt_index) / "checks"])
        summary_text = canonical_json(summary_payload) + "\n"
        await write_text_file(checks_dir / f"{check_name}.json", summary_text)
        await write_text_file(checks_dir / f"{check_name}.log", log_text)

    async def write_metrics(self, attempt_index: int, payload: dict[str, Any]) -> None:
        await self._write_json(self.attempt_dir(attempt_index) / "metrics.json", payload)

    async def write_decision(self, attempt_index: int, payload: dict[str, Any]) -> None:
        await self._write_json(self.attempt_dir(attempt_index) / "decision.json", payload)

    async def write_tree_digest(self, attempt_index: int, digest: str) -> None:
        await write_text_file(self.attempt_dir(attempt_index) / "tree_digest.txt", f"{digest}\n")

    async def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        await write_text_file(path, canonical_json(payload) + "\n")

async def read_json_object(path: Path, *, error_location: str = "at") -> dict[str, Any]:
    path, = capture_file_roots([path])
    text = await run_owned_thread(partial(path.read_text, encoding="utf-8"), label="marshaller-json-read")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError(f"Expected object {error_location} {path}")
    return value


async def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    await write_text_file(path, text)


async def write_text_file(path: Path, content: str) -> None:
    path, = capture_file_roots([path])
    await run_owned_thread(partial(path.parent.mkdir, parents=True, exist_ok=True), label="marshaller-parent")
    await run_owned_thread(partial(_write_utf8_text, path, content), label="marshaller-artifact")


def _write_utf8_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")
