"""Docker CLI translation; the application authorizes each resource operation."""
from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from pathlib import Path

from orket.adapters.execution.fixture_runner import RUNNER_CODE
from orket.core.contracts.owned_command import OwnedCommandResult

OWNER_LABEL = "org.orket.verification.owner"


side_effecting = True


class DockerObservationError(RuntimeError):
    """The daemon observation cannot establish the requested fact."""


def container_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise DockerObservationError("Docker did not return a full immutable container ID")
    return value


class FixtureDockerAdapter:
    side_effecting = True

    def __init__(self, run: Callable[..., Awaitable[OwnedCommandResult]]):
        self.run = run

    async def create(self, *, name: str, owner_id: str, root: Path, image: str) -> str:
        result = await self.run("create", ["docker", "container", "create", "--name", name,
            "--label", f"{OWNER_LABEL}={owner_id}", "--interactive", "--network", "none", "--read-only",
            "--tmpfs", "/tmp:size=10m", "--memory", "256m", "--cpus", "0.5",
            "--volume", f"{root}:/verification:ro", "--workdir", "/verification",
            image, "python", "-I", "-c", RUNNER_CODE])
        self._require_success(result, "create")
        return container_id(result.stdout.decode("ascii").strip())

    async def attach(self, identity: str, payload: bytes) -> OwnedCommandResult:
        return await self.run("attach", ["docker", "container", "start", "--attach", "--interactive",
                                       container_id(identity)], input_data=payload)

    async def inspect(self, identity: str) -> dict:
        result = await self.run("inspect", ["docker", "container", "inspect", container_id(identity)])
        self._require_success(result, "inspect")
        rows = json.loads(result.stdout)
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise DockerObservationError("Invalid container inspection")
        return rows[0]

    async def discover(self, name: str) -> list[str]:
        result = await self.run("discover", ["docker", "container", "ls", "--all", "--no-trunc",
                "--filter", f"name={name}", "--format", "{{json .}}"])
        self._require_success(result, "discover")
        identities = []
        for line in result.stdout.splitlines():
            row = json.loads(line)
            if not isinstance(row, dict) or not isinstance(row.get("Names"), str):
                raise DockerObservationError("Invalid container listing")
            if row["Names"] == name:
                identities.append(container_id(row.get("ID", "")))
        return identities

    async def absent(self, identity: str) -> bool:
        result = await self.run("absence", ["docker", "container", "ls", "--all", "--no-trunc",
                "--filter", f"id={container_id(identity)}", "--format", "{{.ID}}"])
        self._require_success(result, "absence")
        observed = [container_id(line) for line in result.stdout.decode("ascii").splitlines()]
        return identity not in observed

    async def remove(self, identity: str) -> None:
        result = await self.run("remove", ["docker", "container", "rm", "--force", "--volumes",
                                         container_id(identity)])
        self._require_success(result, "remove")

    @staticmethod
    def _require_success(result: OwnedCommandResult, operation: str) -> None:
        if result.reason != "completed" or result.returncode != 0 or not result.cleanup_confirmed:
            # CLI failure is never interpreted as successful daemon absence.
            raise DockerObservationError(f"Docker {operation} did not complete successfully ({result.reason})")
