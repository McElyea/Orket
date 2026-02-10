# The Orket “Stop Refactoring” Benchmark

## The Goal
To stop the cycle of infinite refactoring and architectural "vibes" by proving the system works in a cold-start, zero-babysitting environment.

## The Sacred Rules
1. **Binary Result**: There is no "almost passed". If any of the 5 criteria fail, the whole test fails.
2. **The 90-Day Freeze**: If this test passes twice in a row, the core architecture is frozen. No renames. No phase redesigns. No new IRs.
3. **Mechanical Fixes Only**: If the test fails, you are only allowed to fix the specific code path that blocked completion. You cannot "refactor the module to be better" in response to a failure.

## How to Run
1. Ensure your local LLM (Ollama/LM Studio) is running.
2. Clear your `workspace/runs/` directory if you want a truly clean look (the script does this automatically per run).
3. Run the referee:
   ```bash
   python tests/benchmark_cold_start.py
   ```

## Criteria for the Human Judge
You are the judge for **Condition 5: Zero Reread**.
After the script finishes, read the terminal output. If you can answer these three questions without opening a single source file in the benchmark workspace:
1. "Would I merge this?"
2. "What broke?"
3. "What's next?"
...then Condition 5 is a **PASS**. If you have to go "check what it actually did", it is a **FAIL**.

## Why We Do This
If Orket cannot survive without you, it is not an agent; it is a complex script. This test proves it is an agent.
