# Orket Code Review -- 2026-03-02

**Reviewer**: Claude Opus 4.6 (4 parallel audit agents + manual verification)
**Scope**: Full codebase -- 293 source files, 309 test files, ~42,000 lines
**Baseline**: 1,300 tests passing, 9 skipped, 74s runtime
**Branch**: main @ `601e809`

---

## Executive Summary

### Scores

| Dimension | Previous (Feb 10) | Current (Mar 2) | Delta |
|---|---|---|---|
| Architecture / Conceptual Design | 8/10 | 8/10 | -- |
| Implementation Quality | 5/10 | 6/10 | +1 |
| Security | 3/10 | 5/10 | +2 |
| Test Quality | 4/10 | 5/10 | +1 |
| Code Hygiene (DRY/YAGNI/dead code) | 4/10 | 5/10 | +1 |
| **Overall** | **5/10** | **6/10** | **+1** |

### Verdict

Measurable progress. The reconstruction is working. The datetime.now() plague is eradicated. The old dead modules (filesystem.py, conductor.py, persistence.py) are gone. aiosqlite migration is complete. Blocking `requests.post` replaced with httpx. Test count jumped from 67 to 1,300. These are real wins.

But cleaning revealed new problems, as you predicted. The path traversal in the API layer is the most urgent. Several "thin wrapper" classes add indirection without value. The `__getattr__` delegation pattern is used in 4+ classes and creates dead code in every one. And there are still ~15 files that exist purely as stubs or dead code.

The honest path to 7/10: fix the 8 critical findings below, delete the ~15 dead files/stubs, and collapse the passthrough layers. That is roughly one focused week of unglamorous cleanup.

---

## What Was Fixed Since Last Review (Credit Where Due)

These items from the Feb 10 review are resolved:

| Item | Status |
|---|---|
| 16x `datetime.now()` without timezone | **FIXED** -- Zero occurrences remain. All use `datetime.now(UTC)`. |
| Delete filesystem.py, conductor.py, persistence.py | **FIXED** -- All three are gone. |
| `requests.post` blocking call | **FIXED** -- Replaced with httpx throughout. |
| `GITEA_ADMIN_PASSWORD` enforcement | **FIXED** -- RuntimeError raised when unset. |
| `ORKET_AUTH_SECRET` enforcement | **FIXED** -- RuntimeError at import time. |
| Sandbox passwords via `secrets.token_urlsafe(32)` | **FIXED** -- sandbox_orchestrator.py uses secrets module. |
| Path traversal via `startswith()` | **FIXED** -- `is_relative_to()` used in ToolGate. |
| `_calculate_weight` typo | **FIXED** |
| aiosqlite migration for repositories | **FIXED** -- Session, Snapshot, Card, PendingGate, Webhook all async. |
| `except Exception` broad catches | **MOSTLY FIXED** -- Down to 2 occurrences in non-critical scripts. |
| Test count (was 67, roadmap claimed 150+) | **FIXED** -- Now 1,300 passing tests. |

This is real, measurable progress. The score increase from 5/10 to 6/10 reflects this work.

---

## Critical Findings (Fix This Week)

### CRIT-1: Path Traversal in API -- `session_id` Used Directly in Filesystem Paths

**File**: `orket/interfaces/api.py` lines 664, 774, 1150, 1203, 1265
**Impact**: An attacker supplying `session_id=../../etc/passwd` traverses out of workspace.

```python
candidate_files.append(PROJECT_ROOT / "workspace" / "runs" / session_id / "orket.log")
```

Python's `Path.__truediv__` does not validate containment. `resolve()` is never called. `is_relative_to()` is never checked. The ToolGate fix from the last review does not protect this code path -- ToolGate guards tool execution, not API route parameters.

**Fix**: Create and apply a sanitizer at all 5 call sites:
```python
def _safe_session_path(base: Path, session_id: str) -> Path:
    p = (base / session_id).resolve()
    if not p.is_relative_to(base.resolve()):
        raise HTTPException(status_code=400, detail="Invalid session_id")
    return p
```

