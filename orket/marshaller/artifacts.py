from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from .canonical import canonical_json


class MarshallerArtifacts:
    """Async-safe writer for Marshaller v0 artifact layout."""

    def __init__(self, workspace_root: Path, run_id: str) -> None:
        self.run_root = workspace_root / "workspace" / "default" / "stabilizer" / "run" / run_id

    async def ensure_layout(self) -> None:
        await asyncio.to_thread((self.run_root / "attempts").mkdir, parents=True, exist_ok=True)

    def attempt_dir(self, attempt_index: int) -> Path:
        return self.run_root / "attempts" / str(attempt_index)

    async def write_run_json(self, payload: dict[str, Any]) -> None:
        await self._write_json(self.run_root / "run.json", payload)

    async def write_proposal(self, attempt_index: int, payload: dict[str, Any]) -> None:
        await self._write_json(self.attempt_dir(attempt_index) / "proposal.json", payload)

    async def write_patch(self, attempt_index: int, patch_text: str) -> Path:
        path = self.attempt_dir(attempt_index) / "patch.diff"
        normalized = patch_text if patch_text.endswith("\n") else f"{patch_text}\n"
        await self._write_text(path, normalized)
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
        checks_dir = self.attempt_dir(attempt_index) / "checks"
        await asyncio.to_thread(checks_dir.mkdir, parents=True, exist_ok=True)
        await self._write_json(checks_dir / f"{check_name}.json", summary_payload)
        await self._write_text(checks_dir / f"{check_name}.log", log_text)

    async def write_metrics(self, attempt_index: int, payload: dict[str, Any]) -> None:
        await self._write_json(self.attempt_dir(attempt_index) / "metrics.json", payload)

    async def write_decision(self, attempt_index: int, payload: dict[str, Any]) -> None:
        await self._write_json(self.attempt_dir(attempt_index) / "decision.json", payload)

    async def write_tree_digest(self, attempt_index: int, digest: str) -> None:
        await self._write_text(self.attempt_dir(attempt_index) / "tree_digest.txt", f"{digest}\n")

    async def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        await self._write_text(path, canonical_json(payload) + "\n")

    async def _write_text(self, path: Path, content: str) -> None:
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(_write_utf8_text, path, content)


def _write_utf8_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")
