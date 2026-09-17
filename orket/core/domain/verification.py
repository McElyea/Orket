"""
Legacy fixture migration surface and existing sandbox HTTP verification facade.

Fixture execution belongs to the async application FixtureVerificationService.
Path containment alone does not provide read-only storage or hostile-code isolation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.schema import IssueVerification, VerificationResult

from .fixture_verifier import FixtureVerifier, VerificationSecurityError
from .sandbox_verifier import SandboxVerifier
from .verification_runner import RUNNER_CODE

VERIFICATION_DIR = "verification"
AGENT_OUTPUT_DIR = "agent_output"


class VerificationEngine:
    """Coordinator preserving the historical verification API surface."""

    _RUNNER_CODE = RUNNER_CODE
    _fixture_verifier = FixtureVerifier(verification_dir=VERIFICATION_DIR)
    _sandbox_verifier = SandboxVerifier()

    @staticmethod
    def _mark_all_failed(verification: IssueVerification) -> int:
        return VerificationEngine._fixture_verifier.mark_all_failed(verification)

    @staticmethod
    def verify(verification: IssueVerification, workspace_root: Path) -> VerificationResult:
        return VerificationEngine._fixture_verifier.verify(verification, workspace_root)

    @staticmethod
    async def verify_sandbox(sandbox: Any, verification: IssueVerification) -> VerificationResult:
        return await VerificationEngine._sandbox_verifier.verify_sandbox(sandbox, verification)


__all__ = [
    "AGENT_OUTPUT_DIR",
    "FixtureVerifier",
    "RUNNER_CODE",
    "SandboxVerifier",
    "VERIFICATION_DIR",
    "VerificationEngine",
    "VerificationSecurityError",
]
