"""
Fixture location constants and the retained security-error export.

Fixture execution belongs to the async application FixtureVerificationService.
Path containment alone does not provide read-only storage or hostile-code isolation.
"""

from __future__ import annotations

from .fixture_verifier import VerificationSecurityError

VERIFICATION_DIR = "verification"
AGENT_OUTPUT_DIR = "agent_output"


__all__ = [
    "AGENT_OUTPUT_DIR",
    "VERIFICATION_DIR",
    "VerificationSecurityError",
]