---

### CRIT-2: `orket/vendors/local.py:5` -- Import of Non-Existent `CardConfig` Crashes at Load Time

```python
from orket.schema import RockConfig, EpicConfig, CardConfig  # CardConfig does not exist
```

`CardConfig` is not defined in `orket/schema.py`. The schema has `BaseCardConfig`, `IssueConfig`, `EpicConfig`, `RockConfig`. This is a latent `ImportError` that only avoids triggering because `LocalVendor` is imported lazily via the vendor factory.

**Fix**: Replace `CardConfig` with `IssueConfig`.

---

### CRIT-3: `orket/domain/alerts.py` -- 5-Line Dead Stub, Zero Callers

```python
def evaluate_alert_conditions(alert):
    condition = alert["condition"]
    return "price" in condition and "<" in condition
```

Zero callers. Untyped. References "price" -- copy-pasted from a stock-price tutorial. Has nothing to do with Orket.

**Fix**: Delete the file.

---

### CRIT-4: `orket/domain/bug_fix_phase.py` -- Domain Entity Does I/O with Hardcoded `Path(".")`

Lines 114, 155, 177:
```python
log_event("bug_fix_phase_started", {...}, Path("."))
```

`Path(".")` means "whatever the CWD happens to be." Logs write to a random location. The manager takes no `workspace` parameter. This also applies to `reconciler.py` which hardcodes `Path("workspace/default")`.

**Fix**: Add `workspace: Path` to `BugFixPhaseManager.__init__`. Thread it to all `log_event` calls.

---

### CRIT-5: `WebhookDatabase._ensure_initialized` Has No Lock -- Race Condition

**File**: `orket/adapters/vcs/webhook_db.py` lines 36-100

Unlike `AsyncSessionRepository` and `AsyncSnapshotRepository` (which have `self._lock = asyncio.Lock()`), `WebhookDatabase` has no lock. Two concurrent callers both see `_initialized == False` and both execute the full schema creation block simultaneously.

**Fix**: Add `self._lock = asyncio.Lock()` in `__init__`, guard `_ensure_initialized` with it.

---

### CRIT-6: `PRLifecycleHandler.handle_pr_opened` -- Fire-and-Forget Engine With No Lifecycle

**File**: `orket/adapters/vcs/gitea_webhook_handlers.py` lines 133-138

```python
engine = OrchestrationEngine(self.handler.workspace)
asyncio.create_task(engine.run_card(issue_id))  # no reference stored, exceptions swallowed
```

Engine constructed inside a webhook handler, `create_task()` fired, function returns. Engine never closed. Task exceptions silently dropped. If `OrchestrationEngine` holds DB connections, they leak on every PR event.

**Fix**: Store task reference, add done-callback for error logging, manage engine lifecycle (pass existing engine rather than constructing per webhook).

---

### CRIT-7: `api.py` -- `_coerce_datetime` Returns Naive Datetimes, Comparison With Aware Raises `TypeError`

**File**: `orket/interfaces/api.py` lines 1025-1031, 1295-1300

```python
def _coerce_datetime(value):
    return datetime.fromisoformat(value)  # may or may not be tz-aware
```

If the caller passes a tz-aware ISO string and log records contain naive timestamps (or vice versa), the `<` comparison raises `TypeError: can't compare offset-naive and offset-aware datetimes`, crashing the endpoint with an unhandled 500.

**Fix**: Normalize to UTC in `_coerce_datetime`:
```python
dt = datetime.fromisoformat(value)
if dt.tzinfo is None:
    dt = dt.replace(tzinfo=UTC)
return dt
```

---

### CRIT-8: `BugFixPhase.scheduled_end` Default Ignores `initial_duration_days`

**File**: `orket/domain/bug_fix_phase.py` lines 46-47

