# Program-Level Rewrite: Task 001

This replaces the current method-only task with a runnable program task while keeping deterministic grading.

## Rewritten Prompt (Paste-Ready)

```
Task ID: 001-program
Title: Deterministic Sum CLI Program

Build a runnable Python program that computes the sum of two numbers from CLI input.

Required file layout (inside agent_output/):
- main.py (CLI entrypoint)
- calculator.py (domain logic)
- validators.py (input parsing/validation)
- README.md (how to run, expected output)

Behavior contract:
1. Running `python agent_output/main.py 2 3` prints exactly `5` and exits 0.
2. Running `python agent_output/main.py -1 4` prints exactly `3` and exits 0.
3. Running `python agent_output/main.py 0 0` prints exactly `0` and exits 0.
4. Invalid inputs (missing args, non-numeric args) print one-line deterministic error text to stderr and exit non-zero.
5. Program output must be deterministic across repeated runs (same input -> byte-identical stdout/stderr).

Implementation constraints:
- Python 3.11+.
- Keep domain logic in `calculator.py`; keep parsing/validation in `validators.py`.
- No network calls, randomness, current-time dependence, or external services.
- No third-party dependencies.

Deliverables:
- Working program files listed above.
- report.json and run.log artifacts.
```

## Matching Grading Rubric (100 points)

1. Functional correctness (35 pts): all valid example commands return exact expected stdout and exit code 0.
2. Error handling (20 pts): invalid input paths return deterministic stderr messages and non-zero exit codes.
3. Program structure (20 pts): required multi-file layout exists and responsibilities are separated as specified.
4. Determinism (15 pts): repeated runs produce byte-identical outputs and stable behavior.
5. Runability/docs (10 pts): `README.md` gives accurate run commands that work as written.

Suggested pass threshold: 85/100 and no zero in categories 1-3.

## Suggested Acceptance Contract Shape

```json
{
  "mode": "system",
  "required_artifacts": ["run.log", "report.json"],
  "pass_conditions": [
    "CLI returns expected output for valid cases",
    "CLI returns deterministic error behavior for invalid input",
    "Required artifacts are produced",
    "Task-level checks pass"
  ],
  "determinism_profile": "strict",
  "quality_required_keywords": ["if __name__ == \"__main__\":", "argparse"],
  "quality_forbidden_keywords": [
    "orket.interfaces.cli",
    "run_cli",
    "log_crash",
    "asyncio.run(run_cli())"
  ]
}
```
