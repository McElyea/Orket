# Implementation Plan: Orket Tech Debt Remediation (Review.md)

Last updated: 2026-03-06  
Status: Historical Reference (superseded for active execution)  
Owner: Orket Core

Superseded by cycle execution records:
1. `docs/projects/archive/techdebt/TD03052026/TD03052026-Plan.md`
2. `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`

Closeout note:
1. This document remains as an input/reference from the 2026-03-02 cycle.
2. Non-maintenance execution tracking is closed under TD03052026.
3. Recurring freshness work is now governed only by the recurring maintenance checklist.

## Context

The 2026-03-02 code review scored Orket at 6/10. This plan implements the prescribed fixes from `docs/projects/archive/techdebt/TD03052026/Review.md` in priority order across 3 phases. The goal is to reach 7.5/10 through mechanical cleanup -- no rewrites, no architecture changes.

---

## Phase 1: Critical Findings (CRIT-1 through CRIT-8) + Quick Dead Code Deletion

### 1.1 -- API Path Traversal (CRIT-1)

**Files**: `orket/interfaces/api.py`

Add a `_validate_session_path` helper near the top of the file (after imports). The pattern already exists in the codebase at `orket/decision_nodes/api_runtime_strategy_node.py:156-161` (checks `".." in parts` and `is_relative_to`).

```python
def _validate_session_path(session_id: str) -> Path:
    base = (PROJECT_ROOT / "workspace" / "runs").resolve()
    candidate = (base / session_id).resolve()
    if not candidate.is_relative_to(base):
        raise HTTPException(status_code=400, detail="Invalid session_id")
    return candidate
```

Apply at all 6 call sites:
- Line 651: `resolve_member_metrics_workspace` call
- Line 664: `candidate_files.append`
- Line 774: `_collect_replay_turns`
- Line 1150-1151: `_derive_handoff_edges`
- Line 1203: `_persist_execution_graph_snapshot` (most critical -- this one writes)
- Line 1265: `list_logs`

### 1.2 -- CardConfig Import Crash (CRIT-2)

**File**: `orket/vendors/local.py` line 5

Change:
```python
from orket.schema import RockConfig, EpicConfig, CardConfig
```
To:
```python
from orket.schema import RockConfig, EpicConfig
```
`CardConfig` is imported but never referenced in the file body.

### 1.3 -- Delete alerts.py (CRIT-3)

Delete `orket/domain/alerts.py`. Zero callers confirmed by grep.

### 1.4 -- BugFixPhaseManager Workspace (CRIT-4)

**File**: `orket/domain/bug_fix_phase.py`

Add `workspace: Path = Path(".")` to the constructor (line 82):
```python
def __init__(self, organization_config=None, db=None, workspace: Path = Path(".")):
    ...
    self.workspace = workspace
```

Replace all 3 `log_event` calls (lines 114, 155, 177) to use `self.workspace` instead of `Path(".")`.

Update the one existing test in `tests/application/test_bug_fix_phase_manager.py` to pass a `tmp_path` workspace.

### 1.5 -- WebhookDatabase Lock (CRIT-5)

**File**: `orket/adapters/vcs/webhook_db.py`

Add to `__init__`:
```python
self._lock = asyncio.Lock()
```

Wrap every public async method body with `async with self._lock:`. This matches the pattern used in `AsyncSessionRepository` at `orket/adapters/storage/async_repositories.py`.

Public methods to wrap: `record_review_cycle`, `add_failure_reason`, `get_pr_cycle_count`, `get_failure_reasons`, `update_pr_merge_status`, `get_pr_status_summary`, `get_review_analytics`, `log_webhook_event`.

### 1.6 -- Webhook Engine Lifecycle (CRIT-6)

**File**: `orket/adapters/vcs/gitea_webhook_handlers.py` lines 133-137

Replace fire-and-forget pattern:
```python
engine = OrchestrationEngine(self.handler.workspace)
await engine.cards.update_status(issue_id, CardStatus.CODE_REVIEW)
task = asyncio.create_task(engine.run_card(issue_id))
task.add_done_callback(
    lambda t: t.exception() and log_event(
        "webhook_run_card_error",
        {"issue_id": issue_id, "error": str(t.exception())},
        self.handler.workspace,
    )
)
```

### 1.7 -- Normalize Datetimes in _coerce_datetime (CRIT-7)

**File**: `orket/interfaces/api.py` lines 1025-1031

Add `from datetime import UTC` to the import (line 5 area). Then:
```python
def _coerce_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: '{value}'")
```

### 1.8 -- BugFixPhase.scheduled_end Default (CRIT-8)

**File**: `orket/domain/bug_fix_phase.py` lines 46-47

Remove the `scheduled_end` default_factory. Add a `model_validator` that computes it from `started_at` + `initial_duration_days`:

