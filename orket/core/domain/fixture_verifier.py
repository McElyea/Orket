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
    def _is_truthy(value: str | None) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    def _resolve_execution_mode(self) -> str:
        profile = str(os.getenv("ORKET_RUNTIME_PROFILE") or os.getenv("ORKET_PROFILE") or "development").strip().lower()
        requested = str(os.getenv("ORKET_VERIFY_EXECUTION_MODE", "subprocess")).strip().lower() or "subprocess"
        if requested not in {"subprocess", "container"}:
            requested = "subprocess"
        unsafe_override = self._is_truthy(os.getenv("ORKET_VERIFY_ALLOW_UNSAFE_SUBPROCESS", "0"))
        if profile == "production" and requested != "container" and not unsafe_override:
            raise RuntimeError(
                "Verification subprocess mode is disabled in production profile. "
                "Set ORKET_VERIFY_EXECUTION_MODE=container."
            )
        return requested

    @staticmethod
    def _run_subprocess(payload: dict, verification_root: Path, timeout_sec: int) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = ""
        return subprocess.run(
            [sys.executable, "-I", "-c", RUNNER_CODE],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=str(verification_root),
            env=env,
            check=False,
        )

    @staticmethod
    def _run_container(payload: dict, verification_root: Path, timeout_sec: int) -> subprocess.CompletedProcess[str]:
        fixture_path = Path(str(payload.get("fixture_path") or ""))
        try:
            relative_fixture = fixture_path.resolve().relative_to(verification_root.resolve()).as_posix()
        except ValueError:
            relative_fixture = fixture_path.name

        container_payload = dict(payload)
        container_payload["fixture_path"] = f"/verification/{relative_fixture}"
        image = str(os.getenv("ORKET_VERIFY_CONTAINER_IMAGE", "python:3.11-alpine")).strip() or "python:3.11-alpine"
        command = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:size=10m",
            "--memory",
            "256m",
            "--cpus",
            "0.5",
            "-v",
            f"{verification_root.resolve()}:/verification:ro",
            "-w",
            "/verification",
            image,
            "python",
            "-I",
            "-c",
            RUNNER_CODE,
        ]
        return subprocess.run(
            command,
            input=json.dumps(container_payload),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )

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
            mode = self._resolve_execution_mode()
            if mode == "container":
                result = self._run_container(payload, verification_root, timeout_sec)
            else:
                result = self._run_subprocess(payload, verification_root, timeout_sec)

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
                                logs.append(
                                    f"  [FAIL] Expected {scenario.expected_output}, got {scenario.actual_output}"
                                )
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
