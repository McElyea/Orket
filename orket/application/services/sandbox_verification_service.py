"""Own captured sandbox HTTP verification through observation and client cleanup."""
from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from orket.adapters.execution.owned_io import run_owned_io
from orket.adapters.execution.sandbox_http import SandboxHttpAdapter
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.domain.sandbox_verifier import (
    SandboxHttpObservation,
    SandboxVerificationInput,
    capture_sandbox_verification,
    interpret_sandbox_observations,
)
from orket.schema import IssueVerification, VerificationResult


class SandboxVerificationService:
    def __init__(self, *, runtime_inputs: RuntimeInputService | None = None, timeout_s: float = 10.0,
                 http_factory: Callable[[float], SandboxHttpAdapter] = SandboxHttpAdapter):
        if not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError("E_SANDBOX_HTTP_TIMEOUT_INVALID")
        self.runtime_inputs = runtime_inputs or RuntimeInputService()
        self.timeout_s, self.http_factory = timeout_s, http_factory

    async def verify_sandbox(self, sandbox: Any, verification: IssueVerification) -> VerificationResult:
        captured = capture_sandbox_verification(
            sandbox_id=sandbox.id, base_url=sandbox.api_url, timestamp=self.runtime_inputs.utc_now_iso(),
            verification=verification,
        )
        observations = await run_owned_io(
            lambda: self._observe(captured), label="sandbox-http-verification", preserve_failure=True,
            cancel_on_interrupt=True,
        )
        result, scenarios = interpret_sandbox_observations(captured, observations)
        verification.scenarios = list(scenarios)
        return result

    async def _observe(self, captured: SandboxVerificationInput) -> tuple[SandboxHttpObservation, ...]:
        if all(item.request is None for item in captured.scenarios):
            return tuple(SandboxHttpObservation(item.scenario_id, error=item.rejection) for item in captured.scenarios)
        observations = []
        async with self.http_factory(self.timeout_s) as transport:
            for item in captured.scenarios:
                observation = (await transport.observe(item.request) if item.request is not None else
                               SandboxHttpObservation(item.scenario_id, error=item.rejection))
                observations.append(observation)
        return tuple(observations)
