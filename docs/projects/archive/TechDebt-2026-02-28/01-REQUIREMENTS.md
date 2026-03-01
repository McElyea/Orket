# Tech Debt Requirements

Source: `docs/internal/ClaudeReview.md` (2026-02-28 audit)
Status: Active

---

## Severity: HIGH (Security)

### TD-SEC-1: Remove shell=True from subprocess calls

6 instances of `subprocess.run(..., shell=True)` that risk RCE if command strings contain unsanitized input.

Files:
- `orket/interfaces/scaffold_init.py:55`
- `orket/interfaces/refactor_transaction.py:36`
- `orket/interfaces/api_generation.py:41`
- `scripts/context_ceiling_finder.py:151`
- `scripts/run_determinism_harness.py:332`
- `scripts/run_quant_sweep.py:419`

Fix: Replace with list-based `subprocess.run()` (no `shell=True`).

Acceptance: Zero instances of `shell=True` in production code. Scripts may keep it if command is fully hardcoded (no user input).

### TD-SEC-2: Add asyncio.Lock to GlobalState.interventions

`state.py` GlobalState has locks on `active_websockets` and `active_tasks` but not on `interventions` dict. Concurrent updates can race.

Fix: Add `self._interventions_lock = asyncio.Lock()` and guard all reads/writes.

Acceptance: All mutable shared state in GlobalState is lock-protected.

### TD-SEC-3: Delete dead code with known vulnerabilities

Files to delete:
- `filesystem.py` (path traversal via `startswith()` -- replaced by `is_relative_to()` in async_file_tools.py)
- `conductor.py` (dead orchestration code)
- `persistence.py` (dead persistence layer)
- `CardRepositoryAdapter` (dead adapter)

Fix: Delete files. Fix any imports that reference them (known: `policy.py` imports `FilesystemPolicy` from `filesystem.py` -- must inline or redirect).

Acceptance: Files deleted. No import errors. All tests pass.

---

## Severity: MEDIUM (Correctness)

### TD-ASYNC-1: Replace blocking time.sleep() in async context

`worker_client.py:139` uses `time.sleep()` which blocks the event loop.

Fix: Replace with `await asyncio.sleep()`.

Acceptance: Zero instances of `time.sleep()` in async functions.

### TD-ASYNC-2: Eliminate nested event loop workaround

`async_file_tools.py:29-36` creates new event loops inside existing ones via ThreadPoolExecutor. Functional but fragile.

Fix: Restructure callers to be fully async, or document the workaround with a clear rationale for why it's necessary.

Acceptance: No `ThreadPoolExecutor` + `asyncio.run()` nesting pattern in production code, OR explicit documented justification.

### TD-EXC-1: Narrow broad exception catches

~15 instances of `except Exception` that swallow everything including security errors.

Known locations:
- `gitea_state_adapter.py` (4 instances)
- `orket_sentinel.py` (8 instances)
- `main.py` (1 instance)
- Others scattered across adapters

Fix: Replace each with specific exception types (ValueError, OSError, RuntimeError, etc.) based on what the try block actually raises.

Acceptance: Zero bare `except Exception` catches in production code. Each catch names the specific exceptions it handles.

---

## Severity: MEDIUM (Test Gaps)

### TD-TEST-1: Webhook handler tests

`gitea_webhook_handler.py` core logic is untested:
- PR review cycle enforcement (cycles 1-4 logic)
- Architect escalation after 3 rejections
- Auto-reject after 4 cycles
- Auto-merge on approval
- Sandbox deployment trigger

Acceptance: At least 8 tests covering the above scenarios.

### TD-TEST-2: Sandbox orchestrator tests

Only 1 test file testing a fake runner interface. Missing:
- Docker Compose file generation validation
- Port allocation uniqueness
- Database password generation verification

Acceptance: At least 6 tests covering Compose generation for each tech stack and port allocation.

### TD-TEST-3: API concurrency tests

Only 11 API tests, mostly checking status codes. Missing:
- Concurrent request handling
- WebSocket broadcast isolation
- Session cleanup on connection drop

Acceptance: At least 5 concurrency-focused tests.

### TD-TEST-4: Verification fixture path security test

The `relative_to()` check in `verification.py:157-174` that prevents agent RCE via fixture injection has zero tests.

Acceptance: At least 2 tests: one valid path, one malicious path (e.g., `../../agent_output/fixture.py`).

### TD-TEST-5: Driver tests

Only 5 tests with basic parsing. Missing complex decision logic, error paths, and command routing.

Acceptance: At least 10 tests covering command routing, error handling, and edge cases.

---

## Severity: LOW (Structural)

### TD-STRUCT-1: Driver decomposition

`driver.py` is 916+ lines doing intent parsing, resource management, CLI routing, model invocation, org loading, and config resolution. God class.

Fix: Extract into focused modules (CommandParser, ResourceManager, DriverShell) without changing external behavior.

Acceptance: No single file > 400 lines in the driver path. All existing driver tests pass.

### TD-STRUCT-2: Decision node simplification

`DefaultApiRuntimeStrategyNode` (~200 lines) contains methods that return constants (`{"status_code": 404}`) or delegate to one-line calls. These add indirection without abstraction.

Fix: Inline trivial methods. Keep the node pattern for genuinely variable decisions (planner, evaluator, router). Remove nodes that exist only for consistency.

Acceptance: `builtins.py` reduced by at least 200 lines. Decision node tests still pass.

### TD-STRUCT-3: Documentation gap -- mental model guide

No "getting started for contributors" guide explaining the relationship between Driver, OrchestrationEngine, ExecutionPipeline, Orchestrator, and TurnExecutor.

Fix: Write a concise guide (not a README, not an architecture doc) explaining the mental model and control flow.

Acceptance: A new contributor can trace a request from CLI input to card completion by reading one document.