```python
started_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
scheduled_end: str = Field(default_factory=lambda: (datetime.now(UTC) + timedelta(days=7)).isoformat())
```

Two separate `datetime.now(UTC)` calls (clock skew). `scheduled_end` hardcodes 7 days regardless of `initial_duration_days`. When instantiated directly (not through `BugFixPhaseManager.start_phase()`), the schedule is wrong.

**Fix**: Remove `scheduled_end` default. Compute it in a `model_validator` from `started_at + initial_duration_days`.

---

## High Findings

### HIGH-1: `__getattr__` Delegation Pattern Creates Dead Code in 4+ Classes

This pattern is used in `TurnExecutor`, `AsyncCardRepository`, `GiteaStateAdapter`, and `Orchestrator`. In every case, the `__getattr__` dict is rebuilt on every call (O(n) per access), and several entries are shadowed by explicitly defined methods (making the dict entries unreachable dead code).

**Affected files**:
- `orket/application/workflows/turn_executor.py` lines 84-132 (5 dead entries)
- `orket/adapters/storage/async_card_repository.py` lines 35-52
- `orket/adapters/storage/gitea_state_adapter.py` lines 60-101 (3 dead entries)
- `orket/application/workflows/orchestrator.py` lines 31-43

**Fix**: Use explicit properties or `__init__`-time assignment. Remove shadowed entries from delegation dicts.

---

### HIGH-2: `_sync_patchable_symbols()` Called on Every `__getattr__` Hit

**File**: `orket/application/workflows/orchestrator.py` lines 88-93

Re-assigns 10 module-level globals on every `__getattr__` call. During epic execution, this fires dozens of times. Also called independently in each explicit method.

**Fix**: Call once at class instantiation or set a dirty flag.

---

### HIGH-3: `ToolGate` Layer Violations

**File**: `orket/core/policies/tool_gate.py`

Three issues in the core policy layer:
1. **Lines 76-78**: Imports from `orket.services` (upward dependency from core into application layer)
2. **Line 251**: `CardType.ISSUE` hardcoded -- never uses actual card type for FSM validation
3. **Lines 98, 247**: `hasattr(self.org, "forbidden_file_types")` and `getattr(self.org, "bypass_governance", False)` -- neither attribute exists on `OrganizationConfig`. The code is permanently dead.

**Fix**: Inject validators as constructor dependencies. Extract card type from context. Remove phantom attribute checks.

---

### HIGH-4: `session.py` -- `Optional` Not Imported (Latent `NameError`)

**File**: `orket/session.py` line 25

```python
from typing import List, Dict, Any  # Optional missing
...
end_time: Optional[str] = None  # NameError at runtime
```

**Fix**: Add `Optional` to the typing import.

---

### HIGH-5: `OrchestrationEngine.run_issue()` Return Type Lie

**File**: `orket/orchestration/engine.py` lines 133-140

`run_issue` is annotated `-> List[Dict]` but delegates to `run_card` which returns `-> Dict[str, Any]`. Callers iterating the result get dict keys, not a list of dicts.

**Fix**: Change annotation to `Dict[str, Any]` or wrap result in a list.

---

### HIGH-6: Three Dead Private Methods on `OrchestrationEngine`

**File**: `orket/orchestration/engine.py` lines 89-99

`_resolve_state_backend_mode`, `_validate_state_backend_mode`, `_resolve_gitea_state_pilot_enabled` -- never called from anywhere.

**Fix**: Delete all three.

---

### HIGH-7: `KernelGatewayProxy` -- Pure Passthrough, Zero Value

**File**: `orket/orchestration/kernel_gateway_proxy.py`

7 methods, every one is `return self.kernel_gateway.method(args)`. No transformation, no logging, no validation. Creates a 3-layer stack: `Engine -> Facade -> Proxy -> KernelV1Gateway`.

**Fix**: Delete the proxy. Have the facade hold `KernelV1Gateway` directly.

---

### HIGH-8: `FileSystemTools._path_locks` -- Unbounded Memory Leak

