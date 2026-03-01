# Tech Debt Implementation Plan

Last updated: 2026-02-28
Source: `01-REQUIREMENTS.md`

## Strategy

Fix in severity order. Security first, correctness second, tests third, structural last. Each phase is independently shippable -- no phase depends on a later phase completing.

Do not block SDK or Meta Breaker work for structural cleanup. Security and correctness fixes should be done opportunistically when touching nearby code, or in focused sprints.

---

## Phase 1: Security Fixes

Status: **in progress**
Priority: **do first -- these are real vulnerabilities**
Estimated scope: ~2 hours focused work

### Tasks

| ID | Task | File(s) | Status |
|---|---|---|---|
| TD-SEC-1a | Replace shell=True in scaffold_init.py | `orket/interfaces/scaffold_init.py` | complete |
| TD-SEC-1b | Replace shell=True in refactor_transaction.py | `orket/interfaces/refactor_transaction.py` | complete |
| TD-SEC-1c | Replace shell=True in api_generation.py | `orket/interfaces/api_generation.py` | complete |
| TD-SEC-1d | Audit scripts for shell=True (keep if hardcoded, fix if parameterized) | `scripts/` | pending |
| TD-SEC-2 | Add asyncio.Lock to GlobalState.interventions | `orket/state.py` | complete |
| TD-SEC-3a | Delete filesystem.py | `orket/adapters/storage/filesystem.py` | pending |
| TD-SEC-3b | Delete conductor.py | find and delete | pending |
| TD-SEC-3c | Delete persistence.py | find and delete | pending |
| TD-SEC-3d | Delete CardRepositoryAdapter | find and delete | pending |
| TD-SEC-3e | Fix policy.py imports after filesystem.py deletion | `orket/core/policies/policy.py` | pending |

Exit criteria:
- Zero `shell=True` in production code with user-controlled input
- All mutable shared state in GlobalState is lock-protected
- Dead code with known vulnerabilities deleted
- All tests pass

### Verification

```bash
# Confirm no shell=True in production code
grep -r "shell=True" orket/ --include="*.py"

# Confirm deleted files are gone
test ! -f orket/adapters/storage/filesystem.py

# Run tests
python -m pytest tests -q
```

Progress update (2026-03-01):
- Completed `TD-SEC-1a/b/c` by removing `shell=True` from:
  - `orket/interfaces/scaffold_init.py`
  - `orket/interfaces/refactor_transaction.py`
  - `orket/interfaces/api_generation.py`
- Replaced shell execution with explicit argv parsing (`shlex.split(..., posix=True)`) and direct `subprocess.run(argv, shell=False)`
- Validation:
  - `python -m pytest -q tests/interfaces/test_scaffold_init_cli.py tests/interfaces/test_refactor_transaction_cli.py tests/interfaces/test_api_add_transaction_cli.py tests/interfaces/test_replay_artifact_recording.py`
  - result: `16 passed`
- Completed `TD-SEC-2` by exposing lock-protected intervention APIs on `GlobalState`:
  - `set_intervention`, `get_intervention`, `remove_intervention`, `get_interventions`
  - all methods guard shared intervention state via `_interventions_lock`
- Added coverage:
  - `tests/application/test_runtime_state_interventions.py`
  - validation run included API state lifecycle tests (`92 passed` in combined run)

---

## Phase 2: Async Correctness

Status: **not started**
Priority: **fix when touching async code, or in next focused sprint**
Estimated scope: ~1 hour

### Tasks

| ID | Task | File(s) | Status |
|---|---|---|---|
| TD-ASYNC-1 | Replace time.sleep() with await asyncio.sleep() | `orket/adapters/execution/worker_client.py:139` | pending |
| TD-ASYNC-2 | Document or eliminate nested event loop workaround | `orket/adapters/storage/async_file_tools.py:29-36` | pending |

Exit criteria:
- Zero blocking `time.sleep()` in async functions
- Nested event loop pattern documented or removed

### Verification

