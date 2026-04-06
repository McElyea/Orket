from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


class OpenClawJsonlSubprocessAdapter:
    """Minimal JSONL subprocess bridge for OpenClaw-style tool-intent traffic."""

    def __init__(
        self,
        *,
        command: Sequence[str],
        cwd: str | Path | None = None,
        env: Mapping[str, str] | None = None,
        io_timeout_seconds: float = 30.0,
    ) -> None:
        if not command:
            raise ValueError("command is required")
        self.command = [str(part) for part in command]
        self.cwd = str(cwd) if cwd is not None else None
        self.env = dict(env) if env is not None else None
        self.io_timeout_seconds = max(1.0, float(io_timeout_seconds))

    async def run_requests(self, requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        process = await asyncio.create_subprocess_exec(
            *self.command,
            cwd=self.cwd,
            env=self.env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        if process.stdin is None or process.stdout is None or process.stderr is None:
            raise RuntimeError("subprocess did not expose expected stdio pipes")

        responses: list[dict[str, Any]] = []
        try:
            for request in requests:
                payload = json.dumps(request, sort_keys=True, ensure_ascii=False)
                process.stdin.write(payload.encode("utf-8") + b"\n")
                await process.stdin.drain()

                line = await asyncio.wait_for(process.stdout.readline(), timeout=self.io_timeout_seconds)
                if not line:
                    raise RuntimeError("subprocess closed stdout before returning all responses")
                try:
                    response = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError as exc:
                    raise RuntimeError("subprocess emitted non-JSON response") from exc
                if not isinstance(response, dict):
                    raise RuntimeError("subprocess response must be a JSON object")
                responses.append(response)

            process.stdin.close()
            await process.stdin.wait_closed()

            return_code = await asyncio.wait_for(process.wait(), timeout=self.io_timeout_seconds)
            stderr_text = (await process.stderr.read()).decode("utf-8", errors="replace").strip()
            if return_code != 0:
                raise RuntimeError(f"subprocess exited with code {return_code}: {stderr_text}")
            return responses
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()


__all__ = ["OpenClawJsonlSubprocessAdapter"]
