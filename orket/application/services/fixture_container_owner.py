"""Application owner of a single fixture container, including interrupted creation."""
from __future__ import annotations

import asyncio
from pathlib import Path

from orket.adapters.execution.fixture_docker import OWNER_LABEL, DockerObservationError, FixtureDockerAdapter
from orket.application.services.command_process_supervisor import (
    CommandProcessCancelled,
    CommandProcessSupervisor,
)
from orket.core.contracts.owned_container import OwnedContainerResult


class FixtureContainerCancelled(asyncio.CancelledError):
    def __init__(self, lifetime: OwnedContainerResult):
        super().__init__("Fixture container cancelled")
        self.lifetime = lifetime


class FixtureContainerOwner:
    def __init__(self, *, workspace: Path, environment: dict, name: str, owner_id: str):
        self.workspace, self.environment = workspace, environment
        self.name, self.owner_id = name, owner_id
        self.supervisor = CommandProcessSupervisor(workspace, cancellation_event="verification_process_cancelled")
        self.adapter = FixtureDockerAdapter(self._command)
        self.identity = None
        self.attached = None
        self.commands: list[dict] = []
        self.diagnostics: list[str] = []
        self.create_attempted = False
        self.create_acknowledged = False
        self.returncode = None
        self.reason = "launch_failed"
        self.command_timeout = 5.0

    async def _command(self, operation, argv, *, input_data=None):
        try:
            result = await self.supervisor.run(argv, cwd=self.workspace, environment=self.environment,
                                               timeout_seconds=self.command_timeout, input_data=input_data)
        except CommandProcessCancelled as exc:
            result = exc.lifetime
            self.commands.append({"operation": operation, "returncode": result.returncode, **result.lifetime()})
            if operation == "attach":
                self.attached = result
            raise
        self.commands.append({"operation": operation, "returncode": result.returncode, **result.lifetime()})
        return result

    def _validate_owner(self, observed: dict, identity: str) -> None:
        config = observed.get("Config")
        labels = config.get("Labels") if isinstance(config, dict) else None
        if (observed.get("Id") != identity or observed.get("Name") != f"/{self.name}"
                or not isinstance(labels, dict) or labels.get(OWNER_LABEL) != self.owner_id):
            raise DockerObservationError("Container identity or owner binding mismatch; removal refused")

    async def _execute(self, root, image, payload):
        self.create_attempted = True
        self.identity = await self.adapter.create(name=self.name, owner_id=self.owner_id, root=root, image=image)
        self.create_acknowledged = True
        self._validate_owner(await self.adapter.inspect(self.identity), self.identity)
        self.attached = await self.adapter.attach(self.identity, payload)
        self.reason = self.attached.reason
        if self.reason != "completed":
            return
        observed = await self.adapter.inspect(self.identity)
        self._validate_owner(observed, self.identity)
        state = observed.get("State")
        if (not isinstance(state, dict) or state.get("Running") is not False
                or state.get("Status") != "exited" or type(state.get("ExitCode")) is not int):
            raise DockerObservationError("Container terminal exit was not observed")
        self.returncode = state["ExitCode"]
        if self.attached.returncode != self.returncode:
            raise DockerObservationError("Attached CLI and observed container exit codes disagree")

    async def _cleanup(self) -> bool:
        if not self.create_attempted:
            return True
        try:
            if self.identity is None:
                found = await self.adapter.discover(self.name)
                if len(found) != 1:
                    # A killed CLI can leave an in-flight create at the daemon. Empty is not proof here.
                    raise DockerObservationError("Create acknowledgement lost; owned container not established")
                self.identity = found[0]
            if self.create_acknowledged and await self.adapter.absent(self.identity):
                return True
            self._validate_owner(await self.adapter.inspect(self.identity), self.identity)
            try:
                await self.adapter.remove(self.identity)
            except DockerObservationError as exc:
                self.diagnostics.append(str(exc))
            return await self.adapter.absent(self.identity)
        except Exception as exc:
            # Resource-supervisor boundary: even an unexpected adapter failure must retain uncertainty.
            self.diagnostics.append(f"Container cleanup unconfirmed: {type(exc).__name__}: {exc}")
            return False

    async def _lifecycle(self, root, image, payload, timeout_seconds):
        try:
            async with asyncio.timeout(timeout_seconds):
                self.command_timeout = timeout_seconds
                await self._execute(root, image, payload)
        except asyncio.CancelledError:
            self.reason = "cancelled"
        except TimeoutError:
            self.reason = "timeout"
        except Exception as exc:
            # Resource-supervisor boundary: cleanup still runs after an unexpected execution failure.
            self.reason = "launch_failed" if self.attached is None else "observation_failed"
            self.diagnostics.append(f"{type(exc).__name__}: {exc}")
        self.command_timeout = 3.0
        cleanup = asyncio.create_task(self._cleanup())
        while True:
            try:
                confirmed = await asyncio.shield(cleanup)
                break
            except asyncio.CancelledError:
                self.reason = "cancelled"
                if cleanup.cancelled():
                    self.diagnostics.append("Cleanup task interrupted; retrying identity-bound observation")
                    cleanup = asyncio.create_task(self._cleanup())
        confirmed = confirmed and all(command["cleanup_confirmed"] for command in self.commands)
        if not confirmed:
            self.reason = "cleanup_unconfirmed"
        return OwnedContainerResult(self.name, self.owner_id, self.identity, self.returncode, self.reason,
                                    confirmed, self.attached, tuple(self.commands), tuple(self.diagnostics))

    async def run(self, *, root: Path, image: str, payload: bytes, timeout_seconds: float) -> OwnedContainerResult:
        owner = asyncio.create_task(self._lifecycle(root, image, payload, timeout_seconds))
        cancelled = False
        while True:
            try:
                result = await asyncio.shield(owner)
                break
            except asyncio.CancelledError:
                if owner.cancelled():
                    raise
                if not cancelled and not owner.cancelling():
                    owner.cancel()
                cancelled = True
        if cancelled:
            raise FixtureContainerCancelled(result)
        return result