**File**: `orket/adapters/tools/families/filesystem.py` lines 12-29

Locks added to a class-level dict but never removed. Every unique file path accumulates an `asyncio.Lock` forever.

**Fix**: Use `weakref.WeakValueDictionary` or an LRU cache with fixed upper bound.

---

### HIGH-9: `GiteaVendor` Creates New `httpx.AsyncClient` Per Method Call

**File**: `orket/vendors/gitea.py` lines 31-83

Six methods, each opens and closes a fresh `httpx.AsyncClient()` -- no connection pooling, no timeout, no shared auth config.

**Fix**: Create `self._client` in `__init__`, share across methods, implement `close()`.

---

### HIGH-10: `InMemoryCoordinatorStore` Uses `threading.Lock` in Async Context

**File**: `orket/application/services/coordinator_store.py` line 14

`threading.Lock` is a blocking primitive. In FastAPI's asyncio event loop, it blocks the entire loop thread.

**Fix**: Replace with `asyncio.Lock()`, convert methods to `async def`.

---

### HIGH-11: `MemoryStore.search()` Fetches ALL Rows Into Memory

**File**: `orket/services/memory_store.py` lines 56-77

`fetchall()` with no `LIMIT` pulls every row, then filters in Python. Unbounded memory allocation.

**Fix**: Add `LIMIT` to the query. Push filtering to SQL.

---

### HIGH-12: `utils.py` -- `os.makedirs` at Import Time

**File**: `orket/utils.py` line 51

Creates `logs/` directory as a side effect of importing the module. Contaminates test environments.

**Fix**: Move to an explicit `setup_logging()` function.

---

### HIGH-13: `sessions.py` Router -- Fire-and-Forget `asyncio.create_task`

**File**: `orket/interfaces/routers/sessions.py` line 116

Exceptions inside `_run_turn` after `create_task()` are silently dropped. Client gets 200 but the turn failed.

**Fix**: Add done-callback for error logging. Widen the except clause inside `_run_turn`.

---

### HIGH-14: `AsyncSessionRepository` Lock Serializes Reads

**File**: `orket/adapters/storage/async_repositories.py` lines 43-60

Write lock held for the entire DB operation including reads. SQLite WAL mode supports concurrent readers.

**Fix**: Lock only around writes.

---

---

## Medium Findings

