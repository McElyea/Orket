import importlib.util
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from orket.schema import IssueConfig, VerificationScenario, VerificationResult

class VerificationEngine:
    """
    The FIT-style execution engine for Orket.
    Loads fixtures, runs scenarios, and produces empirical results.
    """
    
    @staticmethod
    async def verify_issue(workspace: Path, issue: IssueConfig) -> VerificationResult:
        if not issue.verification_fixture:
            return VerificationResult(
                timestamp=datetime.now().isoformat(),
                total_scenarios=0, passed=0, failed=0,
                logs=["No verification fixture defined for this card."]
            )

        fixture_path = workspace / issue.verification_fixture
        if not fixture_path.exists():
            return VerificationResult(
                timestamp=datetime.now().isoformat(),
                total_scenarios=0, passed=0, failed=0,
                logs=[f"Fixture file not found: {fixture_path}"]
            )

        print(f"  [VERIFIER] Running FIT Fixture: {issue.verification_fixture}")
        
        passed_count = 0
        logs = []
        
        # 1. Load the Fixture Module
        try:
            spec = importlib.util.spec_from_file_location("fit_fixture", fixture_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # The fixture must implement a 'verify' function
            if not hasattr(module, 'verify'):
                raise AttributeError("Fixture must implement a 'verify(input_data)' function.")

            # 2. Iterate Scenarios
            for scenario in issue.scenarios:
                try:
                    # Execute Fixture
                    actual = module.verify(scenario.input_data)
                    scenario.actual_output = actual
                    
                    # Comparison Logic (FIT Table Style)
                    if actual == scenario.expected_output:
                        scenario.status = "pass"
                        passed_count += 1
                        logs.append(f"Scenario '{scenario.description}': PASS")
                    else:
                        scenario.status = "fail"
                        logs.append(f"Scenario '{scenario.description}': FAIL (Expected {scenario.expected_output}, got {actual})")
                
                except Exception as e:
                    scenario.status = "fail"
                    logs.append(f"Scenario '{scenario.description}': ERROR ({str(e)})")

        except Exception as e:
            logs.append(f"CRITICAL FIXTURE ERROR: {str(e)}")

        return VerificationResult(
            timestamp=datetime.now().isoformat(),
            total_scenarios=len(issue.scenarios),
            passed=passed_count,
            failed=len(issue.scenarios) - passed_count,
            logs=logs
        )