```python
scheduled_end: Optional[str] = None

@model_validator(mode="after")
def _set_scheduled_end(self) -> "BugFixPhase":
    if self.scheduled_end is None:
        start = datetime.fromisoformat(self.started_at)
        self.scheduled_end = (start + timedelta(days=self.initial_duration_days)).isoformat()
    return self
```

Update the test that constructs `BugFixPhase` directly to verify the computed end.

### 1.9 -- Dead Code Deletion Batch

Delete or clean these in a single pass:

| Action | File |
|---|---|
| Delete file | `orket/domain/alerts.py` (done in 1.3) |
| Delete file | `orket/orchestration/kernel_gateway_proxy.py` |
| Delete 3 methods | `orket/orchestration/engine.py` lines 89-99 (`_resolve_state_backend_mode`, `_validate_state_backend_mode`, `_resolve_gitea_state_pilot_enabled`) |
| Inline calls | `engine.py __init__`: replace `self._resolve_state_backend_mode()` with `self.orchestration_config.resolve_state_backend_mode()` (same for the other two) |
| Update facade | `orket/orchestration/engine_services.py`: `KernelGatewayFacade.__init__` takes `KernelV1Gateway` directly instead of proxy |
| Update engine | `engine.py`: remove proxy construction, pass gateway directly to facade |
| Delete identical wrappers | `orket/interfaces/api.py` lines 91-96: `_resolve_async_method` and `_resolve_sync_method` -- replace 3 call sites with direct `_resolve_method` calls |
| Delete duplicate | `orket/interfaces/api.py` line 1271: local `_record_session_id` inside `list_logs` -- use the module-level one at line 1211 |
| Delete dead method | `orket/adapters/vcs/webhook_db.py:221-231`: `log_webhook_event` (never called) |
| Delete dead class | `orket/adapters/storage/async_repositories.py:165-198`: `AsyncSuccessRepository` (never used) |
| Delete dead stub | `orket/application/services/runtime_verifier.py:137-141`: `_default_commands_for_profile` (always returns `[]`) -- inline `[]` at call site |
| Remove YAGNI fields | `orket/schema.py`: remove `EpicConfig.example_task`, `EpicConfig.handshake_enabled`, `IssueMetrics.path_delta` |

---

## Phase 2: High Findings

### 2.1 -- Fix `session.py` Missing Import (HIGH-4)

**File**: `orket/session.py` line 5

Add `Optional` to the typing import.

### 2.2 -- Fix `run_issue` Return Type (HIGH-5)

**File**: `orket/orchestration/engine.py` line 133

Change `-> List[Dict]` to `-> Dict[str, Any]`.

### 2.3 -- Remove Dead `__getattr__` Entries (HIGH-1 partial)

**Files**:
- `orket/application/workflows/turn_executor.py`: Remove `"_prepare_messages"`, `"_parse_response"`, `"_execute_tools"` from the delegation dict (lines ~86, 87, 90)
- `orket/adapters/storage/gitea_state_adapter.py`: Remove `"_request_response"`, `"_request_json"`, `"_request_response_with_retry"`, `"acquire_lease"` from delegation dict (lines ~62-75)

### 2.4 -- Fix `_sync_patchable_symbols` Call Frequency (HIGH-2)

**File**: `orket/application/workflows/orchestrator.py`

Call `_sync_patchable_symbols()` once in `Orchestrator.__init__` instead of in every method and `__getattr__`. Remove calls from `verify_issue`, `_trigger_sandbox`, `execute_epic`, `_save_checkpoint`, and `__getattr__`.

### 2.5 -- FileSystemTools Lock Leak (HIGH-8)

**File**: `orket/adapters/tools/families/filesystem.py` lines 11-29

Replace class-level `_path_locks` dict with an instance-level `_path_locks` in `__init__`. Add a max size bound (e.g., 1024 entries with LRU eviction via `collections.OrderedDict`). Replace `threading.Lock` guard with `asyncio.Lock`.

### 2.6 -- GiteaVendor Connection Pooling (HIGH-9)

**File**: `orket/vendors/gitea.py`

Add `self._client = httpx.AsyncClient(headers=self.headers, timeout=30.0)` to `__init__`. Replace all 6 `async with httpx.AsyncClient() as client:` blocks with `self._client`. Add an `async def close(self)` method.

### 2.7 -- CoordinatorStore Lock Type (HIGH-10)

**File**: `orket/application/services/coordinator_store.py`

Replace `threading.Lock()` with `asyncio.Lock()`. Convert all methods that use `with self._lock:` to `async def` with `async with self._lock:`. Update callers in `orket/interfaces/coordinator_api.py` to `await` the now-async methods.

### 2.8 -- MemoryStore Search Bound (HIGH-11)

**File**: `orket/services/memory_store.py` lines 56-60

