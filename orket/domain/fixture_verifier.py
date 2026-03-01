from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from orket.logging import log_event
from orket.schema import IssueVerification, VerificationResult

from .verification_runner import RUNNER_CODE


class VerificationSecurityError(Exception):
    """Raised when verification detects a security violation."""


class FixtureVerifier:
    """Runs fixture-based verification in isolated subprocesses."""

    def __init__(self, verification_dir: str = "verification") -> None:
        self.verification_dir = verification_dir

    @staticmethod
    def mark_all_failed(verification: IssueVerification) -> int:
        for scenario in verification.scenarios:
            scenario.status = "fail"
        return len(verification.scenarios)

    def verify(self, verification: IssueVerification, workspace_root: Path) -> VerificationResult:
        logs: list[str] = []
        passed = 0
        failed = 0
        now = datetime.now(UTC).isoformat()
        logs.append(f"--- Verification Started at {now} ---")

        if not verification.fixture_path:
            logs.append("No verification fixture defined. Skipping empirical tests.")
            return VerificationResult(
                timestamp=now,
                total_scenarios=len(verification.scenarios),
                passed=0,
                failed=0,
                logs=logs,
            )

        fixture_path = (workspace_root / verification.fixture_path).resolve()
        verification_root = (workspace_root / self.verification_dir).resolve()
        try:
            fixture_path.relative_to(verification_root)
        except ValueError as exc:
            msg = (
                f"SECURITY VIOLATION: Fixture path '{verification.fixture_path}' is outside the "
                f"verification directory '{self.verification_dir}/'. Agents cannot execute code "
                "from arbitrary locations."
            )
            logs.append(msg)
            log_event(
                "verification_security_violation",
                {"fixture_path": str(fixture_path), "verification_root": str(verification_root)},
                workspace_root,
            )
            raise VerificationSecurityError(msg) from exc

        if not fixture_path.exists():
            logs.append(f"ERROR: Fixture file not found at {fixture_path}")
            failed = self.mark_all_failed(verification)
            return VerificationResult(
                timestamp=now,
                total_scenarios=len(verification.scenarios),
                passed=0,
                failed=failed,
                logs=logs,
            )

        timeout_sec = int(os.getenv("ORKET_VERIFY_TIMEOUT_SEC", "5"))
        payload = {
            "fixture_path": str(fixture_path),
            "scenarios": [
                {
                    "id": scenario.id,
                    "input_data": scenario.input_data,
                    "expected_output": scenario.expected_output,
                }
                for scenario in verification.scenarios
            ],
        }

        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = ""
            result = subprocess.run(
                [sys.executable, "-I", "-c", RUNNER_CODE],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                cwd=str(verification_root),
                env=env,
                check=False,
            )

            if result.returncode != 0:
                logs.append(f"FATAL ERROR loading fixture: subprocess exit code {result.returncode}")
                if result.stderr:
                    logs.append(f"STDERR: {result.stderr.strip()}")
                failed = self.mark_all_failed(verification)
            else:
                try:
                    parsed = json.loads(result.stdout or "{}")
                except json.JSONDecodeError as exc:
                    parsed = {"ok": False, "fatal_error": f"Invalid subprocess JSON output: {exc}", "results": []}

                if not parsed.get("ok", False):
                    logs.append(f"FATAL ERROR loading fixture: {parsed.get('fatal_error', 'unknown')}")
                    if parsed.get("traceback"):
                        logs.append(parsed["traceback"])
                    failed = self.mark_all_failed(verification)
                else:
                    outcomes = {item.get("id"): item for item in parsed.get("results", [])}
                    for scenario in verification.scenarios:
                        logs.append(f"Running Scenario: {scenario.description}")
                        outcome = outcomes.get(scenario.id)
                        if not outcome:
                            logs.append(f"  [FAIL] Missing subprocess result for scenario {scenario.id}")
                            scenario.status = "fail"
                            failed += 1
                            continue
                        scenario.actual_output = outcome.get("actual_output")
                        if outcome.get("status") == "pass":
                            logs.append(f"  [PASS] Actual matches Expected: {scenario.actual_output}")
                            scenario.status = "pass"
                            passed += 1
                        else:
                            if outcome.get("error"):
                                logs.append(f"  [ERROR] Execution error: {outcome['error']}")
                            else:
                                logs.append(f"  [FAIL] Expected {scenario.expected_output}, got {scenario.actual_output}")
                            scenario.status = "fail"
                            failed += 1
        except subprocess.TimeoutExpired:
            logs.append(f"FATAL ERROR loading fixture: subprocess timeout after {timeout_sec}s")
            failed = self.mark_all_failed(verification)
        except VerificationSecurityError:
            raise
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            logs.append(f"FATAL ERROR loading fixture: {type(exc).__name__}: {exc}")
            failed = self.mark_all_failed(verification)

        logs.append(f"--- Verification Complete: {passed} Passed, {failed} Failed ---")
        return VerificationResult(
            timestamp=now,
            total_scenarios=len(verification.scenarios),
            passed=passed,
            failed=failed,
            logs=logs,
        )
