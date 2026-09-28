"""Canonical async fixture admission, execution ownership, and result publication."""
from __future__ import annotations

import asyncio
import json
import math
import os
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from uuid import UUID

from orket.adapters.execution.fixture_runner import RUNNER_CODE
from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.command_process_supervisor import (
    CommandProcessCancelled,
    CommandProcessSupervisor,
)
from orket.application.services.fixture_container_owner import FixtureContainerCancelled, FixtureContainerOwner
from orket.application.services.process_input_service import capture_process_context
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.contracts.verification_inputs import capture_fixture_verification, verification_timestamp
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
    def __init__(self, workspace: Path, *, utc_now: Callable[[], datetime], environment: dict | None = None,
                 runtime_inputs: RuntimeInputService | None = None):
        self.workspace = workspace
        self.utc_now = utc_now
        self.environment = dict(os.environ if environment is None else environment)
        self.runtime_inputs = runtime_inputs or RuntimeInputService()
        self.supervisor = CommandProcessSupervisor(workspace, cancellation_event="verification_process_cancelled")

    @staticmethod
    def _paths(workspace: Path, fixture: str) -> tuple[Path, Path, bool]:
        root = (workspace / "verification").resolve()
        path = (workspace / fixture).resolve()
        if not path.is_relative_to(root):
            raise VerificationSecurityError(f"SECURITY VIOLATION: Fixture path '{fixture}' is outside verification/.")
        return root, path, path.is_file()

    @staticmethod
    def _settings(env) -> tuple[str, float]:
        mode = resolve_execution_mode(env.get("ORKET_RUNTIME_PROFILE") or env.get("ORKET_PROFILE", "development"),
                                      env.get("ORKET_VERIFY_EXECUTION_MODE", "subprocess"),
                                      env.get("ORKET_VERIFY_ALLOW_UNSAFE_SUBPROCESS", "0"))
        timeout = float(env.get("ORKET_VERIFY_TIMEOUT_SEC", "5"))
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Verification timeout must be a finite positive number")
        return mode, timeout

    async def _execute(self, verification, root, path, mode, timeout_seconds, *,
                       workspace, environment, create_owner_id, supervisor):
        payload = {"fixture_path": str(path), "scenarios": [
            {"id": scenario.id, "input_data": scenario.input_data, "expected_output": scenario.expected_output}
            for scenario in verification.scenarios]}
        if mode == "container":
            payload["fixture_path"] = "/verification/" + path.relative_to(root).as_posix()
            owner_id = str(UUID(create_owner_id()))
            owner = FixtureContainerOwner(workspace=workspace, environment=environment,
                name="orket-verification-" + UUID(owner_id).hex, owner_id=owner_id)
            image = environment.get("ORKET_VERIFY_CONTAINER_IMAGE", "python:3.11-alpine").strip()
            if not image or image.startswith("-"):
                raise ValueError("Verification container image must be an image reference")
            return await owner.run(root=root, image=image, payload=json.dumps(payload).encode("utf-8"),
                                   timeout_seconds=timeout_seconds)
        return await supervisor.run([sys.executable, "-I", "-c", RUNNER_CODE], cwd=root,
            environment={**environment, "PYTHONPATH": ""}, timeout_seconds=timeout_seconds,
            input_data=json.dumps(payload).encode("utf-8"))

    async def verify(self, verification: IssueVerification) -> VerificationResult:
        destination = verification
        verification = capture_fixture_verification(verification)
        utc_now, create_owner_id = self.utc_now, self.runtime_inputs.create_effect_owner_id
        timestamp = verification_timestamp(utc_now())
        workspace, environment = capture_process_context(cwd=self.workspace, environment=self.environment)
        supervisor = self.supervisor.for_workspace(workspace)
        paths, publish = self._paths, log_event
        caller = asyncio.current_task()
        cancellations_at_admission = caller.cancelling() if caller is not None else 0
        observed = None
        error = None
        if verification.fixture_path:
            try:
                root, path, exists = await run_owned_thread(
                    lambda: paths(workspace, verification.fixture_path), label="fixture-admission-metadata")
                if not exists:
                    raise ValueError(f"Fixture file not found at {path}")
                mode, timeout = self._settings(environment)
                observed = await self._execute(verification, root, path, mode, timeout,
                    workspace=workspace, environment=environment, create_owner_id=create_owner_id, supervisor=supervisor)
            except (CommandProcessCancelled, FixtureContainerCancelled) as exc:
                await _record_lifetime(workspace, "fixture_verification_cancelled", exc.lifetime.lifetime())
                raise
            except VerificationSecurityError:
                await run_owned_thread(lambda: publish("verification_security_violation",
                    {"fixture_path": verification.fixture_path}, workspace), label="fixture-security-publication")
                raise
            except (OSError, ValueError) as exc:
                if caller is not None and caller.cancelling() > cancellations_at_admission:
                    raise
                error = f"{type(exc).__name__}: {exc}"
        if observed is not None:
            if not observed.cleanup_confirmed:
                await _record_lifetime(workspace, "fixture_verification_uncertain", observed.lifetime())
                raise FixtureVerificationUncertain(observed.lifetime())
            if observed.reason != "completed" or not observed.capture_complete:
                error = f"Fixture execution {observed.reason}"
            elif observed.returncode != 0:
                error = f"subprocess exit code {observed.returncode}; STDERR: {observed.stderr.decode('utf-8', 'replace')}"
        result, scenarios = interpret_fixture(verification, timestamp=timestamp, error=error,
            stdout=observed.stdout if observed else b"", lifetime=observed.lifetime() if observed else None)
        destination.scenarios = scenarios
        return result
