"""
Legacy synchronous fixture migration surface.

Fixture execution belongs to the async application FixtureVerificationService.
Path containment alone does not provide read-only storage or hostile-code isolation.
"""

from __future__ import annotations

from pathlib import Path

from orket.schema import IssueVerification, VerificationResult

from .fixture_verifier import FixtureVerifier, VerificationSecurityError

VERIFICATION_DIR = "verification"
AGENT_OUTPUT_DIR = "agent_output"


class VerificationEngine:
    """Coordinator preserving the historical verification API surface."""

    _fixture_verifier = FixtureVerifier(verification_dir=VERIFICATION_DIR)

    @staticmethod
    def _mark_all_failed(verification: IssueVerification) -> int:
        return VerificationEngine._fixture_verifier.mark_all_failed(verification)

    @staticmethod
    def verify(verification: IssueVerification, workspace_root: Path) -> VerificationResult:
        return VerificationEngine._fixture_verifier.verify(verification, workspace_root)

__all__ = [
    "AGENT_OUTPUT_DIR",
    "FixtureVerifier",
    "VERIFICATION_DIR",
    "VerificationEngine",
    "VerificationSecurityError",
]
