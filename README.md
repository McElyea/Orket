# Orket

Orket is a local-first workflow runtime that executes card-based work with LLM turns, guard checks, and persistent state.

## Current Focus
1. Quantization diagnostics and sweep operations for live/local model runs.
2. Deterministic telemetry contracts and run-validity policy.
3. Guarded workflow execution through state and tool gates.

## Runtime Model

### Card Lifecycle

```text
OPEN -> CLAIMED -> IN_PROGRESS -> REVIEW -> DONE
  |        |           |            |
  |        |           |            +--> BLOCKED (guard/rule failure)
  |        |           +--> FAILED (execution failure)
  |        +--> OPEN (lease/claim released)
  +--> ARCHIVED (operator action)
```

### Turn Execution and Guard Flow

```text
[Planner/Selector]
      |
      v
[Turn Executor] --tool calls--> [Tool Gate] ----deny----> [Violation + Blocked]
      |                              |
      |                              +--allow--> [Action]
      v
[State Transition Request] --> [State Machine Gate] --deny--> [Violation + Blocked]
      |                                  |
      +-------------allow----------------+
                     |
                     v
               [Persist + Emit Telemetry]
```

## Repository Map
1. `orket/core`: contracts, state rules, policy types.
2. `orket/application`: orchestration services and workflow logic.
3. `orket/adapters`: model/storage/tool integrations.
4. `orket/interfaces`: API/CLI surfaces.
5. `scripts/`: operational and benchmark tooling.
6. `benchmarks/`: task banks, runs, and diagnostics artifacts.
7. `docs/`: architecture, security, runbooks, and active roadmap.

## Quick Start
1. Install dependencies:
```bash
pip install -r requirements.txt
```
2. Configure environment:
```bash
cp .env.example .env
```
3. Run the API server:
```bash
python server.py
```

## Documentation
Start with `docs/README.md` for a source-of-truth index.