| # | File | Issue |
|---|---|---|
| M-1 | `orchestrator_ops.py:255-313` | 5 identical `_is_X_disabled()` functions -- extract `_resolve_bool_flag()` helper |
| M-2 | `orchestration_config.py:40-57` | `NotImplementedError` for config error (should be `ValueError`) |
| M-3 | `orchestration_config.py:42-48` | Redundant guard condition (first `if` is dead given the second) |
| M-4 | `governance_auditor.py:157-162` | `content.encode("utf-8")` called twice in immediate succession |
| M-5 | `notes.py:39-40` | `all()` returns internal list by reference -- callers can corrupt state |
| M-6 | `models.py:159-253` | `_last_selection_decision` set in 6 identical branches (DRY violation) |
| M-7 | `tool_parser.py:117-130` | Legacy DSL fallback has off-by-one `IndexError` risk |
| M-8 | `organization_loop.py:12-37` | Hardcoded `Path(".")` and `Path("workspace/default")` -- CWD-dependent |
| M-9 | `organization_loop.py:36-37` | New `ExecutionPipeline` constructed on every loop iteration |
| M-10 | `runtime_verifier.py:137-141` | `_default_commands_for_profile()` always returns `[]` -- dead stub |
| M-11 | `preview.py:69-71` | `type("MockProvider", (), {"model": m})` -- fragile anonymous class |
| M-12 | `coordinator_api.py:38-52` | Demo data initialized at module import time -- not production-safe |
| M-13 | `api.py:91-96` | `_resolve_async_method` and `_resolve_sync_method` are identical wrappers |
| M-14 | `api.py:403-425` | `StreamBus` construction duplicated (DRY violation) |
| M-15 | `api.py:1211+1271` | `_record_session_id` defined twice with identical body |
| M-16 | `routers/settings.py:52+166` | `PATCH /settings` and `POST /system/runtime-policy` overlap |
| M-17 | `routers/kernel.py:30-37` | Missing `await` on engine call; no error handling; untyped dicts |
| M-18 | `routers/cards.py:89-144` | Guard history parsed from free-form strings (brittle) |
| M-19 | `webhook_db.py:145-159` | Two DB connections for one logical operation (TOCTOU on cycle_count) |
| M-20 | `vendors/factory.py:18-27` | Silent fallback to `LocalVendor` for unsupported vendor types |
| M-21 | `card_migrations.py:42-51` | Redundant `ALTER TABLE`, `OperationalError` swallowed |
| M-22 | `async_executor_service.py:21-24` | New event loop per sync call; `max_workers=1` serializes I/O |
| M-23 | `local_model_provider.py:86-108` | Re-raise without `from exc` loses traceback |
| M-24 | `schema.py:106,109` | `VerificationScenario.status` is untyped string, should be enum |
| M-25 | `schema.py:145` | `LessonsLearned.sentiment` is free-form string, should be `Literal["positive","negative"]` |
| M-26 | `schema.py:95` | `IssueMetrics.audit_date` is `Optional[str]`, should be typed datetime |
| M-27 | `schema.py:153,155` | `EpicConfig.example_task` and `handshake_enabled` have zero callers (YAGNI) |
| M-28 | `schema.py:98` | `IssueMetrics.path_delta` never read or written (YAGNI) |
| M-29 | `core/domain/workitem_transition.py:88-119` | `system_set_status` bypasses FSM with no audit trail |
| M-30 | `settings.py:34-39` | `load_env()` uses `AsyncFileTools.read_file_sync()` -- use `Path.read_text()` |
| M-31 | `settings.py:12-13` | Global mutable caches without thread safety |
| M-32 | `events.py:27-28` | `last()` returns `None` but annotated `-> Event` |
| M-33 | `core/domain/verification_scope.py:49-55` | `provided_context` and `active_context` silently aliased |
| M-34 | `gitea_artifact_exporter.py:79` | `Dict` used but not imported (latent `NameError`) |
| M-35 | `domain/reconciler.py:107,147` | No `OSError` handling on file writes |

---

## Low Findings

