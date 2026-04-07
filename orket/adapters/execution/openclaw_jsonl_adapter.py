from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class OpenClawSubprocessError(RuntimeError):
    """Subprocess failure carrying the number of completed adapter responses."""

    def __init__(self, message: str, *, completed_count: int) -> None:
        super().__init__(message)
        self.completed_count = int(completed_count)


@dataclass(frozen=True)
class PartialAdapterResult:
    responses: list[dict[str, Any]]
    failed_at: int | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.failed_at is None and self.error is None

    @property
    def completed_count(self) -> int:
        return len(self.responses)


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

    async def run_requests(self, requests: list[dict[str, Any]]) -> PartialAdapterResult:
        try:
            process = await asyncio.create_subprocess_exec(
                *self.command,
                cwd=self.cwd,
                env=self.env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            return PartialAdapterResult(
                responses=[],
                failed_at=0,
                error=str(OpenClawSubprocessError(str(exc), completed_count=0)),
        )
        if process.stdin is None or process.stdout is None or process.stderr is None:
            if process.returncode is None:
                process.kill()
                await process.wait()
            return PartialAdapterResult(
                responses=[],
                failed_at=0,
                error="subprocess did not expose expected stdio pipes",
            )

        responses: list[dict[str, Any]] = []
        try:
            for request in requests:
                payload = json.dumps(request, sort_keys=True, ensure_ascii=False)
                process.stdin.write(payload.encode("utf-8") + b"\n")
                await process.stdin.drain()

                line = await asyncio.wait_for(process.stdout.readline(), timeout=self.io_timeout_seconds)
                if not line:
                    return self._partial_failure(
                        responses,
                        "subprocess closed stdout before returning all responses",
                    )
                try:
                    response = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError as exc:
                    return self._partial_failure(
                        responses,
                        f"subprocess emitted non-JSON response: {exc}",
                    )
                if not isinstance(response, dict):
                    return self._partial_failure(responses, "subprocess response must be a JSON object")
                responses.append(response)

            process.stdin.close()
            await process.stdin.wait_closed()

            return_code = await asyncio.wait_for(process.wait(), timeout=self.io_timeout_seconds)
            stderr_text = (await process.stderr.read()).decode("utf-8", errors="replace").strip()
            if return_code != 0:
                return self._partial_failure(
                    responses,
                    f"subprocess exited with code {return_code}: {stderr_text}",
                )
            return PartialAdapterResult(responses=responses)
        except (TimeoutError, BrokenPipeError, ConnectionResetError, OSError, RuntimeError) as exc:
            return self._partial_failure(responses, str(exc))
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()

    @staticmethod
    def _partial_failure(responses: list[dict[str, Any]], message: str) -> PartialAdapterResult:
        return PartialAdapterResult(
            responses=list(responses),
            failed_at=len(responses),
            error=str(OpenClawSubprocessError(message, completed_count=len(responses))),
        )


__all__ = ["OpenClawJsonlSubprocessAdapter", "OpenClawSubprocessError", "PartialAdapterResult"]
