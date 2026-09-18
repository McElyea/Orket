"""Canonical async fixture admission, execution ownership, and result publication."""
from __future__ import annotations

import asyncio
import json
import math
import os
import sys
from pathlib import Path
from uuid import UUID

from orket.adapters.execution.fixture_runner import RUNNER_CODE
from orket.application.services.command_process_supervisor import (
    CommandProcessCancelled,
    CommandProcessSupervisor,
)
from orket.application.services.fixture_container_owner import FixtureContainerCancelled, FixtureContainerOwner
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.domain.fixture_verifier import VerificationSecurityError, interpret_fixture, resolve_execution_mode
from orket.exceptions import OrketInfrastructureError
from orket.logging import log_event
from orket.schema import IssueVerification, VerificationResult


class FixtureVerificationUncertain(OrketInfrastructureError):
    """No result may be published while fixture resource cleanup is unconfirmed."""

    def __init__(self, lifetime: dict):
        super().__init__("Fixture cleanup unconfirmed; verification result was not published")
        self.lifetime = lifetime


async def _record_lifetime(workspace: Path, event: str, lifetime: dict) -> None:
    publication = asyncio.create_task(asyncio.to_thread(log_event, event, lifetime, workspace))
    while True:
        try:
            await asyncio.shield(publication)
            return
        except asyncio.CancelledError:
            if publication.cancelled():
                raise


class FixtureVerificationService:
    def __init__(self, workspace: Path, *, environment: dict | None = None,
                 runtime_inputs: RuntimeInputService | None = None):
        self.workspace = workspace
        self.environment = dict(os.environ if environment is None else environment)
        self.runtime_inputs = runtime_inputs or RuntimeInputService()
        self.supervisor = CommandProcessSupervisor(workspace, cancellation_event="verification_process_cancelled")

    def _paths(self, fixture: str) -> tuple[Path, Path, bool]:
        root = (self.workspace / "verification").resolve()
        path = (self.workspace / fixture).resolve()
        if not path.is_relative_to(root):
            raise VerificationSecurityError(f"SECURITY VIOLATION: Fixture path '{fixture}' is outside verification/.")
        return root, path, path.is_file()

    def _settings(self) -> tuple[str, float]:
        env = self.environment
        mode = resolve_execution_mode(env.get("ORKET_RUNTIME_PROFILE") or env.get("ORKET_PROFILE", "development"),
                                      env.get("ORKET_VERIFY_EXECUTION_MODE", "subprocess"),
                                      env.get("ORKET_VERIFY_ALLOW_UNSAFE_SUBPROCESS", "0"))
        timeout = float(env.get("ORKET_VERIFY_TIMEOUT_SEC", "5"))
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Verification timeout must be a finite positive number")
        return mode, timeout

    async def _execute(self, verification, root, path, mode, timeout_seconds):
        payload = {"fixture_path": str(path), "scenarios": [
            {"id": scenario.id, "input_data": scenario.input_data, "expected_output": scenario.expected_output}
            for scenario in verification.scenarios]}
        if mode == "container":
            payload["fixture_path"] = "/verification/" + path.relative_to(root).as_posix()
            owner_id = str(UUID(self.runtime_inputs.create_effect_owner_id()))
            owner = FixtureContainerOwner(workspace=self.workspace, environment=self.environment,
                name="orket-verification-" + UUID(owner_id).hex, owner_id=owner_id)
            image = self.environment.get("ORKET_VERIFY_CONTAINER_IMAGE", "python:3.11-alpine").strip()
            if not image or image.startswith("-"):
                raise ValueError("Verification container image must be an image reference")
            return await owner.run(root=root, image=image, payload=json.dumps(payload).encode("utf-8"),
                                   timeout_seconds=timeout_seconds)
        environment = {**self.environment, "PYTHONPATH": ""}
        return await self.supervisor.run([sys.executable, "-I", "-c", RUNNER_CODE], cwd=root,
            environment=environment, timeout_seconds=timeout_seconds, input_data=json.dumps(payload).encode("utf-8"))

    async def verify(self, verification: IssueVerification) -> VerificationResult:
        timestamp = self.runtime_inputs.utc_now_iso()
        observed = None
        error = None
        if verification.fixture_path:
            try:
                root, path, exists = await asyncio.to_thread(self._paths, verification.fixture_path)
                if not exists:
                    raise ValueError(f"Fixture file not found at {path}")
                mode, timeout = self._settings()
                observed = await self._execute(verification, root, path, mode, timeout)
            except (CommandProcessCancelled, FixtureContainerCancelled) as exc:
                await _record_lifetime(self.workspace, "fixture_verification_cancelled", exc.lifetime.lifetime())
                raise
            except VerificationSecurityError:
                await asyncio.to_thread(log_event, "verification_security_violation",
                                        {"fixture_path": verification.fixture_path}, self.workspace)
                raise
            except (OSError, ValueError) as exc:
                error = f"{type(exc).__name__}: {exc}"
        if observed is not None:
            if not observed.cleanup_confirmed:
                await _record_lifetime(self.workspace, "fixture_verification_uncertain", observed.lifetime())
                raise FixtureVerificationUncertain(observed.lifetime())
            if observed.reason != "completed" or not observed.capture_complete:
                error = f"Fixture execution {observed.reason}"
            elif observed.returncode != 0:
                error = f"subprocess exit code {observed.returncode}; STDERR: {observed.stderr.decode('utf-8', 'replace')}"
        result, scenarios = interpret_fixture(verification, timestamp=timestamp, error=error,
            stdout=observed.stdout if observed else b"", lifetime=observed.lifetime() if observed else None)
        verification.scenarios = scenarios
        return result
