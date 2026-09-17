"""Deterministic fixture policy and result interpretation; no execution authority."""
from __future__ import annotations

import json
from pathlib import Path

from orket.schema import IssueVerification, VerificationResult


class VerificationSecurityError(Exception):
    """A fixture does not meet the admitted path policy."""


def resolve_execution_mode(profile: str, requested: str, unsafe_override: str) -> str:
    mode = requested.strip().lower()
    if mode not in {"subprocess", "container"}:
        raise ValueError(f"Unknown verification execution mode: {requested!r}")
    if (profile.strip().lower() == "production" and mode == "subprocess"
            and unsafe_override.strip().lower() not in {"1", "true", "yes", "on"}):
        raise ValueError("Verification subprocess mode is disabled in production profile. "
                         "Set ORKET_VERIFY_EXECUTION_MODE=container.")
    return mode


def _outcomes(stdout: bytes) -> dict:
    parsed = json.loads(stdout)
    if not isinstance(parsed, dict) or parsed.get("ok") is not True:
        error = parsed.get("fatal_error", "unknown") if isinstance(parsed, dict) else "invalid result object"
        raise ValueError(str(error))
    rows = parsed.get("results")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Invalid fixture results")
    ids = [row.get("id") for row in rows]
    if any(not isinstance(key, str) for key in ids) or len(set(ids)) != len(ids):
        raise ValueError("Invalid or duplicate fixture scenario identity")
    return dict(zip(ids, rows, strict=True))


def interpret_fixture(verification: IssueVerification, *, timestamp: str, stdout: bytes = b"",
                      error: str | None = None, lifetime: dict | None = None) -> tuple:
    """Return a result and copied scenarios; callers own applying the observation."""
    scenarios = [scenario.model_copy(deep=True) for scenario in verification.scenarios]
    logs = [f"--- Verification Started at {timestamp} ---"]
    passed = failed = 0
    outcomes = {}
    if verification.fixture_path and error is None:
        try:
            outcomes = _outcomes(stdout)
        except (ValueError, UnicodeError) as exc:
            error = f"Invalid fixture output: {exc}"
    if not verification.fixture_path:
        logs.append("No verification fixture defined. Skipping empirical tests.")
    elif error is not None:
        logs.append(f"FATAL ERROR loading fixture: {error}")
        for scenario in scenarios:
            scenario.status = "fail"
        failed = len(scenarios)
    else:
        for scenario in scenarios:
            outcome = outcomes.get(scenario.id, {})
            scenario.actual_output = outcome.get("actual_output")
            matched = (outcome.get("status") == "pass" and not outcome.get("error")
                       and "actual_output" in outcome and scenario.actual_output == scenario.expected_output)
            scenario.status = "pass" if matched else "fail"
            passed += int(matched)
            failed += int(not matched)
            detail = outcome.get("error") or f"Expected {scenario.expected_output}, got {scenario.actual_output}"
            logs.append(f"Running Scenario: {scenario.description}")
            logs.append(f"  [{'PASS' if matched else 'FAIL'}] {detail}")
    logs.append(f"--- Verification Complete: {passed} Passed, {failed} Failed ---")
    return VerificationResult(timestamp=timestamp, total_scenarios=len(scenarios), passed=passed,
                              failed=failed, logs=logs, process_lifetime=lifetime), scenarios


class FixtureVerifier:
    """Legacy symbols pending BT4-FIXTURE-SYNC-RETIRE at the 0.7.0 cutover."""

    def __init__(self, verification_dir: str = "verification") -> None:
        self.verification_dir = verification_dir

    @staticmethod
    def mark_all_failed(verification: IssueVerification) -> int:
        for scenario in verification.scenarios:
            scenario.status = "fail"
        return len(verification.scenarios)

    def verify(self, verification: IssueVerification, workspace_root: Path) -> VerificationResult:
        raise RuntimeError("Synchronous fixture execution was retired. "
                           "Use await FixtureVerificationService(workspace).verify(verification).")
