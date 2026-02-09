import importlib.util
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from orket.schema import IssueVerification, VerificationScenario, VerificationResult

class VerificationEngine:
    """
    Empirical Verification Service (The 'FIT' Executor).
    Runs physical code fixtures to verify Issue completion.
    """

    @staticmethod
    def verify(verification: IssueVerification, workspace_root: Path) -> VerificationResult:
        """
        Executes the verification logic for an issue.
        """
        logs = []
        passed = 0
        failed = 0
        
        logs.append(f"--- Verification Started at {datetime.now().isoformat()} ---")
        
        if not verification.fixture_path:
            logs.append("No verification fixture defined. Skipping empirical tests.")
            return VerificationResult(
                timestamp=datetime.now().isoformat(),
                total_scenarios=len(verification.scenarios),
                passed=0,
                failed=0,
                logs=logs
            )

        fixture_path = workspace_root / verification.fixture_path
        if not fixture_path.exists():
            logs.append(f"ERROR: Fixture file not found at {fixture_path}")
            return VerificationResult(
                timestamp=datetime.now().isoformat(),
                total_scenarios=len(verification.scenarios),
                passed=0,
                failed=failed,
                logs=logs
            )

        try:
            # 1. Load the fixture as a module
            spec = importlib.util.spec_from_file_location("verification_fixture", fixture_path)
            module = importlib.util.module_from_spec(spec)
            
            # Add workspace to sys.path so the fixture can import local modules
            sys.path.insert(0, str(workspace_root.resolve()))
            spec.loader.exec_module(module)
            
            # 2. Iterate through scenarios
            for scenario in verification.scenarios:
                logs.append(f"Running Scenario: {scenario.description}")
                
                # Fixtures must implement a 'verify' function or a function matching the scenario ID
                verify_fn = getattr(module, f"verify_{scenario.id}", None) or getattr(module, "verify", None)
                
                if not verify_fn:
                    logs.append(f"  [FAIL] No verify function found in fixture for scenario {scenario.id}")
                    scenario.status = "fail"
                    failed += 1
                    continue

                try:
                    # Execute with input data
                    actual = verify_fn(scenario.input_data)
                    scenario.actual_output = actual
                    
                    # Comparison logic (can be simple equality or custom)
                    if actual == scenario.expected_output:
                        logs.append(f"  [PASS] Actual matches Expected: {actual}")
                        scenario.status = "pass"
                        passed += 1
                    else:
                        logs.append(f"  [FAIL] Expected {scenario.expected_output}, got {actual}")
                        scenario.status = "fail"
                        failed += 1
                except Exception as e:
                    logs.append(f"  [ERROR] Execution error: {str(e)}")
                    scenario.status = "fail"
                    failed += 1
                    
        except Exception as e:
            logs.append(f"FATAL ERROR loading fixture: {str(e)}")
        finally:
            if str(workspace_root.resolve()) in sys.path:
                sys.path.remove(str(workspace_root.resolve()))

        logs.append(f"--- Verification Complete: {passed} Passed, {failed} Failed ---")
        
        return VerificationResult(
            timestamp=datetime.now().isoformat(),
            total_scenarios=len(verification.scenarios),
            passed=passed,
            failed=failed,
            logs=logs
        )