from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from orket.schema import IssueVerification, VerificationResult


class SandboxVerifier:
    """Runs verification scenarios against a live sandbox API."""

    async def verify_sandbox(self, sandbox: Any, verification: IssueVerification) -> VerificationResult:
        import httpx

        logs: list[str] = []
        passed = 0
        failed = 0
        now = datetime.now(UTC).isoformat()

        logs.append(f"--- Sandbox Verification Started for {sandbox.id} at {now} ---")
        logs.append(f"Target URL: {sandbox.api_url}")

        async with httpx.AsyncClient(timeout=10.0) as client:
            for scenario in verification.scenarios:
                endpoint = scenario.input_data.get("endpoint")
                if not endpoint:
                    continue

                logs.append(f"Testing Endpoint: {endpoint}")
                url = f"{sandbox.api_url}{endpoint}"
                method = scenario.input_data.get("method", "GET").upper()

                try:
                    res = await client.request(method, url, json=scenario.input_data.get("payload"))
                    actual = res.json() if "application/json" in res.headers.get("content-type", "") else res.text
                    scenario.actual_output = actual

                    if res.status_code == scenario.input_data.get("expected_status", 200):
                        if scenario.expected_output and actual != scenario.expected_output:
                            logs.append("  [FAIL] Status OK, but output mismatch.")
                            scenario.status = "fail"
                            failed += 1
                        else:
                            logs.append("  [PASS] Endpoint responded correctly.")
                            scenario.status = "pass"
                            passed += 1
                    else:
                        logs.append(
                            f"  [FAIL] Expected status {scenario.input_data.get('expected_status', 200)}, got {res.status_code}"
                        )
                        scenario.status = "fail"
                        failed += 1
                except (httpx.HTTPError, ValueError, TypeError, OSError) as exc:
                    logs.append(f"  [ERROR] Request failed: {exc}")
                    scenario.status = "fail"
                    failed += 1

        logs.append(f"--- Sandbox Verification Complete: {passed} Passed, {failed} Failed ---")
        return VerificationResult(
            timestamp=now,
            total_scenarios=len(verification.scenarios),
            passed=passed,
            failed=failed,
            logs=logs,
        )
