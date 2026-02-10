"""
Verification Engine (The 'FIT' Executor)

Runs physical code fixtures to verify Issue completion.

SECURITY: Fixtures are loaded from a READ-ONLY verification directory.
Agents can only write to their workspace, NOT to the verification directory.
This prevents the write-then-execute RCE vulnerability.
"""
import importlib.util
import sys
from pathlib import Path
from datetime import datetime, UTC

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

        try:
            spec = importlib.util.spec_from_file_location("verification_fixture", fixture_path)
            module = importlib.util.module_from_spec(spec)

            # Add ONLY the verification directory to sys.path (not the full workspace)
            sys.path.insert(0, str(verification_root))
            spec.loader.exec_module(module)

            for scenario in verification.scenarios:
                logs.append(f"Running Scenario: {scenario.description}")
                verify_fn = getattr(module, f"verify_{scenario.id}", None) or getattr(module, "verify", None)

                if not verify_fn:
                    logs.append(f"  [FAIL] No verify function found for scenario {scenario.id}")
                    scenario.status = "fail"
                    failed += 1
                    continue

                try:
                    actual = verify_fn(scenario.input_data)
                    scenario.actual_output = actual
                    if actual == scenario.expected_output:
                        logs.append(f"  [PASS] Actual matches Expected: {actual}")
                        scenario.status = "pass"
                        passed += 1
                    else:
                        logs.append(f"  [FAIL] Expected {scenario.expected_output}, got {actual}")
                        scenario.status = "fail"
                        failed += 1
                except Exception as e:
                    logs.append(f"  [ERROR] Execution error: {type(e).__name__}: {e}")
                    scenario.status = "fail"
                    failed += 1

        except VerificationSecurityError:
            raise
        except ImportError as e:
            logs.append(f"FATAL ERROR loading fixture (import): {e}")
        except SyntaxError as e:
            logs.append(f"FATAL ERROR loading fixture (syntax): {e}")
        except Exception as e:
            logs.append(f"FATAL ERROR loading fixture: {type(e).__name__}: {e}")
        finally:
            if str(verification_root) in sys.path:
                sys.path.remove(str(verification_root))

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

                except Exception as e:
                    logs.append(f"  [ERROR] Request failed: {e}")
                    scenario.status = "fail"
                    failed += 1

        logs.append(f"--- Sandbox Verification Complete: {passed} Passed, {failed} Failed ---")
        return VerificationResult(
            timestamp=now,
            total_scenarios=len(verification.scenarios),
            passed=passed, failed=failed, logs=logs
        )
