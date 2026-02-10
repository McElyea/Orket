import asyncio
import os
import shutil
import uuid
import json
from pathlib import Path
from datetime import datetime, UTC

from orket.orchestration.engine import OrchestrationEngine
from orket.schema import CardStatus
from orket.logging import subscribe_to_events

class ColdStartReferee:
    """
    The Referee for the Orket 'Stop Refactoring' Benchmark.
    Enforces the 'Cold Start Reality Test' rules.
    """

    SACRED_PROMPT = (
        "Create a small but real feature for this repo: "
        "add structured logging to the core execution loop, "
        "include tests, update docs, and open a PR."
    )

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        self.bench_id = f"benchmark_{self.timestamp}"
        self.workspace = root_dir / "workspace" / "runs" / self.bench_id
        self.logs = []
        self.artifacts_detected = []

    def setup_clean_room(self):
        """Rule 1: Fresh environment. No cached context."""
        if self.workspace.exists():
            shutil.rmtree(self.workspace)
        self.workspace.mkdir(parents=True)
        
        # Create minimal defaults (No 'known good' tweaks)
        (self.workspace / "orket.log").write_text("", encoding="utf-8")
        print(f"  [REFEREE] Clean room established: {self.workspace}")

    def on_event(self, event):
        self.logs.append(event)
        if event.get("type") == "turn_complete":
            self.artifacts_detected.append(event.get("issue_id"))

    async def run(self):
        """Rule 4: No manual steering."""
        self.setup_clean_room()
        subscribe_to_events(self.on_event)

        engine = OrchestrationEngine(
            workspace_root=self.workspace,
            db_path=str(self.workspace / "benchmark.db")
        )

        print(f"  [REFEREE] Injecting Sacred Prompt...")
        print(f"  [PROMPT] "{self.SACRED_PROMPT}"")

        # We trigger the engine on the prompt
        # In a real cold start, we use the driver to turn prompt into an epic/issue
        from orket.driver import OrketDriver
        driver = OrketDriver()
        
        start_time = datetime.now(UTC)
        try:
            # We wrap the driver request to simulate a fresh start
            response = await driver.process_request(self.SACRED_PROMPT)
            print(f"  [SYSTEM] Initial response: {response}")
            
            # Now we find the issue/epic it created and run it
            backlog = await engine.cards.get_by_build(f"build-{self.bench_id}")
            if not backlog:
                # If driver didn't create a build, check for recent session
                print("  [REFEREE] No build found. Checking sessions...")
                
            # Simulate the 'Autonomous Execution' loop
            # Note: We expect the system to run until DONE or CatastrophicFailure
            # We don't call run_epic manually to avoid 'hints'.
            
        except Exception as e:
            print(f"  [FAIL] System crashed during cold start: {e}")

        self.evaluate()

    def evaluate(self):
        """Binary Scoring: Non-negotiable Criteria."""
        print("
" + "="*60)
        print("  THE STOP REFACTORING BENCHMARK: SCORECARD")
        print("="*60)

        # 1. Multiple Artifacts
        files = list(self.workspace.rglob("*"))
        has_code = any(f.suffix == ".py" for f in files)
        has_tests = any("test" in f.name for f in files)
        has_docs = any(f.suffix in [".md", ".txt"] for f in files)
        
        p1 = has_code and has_tests and has_docs
        print(f"  [1] Multiple Artifacts:      {'PASS' if p1 else 'FAIL'}")
        if not p1:
            print(f"      Missing: {'code ' if not has_code else ''}{'tests ' if not has_tests else ''}{'docs' if not has_docs else ''}")

        # 2. Separated Reasoning
        # Check if logs contain structured 'thought' or 'reasoning' fields
        has_reasoning = any("reasoning" in str(l).lower() for l in self.logs)
        print(f"  [2] Artifacts Separated:      {'PASS' if has_reasoning else 'FAIL'}")

        # 3. Survival of Partial Failure
        # Check if retry_count > 0 was ever hit
        retries = [l for l in self.logs if l.get("type") == "retry_triggered"]
        p3 = len(retries) > 0
        print(f"  [3] Survives Partial Failure: {'PASS' if p3 else 'FAIL'}")

        # 5. Zero Reread Summary
        print("
  [5] JUDGE CONDITION: Zero Reread Summary")
        print("-" * 40)
        summary_events = [l for l in self.logs if l.get("type") in ["session_end", "catastrophic_failure", "governance_violation"]]
        if summary_events:
            for se in summary_events:
                print(f"      EVENT: {se.get('type')} - {se.get('error', 'Success')}")
        else:
            print("      No terminal events found. System may still be running or hung.")
        
        print("
  DECISION:")
        if p1 and has_reasoning and p3:
            print("  >> RESULT: PASS. Freeze architecture for 90 days.")
        else:
            print("  >> RESULT: FAIL. Fix only the first blocker and rerun.")
        print("="*60)

if __name__ == "__main__":
    ref = ColdStartReferee(Path("."))
    asyncio.run(ref.run())