```bash
# Find blocking sleep in async code
grep -rn "time\.sleep" orket/ --include="*.py"

# Run tests
python -m pytest tests -q
```

---

## Phase 3: Exception Narrowing

Status: **not started**
Priority: **fix opportunistically when touching files, or in focused sprint**
Estimated scope: ~2-3 hours (15 instances, each needs investigation)

### Tasks

| ID | Task | File(s) | Status |
|---|---|---|---|
| TD-EXC-1a | Narrow 4 broad catches in gitea_state_adapter | `orket/adapters/storage/gitea_state_adapter.py` | pending |
| TD-EXC-1b | Narrow 8 broad catches in orket_sentinel | `orket/tools/ci/orket_sentinel.py` | pending |
| TD-EXC-1c | Narrow 1 broad catch in main | `orket/main.py` | pending |
| TD-EXC-1d | Sweep remaining except Exception catches | grep across codebase | pending |

Approach for each instance:
1. Read the try block
2. Identify what exceptions it can actually raise
3. Replace `except Exception` with specific types
4. If genuinely unknown, add logging before the catch

Exit criteria:
- Zero bare `except Exception` in production code
- Each catch names specific exception types

### Verification

```bash
# Count remaining broad catches
grep -rn "except Exception" orket/ --include="*.py" | wc -l
# Target: 0
```

---

## Phase 4: Test Coverage

Status: **not started**
Priority: **write tests when modifying the module, or in focused test sprint**
Estimated scope: ~4-6 hours total

### Tasks

| ID | Task | Target Tests | Status |
|---|---|---|---|
| TD-TEST-1 | Webhook handler tests | 8+ tests: PR cycles, escalation, auto-merge/reject, sandbox trigger | pending |
| TD-TEST-2 | Sandbox orchestrator tests | 6+ tests: Compose generation (3 stacks), port allocation, password gen | pending |
| TD-TEST-3 | API concurrency tests | 5+ tests: concurrent requests, WebSocket isolation, session cleanup | pending |
| TD-TEST-4 | Verification path security test | 2 tests: valid path, malicious path | pending |
| TD-TEST-5 | Driver tests | 10+ tests: command routing, errors, edge cases | pending |

Exit criteria:
- Each module listed above has meaningful test coverage
- All new tests pass
- No existing tests broken

---

## Phase 5: Structural Simplification

Status: **not started**
Priority: **lowest -- do only when it directly supports SDK or Meta Breaker work**
Estimated scope: ~4-6 hours total

### Tasks

| ID | Task | Status |
|---|---|---|
| TD-STRUCT-1 | Split driver.py into CommandParser + ResourceManager + DriverShell | pending |
| TD-STRUCT-2 | Inline trivial decision node methods in DefaultApiRuntimeStrategyNode | pending |
| TD-STRUCT-3 | Write mental model guide for contributors | pending |

Exit criteria:
- Driver path has no single file > 400 lines
- builtins.py reduced by ~200 lines
- Mental model guide exists and is accurate

---

## Ordering and Dependencies

```
Phase 1 (Security)     -- do first, no dependencies
    |
Phase 2 (Async)        -- independent, can parallel with Phase 1
    |
Phase 3 (Exceptions)   -- independent, can parallel
    |
Phase 4 (Tests)        -- best done after Phase 1-3 so tests cover fixed code
    |
Phase 5 (Structural)   -- lowest priority, do when it supports other work
```

Phases 1-3 can be done in any order or in parallel. Phase 4 benefits from doing 1-3 first. Phase 5 is optional and should only be done when it directly unblocks SDK or Meta Breaker.

---

## Integration with Roadmap

This project does NOT block:
- SDK Phase 1 (package bootstrap)
- Meta Breaker route development
- Reforger expansion

This project SHOULD be prioritized when:
- Touching a file that has a security fix pending (do the fix in the same PR)
- Writing tests for a module (add the missing tests at the same time)
- A bug surfaces that traces to a broad exception catch (fix the catch)

Rule: Fix debt when you're already in the neighborhood. Don't make special trips unless it's security.
