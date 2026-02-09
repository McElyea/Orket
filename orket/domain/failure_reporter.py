import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

class FailureReporter:
    """
    Generates a high-fidelity 'Black Box' report when the engine stalls.
    Helps the McElyea Organization troubleshoot governance failures.
    """
    
    @staticmethod
    def generate_report(workspace: Path, session_id: str, card_id: str, violation: str, transcript: List[Any]):
        report = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "blocked_card": card_id,
            "failure_type": "Governance_Policy_Violation",
            "violation_detail": violation,
            "recommendation": "Manual intervention required. Review the 'All Hands on Deck' turn in orket.log.",
            "last_active_turn": transcript[-1] if transcript else "No turns recorded"
        }
        
        report_path = workspace / f"failure_report_{card_id}.json"
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=4)
        
        print(f"  [REPORT] Failure analysis saved to {report_path}")
        return report_path