| # | File | Issue |
|---|---|---|
| L-1 | `engine_services.py` | 4 delegation wrappers (`KernelGatewayFacade`, `SandboxManager`, `SessionController`, `CardArchiver`) add no logic |
| L-2 | `guard_agent.py:50-51` | `GuardEvaluator.evaluate_contract()` is a no-op stub |
| L-3 | `orchestrator.py:27-28` | Redundant re-export of `load_user_settings`/`load_user_preferences` |
| L-4 | `discovery.py:116-118` | `print()` in library code (should use `log_event`) |
| L-5 | `hardware.py:11-15` | Module-level mutable VRAM cache, not thread-safe |
| L-6 | `canonical_role_templates.py` vs `prompt_compiler.py:55-83` | Role contracts duplicated in two files |
| L-7 | `engine.py:48-49,72-73` | Deferred imports inside `__init__` (circular import workaround) |
| L-8 | `core/critical_path.py:85-86` | `CriticalPathEngine` is empty inheritance alias |
| L-9 | `guard_rule_catalog.py:8` + `guard_contract.py:9` | `GuardSeverity` type alias defined twice |
| L-10 | `naming.py` | `sanitize_name()` does not strip dangerous filename chars (`/`, `\`, `:`) |
| L-11 | `logging.py:112-120` | Legacy compat branch silently reinterprets positional args |
| L-12 | `core/contracts/repositories.py:22` | `assignee: str = None` should be `Optional[str]` |
| L-13 | `domain/sandbox.py:91` | `PortAllocator` forward reference (defined after `SandboxRegistry`) |
| L-14 | `api.py:1090` | `topo_queue.pop(0)` is O(n), re-sorted every iteration |
| L-15 | `coordinator_api.py:10-22` | `ClaimRequest` and `RenewRequest` are identical models |
| L-16 | `routers/cards.py:76-78` | Dead `return card` branch (Pydantic model always has `model_dump`) |
| L-17 | `adapters/vcs/webhook_db.py:221-231` | `log_webhook_event` defined but never called |
| L-18 | `adapters/storage/async_repositories.py:165-198` | `AsyncSuccessRepository.record_success` never called |
| L-19 | `project_dumper_small.py` | Dev script in wrong package; bare `except Exception` |
| L-20 | `agent_factory.py:23-34` | Factory body is a `pass` stub; gives every agent full tool map |

---

## Test Suite Assessment

### Stats
- **1,300 tests passing**, 9 skipped, 74s
- **309 test files** across 10 directories
- **Unit-to-integration ratio**: ~85% unit / 15% integration
- **Live tests**: 8 (always skipped unless env vars set)

### Test Quality Issues

| # | File | Issue | Severity |
|---|---|---|---|
| T-1 | `test_api.py:53-62` | `test_heartbeat` asserts `status_code in [200, 403]` -- can pass without testing anything | HIGH |
| T-2 | (none -- gap) | No tests for `datetime.now(UTC)` migration verification | HIGH |
| T-3 | (none -- gap) | No tests for security-critical paths (GlobalState locks, SSRF, webhook auth) | HIGH |
| T-4 | `test_parallel_execution.py:131-133` | Wall-clock `assert total_duration < 2.5` -- flaky on loaded machines | MEDIUM |
| T-5 | `test_api.py:12` | Module-level `TestClient` created before monkeypatch runs | MEDIUM |
| T-6 | `test_golden_flow.py:132-136` | Patches `__init__` on `LocalModelProvider` -- extremely broad | MEDIUM |
| T-7 | `test_mock_policy.py` | Lint rule implemented as a test, uses relative `Path("tests")`, misclassified as integration | MEDIUM |
| T-8 | `test_ast_governance.py:3`, `test_tool_gating.py:9` | Import from shim `orket.services.tool_gate` instead of canonical path | MEDIUM |
| T-9 | `test_orket_manifest_contract.py:17` | Relative `Path("tests")` for fixture resolution | MEDIUM |
| T-10 | `tests/utils.py:11-12` | Module-level import of `coordinator_api.app` + `store` creates side effects | MEDIUM |
| T-11 | `benchmark_cold_start.py` | Not a test file, lives in `tests/` | MEDIUM |
| T-12 | `test_memory_rag.py:29-34` | `asyncio.sleep(0.1)` for ordering -- SQLite timestamp is 1s resolution | LOW |
| T-13 | `test_golden_flow.py:53,167` | Uses old org name "Vibe Rail" | LOW |
| T-14 | `test_no_old_namespaces.py:27` | Missing `Agents/` in `IGNORE_DIRS` | LOW |

---

## Security Deep-Dive

### Remaining Vulnerabilities (Priority Order)

| # | Severity | File | Issue |
|---|---|---|---|
| S-1 | CRITICAL | `interfaces/api.py` | Path traversal via `session_id` in 5 endpoints (see CRIT-1) |
| S-2 | HIGH | `core/domain/workitem_transition.py` | `system_set_status` bypasses FSM with no audit trail |
| S-3 | HIGH | `naming.py` | `sanitize_name()` does not strip `/ \ : * ?` -- path injection on Windows |
| S-4 | MEDIUM | `governance_auditor.py:163-171` | Path traversal check uses substring `in`, does not check for `..` |
| S-5 | MEDIUM | `vendors/factory.py` | Silent fallback masks misconfigured vendor |
| S-6 | MEDIUM | `settings.py` | Global mutable caches without synchronization |
| S-7 | LOW | `hardware.py` | VRAM cache reads/writes without lock |

### Resolved Since Last Review

| Issue | Status |
|---|---|
| Path traversal via `startswith()` in filesystem.py | FIXED (file deleted, `is_relative_to()` used) |
| Blocking `requests.post` | FIXED (httpx) |
| `GITEA_ADMIN_PASSWORD` not enforced | FIXED (RuntimeError) |
| Hardcoded sandbox DB passwords | FIXED (secrets.token_urlsafe) |
| `ORKET_AUTH_SECRET` not enforced | FIXED (RuntimeError at import) |

---

## Dead Code Inventory (Delete List)

These files/classes have zero callers and add nothing:

| File / Class | Lines | Reason |
|---|---|---|
| `orket/domain/alerts.py` | 5 | Unrelated stub ("price" in condition) |
| `orket/orchestration/kernel_gateway_proxy.py` | ~50 | Pure passthrough, 7 delegation-only methods |
| `orket/orchestration/engine.py:89-99` | 11 | 3 dead private methods |
| `orket/orchestration/project_dumper_small.py` | ~50 | Dev script in wrong package |
| `orket/adapters/vcs/webhook_db.py:221-231` | 10 | `log_webhook_event` never called |
| `orket/adapters/storage/async_repositories.py:165-198` | 33 | `AsyncSuccessRepository` never used |
| `orket/application/services/runtime_verifier.py:137-141` | 5 | `_default_commands_for_profile` always returns `[]` |
| `orket/application/services/guard_agent.py:50-51` | 2 | `GuardEvaluator` is a no-op |
| `orket/interfaces/coordinator_api.py:38-52` | 15 | Demo data at module import time |
| `orket/interfaces/api.py:91-96` | 6 | `_resolve_async_method`/`_resolve_sync_method` identical wrappers |
| `orket/schema.py:153,155,98` | 3 | `example_task`, `handshake_enabled`, `path_delta` -- zero consumers |
| Dead `__getattr__` entries (4 classes) | ~30 | Shadowed by explicit methods |

**Estimated lines recoverable**: ~220

---

## Architectural Observations

### What Is Working Well

1. **Domain model layer** (`schema.py`, `state_machine.py`, `records.py`) -- Clean Pydantic models, correct FSM with role-based guards. This is the strongest layer.

2. **ToolGate** (`core/policies/tool_gate.py`) -- Despite the layer violations noted above, the actual gating logic is solid. 20/20 tests. Policy enforcement works.

3. **TurnExecutor decomposition** -- Successfully broken out from the old god method into `turn_executor.py`, `turn_executor_ops.py`, `turn_artifact_writer.py`. Clean separation of concerns.

4. **Test infrastructure** -- 1,300 tests in 74s is a strong baseline. The conftest fixtures are well-organized. Test naming is generally descriptive.

5. **Async migration** -- aiosqlite is used consistently. No sync sqlite3 in new code. httpx for HTTP. This was a major undertaking done correctly.

### What Needs Attention

1. **The `__getattr__` delegation anti-pattern** -- Used in 4+ classes, creates dead code in every one, defeats IDE type inference, rebuilds dicts on every access. This is the single most pervasive code smell.

2. **Three-layer passthroughs** -- `Engine -> Facade -> Proxy -> Gateway` for kernel ops. `Engine -> CardArchiver -> AsyncCardRepository` for cards. Each layer adds zero logic. Collapse to direct references.

3. **CWD-dependent paths** -- `Path(".")`, `Path("model")`, `Path("workspace/default")` appear in 8+ files. Every one breaks if the working directory is not the project root. This is the #1 testability problem.

4. **Free-form strings where enums belong** -- `VerificationScenario.status`, `LessonsLearned.sentiment`, `IssueMetrics.audit_date`. These are bugs waiting to happen when someone typos a status string.

5. **orchestrator_ops.py** -- 700+ line module of free functions with implicit `self` parameter. This is "methods moved to a different file" without proper decomposition. Needs real service classes.

---

## Prioritized Action Plan

### Week 1: Critical + Quick Wins (Score Impact: +0.5)

| # | Action | Effort | Files Touched |
|---|---|---|---|
| 1 | Fix API path traversal (CRIT-1) | 30 min | `api.py` |
| 2 | Fix `CardConfig` import crash (CRIT-2) | 5 min | `local.py` |
| 3 | Delete `alerts.py` (CRIT-3) | 2 min | `alerts.py` |
| 4 | Add `workspace` param to `BugFixPhaseManager` (CRIT-4) | 30 min | `bug_fix_phase.py` |
| 5 | Add lock to `WebhookDatabase` (CRIT-5) | 10 min | `webhook_db.py` |
| 6 | Fix engine lifecycle in webhook (CRIT-6) | 30 min | `gitea_webhook_handlers.py` |
| 7 | Normalize datetimes in `_coerce_datetime` (CRIT-7) | 10 min | `api.py` |
| 8 | Fix `BugFixPhase.scheduled_end` default (CRIT-8) | 15 min | `bug_fix_phase.py` |
| 9 | Add `Optional` import to `session.py` (HIGH-4) | 2 min | `session.py` |
| 10 | Delete 3 dead methods on engine (HIGH-6) | 5 min | `engine.py` |
| 11 | Delete `KernelGatewayProxy` (HIGH-7) | 20 min | `kernel_gateway_proxy.py`, `engine_services.py` |
| 12 | Delete all dead code from inventory above | 30 min | ~12 files |

### Week 2: High Findings + Test Gaps (Score Impact: +0.5)

| # | Action | Effort |
|---|---|---|
| 13 | Replace `__getattr__` delegation with explicit properties (4 classes) | 2 hours |
| 14 | Fix `_sync_patchable_symbols` call frequency | 30 min |
| 15 | Fix ToolGate layer violations (inject validators) | 1 hour |
| 16 | Fix `test_heartbeat` to assert 200 unconditionally | 15 min |
| 17 | Add security tests (webhook auth, GlobalState races) | 2 hours |
| 18 | Remove wall-clock assertions from parallel tests | 15 min |
| 19 | Fix `GiteaVendor` connection pooling | 30 min |
| 20 | Replace `threading.Lock` with `asyncio.Lock` in coordinator store | 30 min |
| 21 | Add `LIMIT` to `MemoryStore.search()` | 15 min |

### Week 3-4: Medium Findings + Structural (Score Impact: +0.5)

| # | Action | Effort |
|---|---|---|
| 22 | Extract `_resolve_bool_flag` from 5 duplicate functions | 30 min |
| 23 | Add `VerificationStatus` enum, fix untyped strings | 1 hour |
| 24 | Fix CWD-dependent paths across 8 files | 2 hours |
| 25 | Decompose `orchestrator_ops.py` into service classes | 3 hours |
| 26 | Collapse engine service passthroughs | 1 hour |
| 27 | Fix all M-category findings | 3 hours |

---

## Score Trajectory

| Milestone | Projected Score | What Gets You There |
|---|---|---|
| Current | 6/10 | -- |
| After Week 1 | 6.5/10 | All criticals fixed, dead code deleted |
| After Week 2 | 7/10 | High findings resolved, test gaps filled |
| After Week 3-4 | 7.5/10 | Medium findings, structural cleanup |
| Feature-freeze exit | 8/10 | CWD paths fixed, orchestrator_ops decomposed, all shims deprecated |

The path from 6 to 8 is clear and mechanical. No architectural changes needed. No rewrites. Just the unglamorous cleanup you are already doing.

---

*Review generated 2026-03-02 by Claude Opus 4.6. 4 parallel audit agents examined 293 source files, 309 test files, ~42,000 lines of code. Findings cross-verified against Feb 10 review baseline.*
