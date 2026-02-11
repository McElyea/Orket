"""
Verification Engine (The 'FIT' Executor)

Runs physical code fixtures to verify Issue completion.

SECURITY: Fixtures are loaded from a READ-ONLY verification directory.
Agents can only write to their workspace, NOT to the verification directory.
This prevents the write-then-execute RCE vulnerability.
"""
from __future__ import annotations
import sys
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime, UTC
from typing import Any

from orket.schema import IssueVerification, VerificationResult
from orket.logging import log_event


# Verification fixtures MUST live in this subdirectory (read-only to agents)
VERIFICATION_DIR = "verification"

# Agent workspace where agents write code (agents CANNOT execute from here)
AGENT_OUTPUT_DIR = "agent_output"


class VerificationSecurityError(Exception):
    """Raised when verification detects a security violation."""
    pass


class VerificationEngine:
    """
    Empirical Verification Service (The 'FIT' Executor).
    Runs physical code fixtures to verify Issue completion.

    SECURITY MODEL:
    - Fixtures are loaded ONLY from workspace/verification/ (read-only to agents)
    - Agents write to workspace/agent_output/ (cannot be executed)
    - This separation prevents write-then-execute attacks
    """

    _RUNNER_CODE = r"""
import json
import os
import sys
import socket
import importlib.util
import traceback


def _disable_network():
    def _blocked(*args, **kwargs):
        raise RuntimeError("Network access disabled in verification subprocess")
    socket.create_connection = _blocked
    base_socket = socket.socket
    class GuardedSocket(base_socket):
        def connect(self, *args, **kwargs):
            raise RuntimeError("Network access disabled in verification subprocess")
        def connect_ex(self, *args, **kwargs):
            raise RuntimeError("Network access disabled in verification subprocess")
    socket.socket = GuardedSocket


def _apply_limits():
    try:
        import resource
        cpu_sec = int(os.getenv("ORKET_VERIFY_CPU_SEC", "2"))
        mem_mb = int(os.getenv("ORKET_VERIFY_MEM_MB", "256"))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_sec, cpu_sec))
        mem_bytes = mem_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    except (ImportError, OSError, ValueError, AttributeError):
        # Best effort on non-posix platforms.
        pass


def main():
    _disable_network()
    _apply_limits()

    payload = json.loads(sys.stdin.read())
    fixture_path = payload["fixture_path"]
    scenarios = payload.get("scenarios", [])
    response = {"ok": True, "results": [], "fatal_error": None}

    try:
        spec = importlib.util.spec_from_file_location("verification_fixture_subprocess", fixture_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except (FileNotFoundError, ImportError, AttributeError, OSError, SyntaxError, ValueError, TypeError) as exc:
        response["ok"] = False
        response["fatal_error"] = f"{type(exc).__name__}: {exc}"
        response["traceback"] = traceback.format_exc()
        print(json.dumps(response))
        return

    for sc in scenarios:
        scenario_id = sc["id"]
        input_data = sc.get("input_data")
        expected_output = sc.get("expected_output")
        verify_fn = getattr(module, f"verify_{scenario_id}", None) or getattr(module, "verify", None)
        result = {
            "id": scenario_id,
            "expected_output": expected_output,
            "actual_output": None,
            "status": "fail",
            "error": None,
        }
        if verify_fn is None:
            result["error"] = f"No verify function found for scenario {scenario_id}"
            response["results"].append(result)
            continue

        try:
            actual = verify_fn(input_data)
            result["actual_output"] = actual
            result["status"] = "pass" if actual == expected_output else "fail"
        except (RuntimeError, ValueError, TypeError, AssertionError, OSError) as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        response["results"].append(result)

    print(json.dumps(response))


if __name__ == "__main__":
    main()
"""

    @staticmethod
    def verify(verification: IssueVerification, workspace_root: Path) -> VerificationResult:
        """Execute verification logic for an issue."""
        logs = []
        passed = 0
        failed = 0
        now = datetime.now(UTC).isoformat()

        logs.append(f"--- Verification Started at {now} ---")

        if not verification.fixture_path:
            logs.append("No verification fixture defined. Skipping empirical tests.")
            return VerificationResult(
                timestamp=now,
                total_scenarios=len(verification.scenarios),
                passed=0, failed=0, logs=logs
            )

        # SECURITY: Resolve fixture path and validate it's in the verification directory
        fixture_path = (workspace_root / verification.fixture_path).resolve()
        verification_root = (workspace_root / VERIFICATION_DIR).resolve()

        try:
            fixture_path.relative_to(verification_root)
        except ValueError:
            msg = (
                f"SECURITY VIOLATION: Fixture path '{verification.fixture_path}' "
                f"is outside the verification directory '{VERIFICATION_DIR}/'. "
                f"Agents cannot execute code from arbitrary locations."
            )
            logs.append(msg)
            log_event("verification_security_violation", {
                "fixture_path": str(fixture_path),
                "verification_root": str(verification_root),
            }, workspace_root)
            raise VerificationSecurityError(msg)

        if not fixture_path.exists():
            logs.append(f"ERROR: Fixture file not found at {fixture_path}")
            return VerificationResult(
                timestamp=now,
                total_scenarios=len(verification.scenarios),
                passed=0, failed=failed, logs=logs
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
                [sys.executable, "-I", "-c", VerificationEngine._RUNNER_CODE],
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
            else:
                try:
                    parsed = json.loads(result.stdout or "{}")
                except json.JSONDecodeError as exc:
                    parsed = {"ok": False, "fatal_error": f"Invalid subprocess JSON output: {exc}", "results": []}

                if not parsed.get("ok", False):
                    logs.append(f"FATAL ERROR loading fixture: {parsed.get('fatal_error', 'unknown')}")
                    if parsed.get("traceback"):
                        logs.append(parsed["traceback"])
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
            for scenario in verification.scenarios:
                scenario.status = "fail"
            failed = len(verification.scenarios)
        except VerificationSecurityError:
            raise
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as e:
            logs.append(f"FATAL ERROR loading fixture: {type(e).__name__}: {e}")

        logs.append(f"--- Verification Complete: {passed} Passed, {failed} Failed ---")
        return VerificationResult(
            timestamp=now,
            total_scenarios=len(verification.scenarios),
            passed=passed, failed=failed, logs=logs
        )

    @staticmethod
    async def verify_sandbox(sandbox: Any, verification: IssueVerification) -> VerificationResult:
        """
        Executes verification against a running sandbox.
        Checks HTTP endpoints and expected responses.
        """
        import httpx
        logs = []
        passed = 0
        failed = 0
        now = datetime.now(UTC).isoformat()

        logs.append(f"--- Sandbox Verification Started for {sandbox.id} at {now} ---")
        logs.append(f"Target URL: {sandbox.api_url}")

        async with httpx.AsyncClient(timeout=10.0) as client:
            for scenario in verification.scenarios:
                # Only process scenarios with 'endpoint' defined
                endpoint = scenario.input_data.get("endpoint")
                if not endpoint:
                    continue

                logs.append(f"Testing Endpoint: {endpoint}")
                url = f"{sandbox.api_url}{endpoint}"
                method = scenario.input_data.get("method", "GET").upper()

                try:
                    res = await client.request(
                        method, url, 
                        json=scenario.input_data.get("payload")
                    )
                    
                    actual = res.json() if "application/json" in res.headers.get("content-type", "") else res.text
                    scenario.actual_output = actual

                    if res.status_code == scenario.input_data.get("expected_status", 200):
                        # Optional deep comparison of output
                        if scenario.expected_output and actual != scenario.expected_output:
                            logs.append(f"  [FAIL] Status OK, but output mismatch.")
                            scenario.status = "fail"
                            failed += 1
                        else:
                            logs.append(f"  [PASS] Endpoint responded correctly.")
                            scenario.status = "pass"
                            passed += 1
                    else:
                        logs.append(f"  [FAIL] Expected status {scenario.input_data.get('expected_status', 200)}, got {res.status_code}")
                        scenario.status = "fail"
                        failed += 1

                except (httpx.HTTPError, ValueError, TypeError, OSError) as e:
                    logs.append(f"  [ERROR] Request failed: {e}")
                    scenario.status = "fail"
                    failed += 1

        logs.append(f"--- Sandbox Verification Complete: {passed} Passed, {failed} Failed ---")
        return VerificationResult(
            timestamp=now,
            total_scenarios=len(verification.scenarios),
            passed=passed, failed=failed, logs=logs
        )