Add `LIMIT` to the SQL query:
```python
cursor = await conn.execute(
    "SELECT * FROM project_memory ORDER BY created_at DESC, id DESC LIMIT ?",
    (limit * 20,)
)
```

### 2.9 -- utils.py Import Side Effect (HIGH-12)

**File**: `orket/utils.py` line 7 area

Move `os.makedirs(LOG_DIR, exist_ok=True)` into a `def ensure_log_dir():` function. Call it from the application startup path (e.g., in `api.py` lifespan or `__main__.py`), not at import time.

### 2.10 -- sessions.py Task Error Handling (HIGH-13)

**File**: `orket/interfaces/routers/sessions.py` line 116

Store task reference and add done-callback:
```python
task = asyncio.create_task(_run_turn())
task.add_done_callback(lambda t: t.exception() and logger.error("turn failed", exc_info=t.exception()))
```

### 2.11 -- AsyncSessionRepository Read Lock (HIGH-14)

**File**: `orket/adapters/storage/async_repositories.py`

Remove `async with self._lock:` from read methods (`get_session`, `get_recent_runs`, `get_session_issues`). Keep the lock on write methods (`start_session`, `finish_session`, `record_session_issue`). Keep the lock on `_ensure_initialized` to prevent migration races.

---

## Phase 3: Medium Findings (Selected High-Impact)

### 3.1 -- Extract `_resolve_bool_flag` (M-1)

**File**: `orket/application/workflows/orchestrator_ops.py` lines 255-313

Replace the 5 identical `_is_X_disabled()` functions with a single helper:
```python
def _resolve_bool_flag(self, env_key: str, org_key: str, default: bool = False) -> bool:
    env_raw = (os.environ.get(env_key) or "").strip().lower()
    if env_raw in {"1", "true", "yes", "on"}:
        return True
    if self.org and isinstance(getattr(self.org, "process_rules", None), dict):
        value = self.org.process_rules.get(org_key)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
    return default
```

### 3.2 -- StreamBus DRY (M-14)

**File**: `orket/interfaces/api.py` lines 403-425

Replace the module-level `stream_bus = StreamBus(StreamBusConfig(...))` with `stream_bus = _build_stream_bus_from_env()`.

### 3.3 -- ToolGate Fixes (HIGH-3)

**File**: `orket/core/policies/tool_gate.py`

- Add `forbidden_file_types: List[str] = Field(default_factory=list)` and `bypass_governance: bool = False` to `OrganizationConfig` in `orket/schema.py`
- Replace phantom `hasattr`/`getattr` checks with direct attribute access
- Change hardcoded `CardType.ISSUE` at line 251 to extract card type from `context.get("card_type", "issue")`
- Move `iDesignValidator` and `ASTValidator` to constructor-injected optional dependencies with lazy imports only as fallback

### 3.4 -- Fix `OrchestrationConfig` Exception Type (M-2)

**File**: `orket/orchestration/orchestration_config.py` lines 40-57

Change `NotImplementedError` to `ValueError`. Delete the redundant first `if` block (lines 42-48).

### 3.5 -- Fix `NoteStore.all()` Reference Leak (M-5)

**File**: `orket/orchestration/notes.py` line 39-40

Change `return self._notes` to `return list(self._notes)`.

### 3.6 -- Fix `EventStream.last()` Return Type (M-32)

**File**: `orket/events.py` line 27

Change `-> Event` to `-> Optional[Event]`. Add `Optional` to imports.

---

## Verification Plan

After each phase, run:
```bash
python -m pytest tests/ --tb=short -q
```
Baseline: 1,300 passed, 9 skipped.

### Phase 1 verification (after critical fixes):
1. All 1,300+ tests still pass
2. Manually verify path traversal fix: `curl localhost:8000/v1/runs/..%2F..%2Fetc/token-summary` returns 400
3. `python -c "from orket.vendors.local import LocalVendor"` succeeds (CRIT-2)
4. `python -c "from orket.domain.alerts import evaluate_alert_conditions"` fails with `ModuleNotFoundError` (CRIT-3)
5. Grep confirms zero `Path(".")` in `bug_fix_phase.py`
6. Grep confirms `self._lock = asyncio.Lock()` in `webhook_db.py`

### Phase 2 verification:
1. All tests still pass
2. `python -c "from orket.session import Session"` succeeds (no NameError)
3. Grep confirms no `_sync_patchable_symbols` calls in method bodies
4. Grep confirms no `kernel_gateway_proxy` imports anywhere

### Phase 3 verification:
1. All tests still pass
2. Grep confirms only 1 `_is_.*_disabled` pattern in `orchestrator_ops.py`
3. Grep confirms `forbidden_file_types` and `bypass_governance` exist in `OrganizationConfig`

### Final check:
```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -5
```
Target: 1,300+ passed, 0 failed.
