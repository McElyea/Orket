# Orket — Brutal Code Review

> Reviewed against the dumped source tree (v0.4.34). Every section below is a real, reproducible problem — not style preference.

---

## 1. Circular Imports Disguised as Lazy Imports (Critical)

**Files:** `orket/orchestration/engine.py`, `orket/runtime/execution_pipeline.py`

Both `OrchestrationEngine.__init__` and `ExecutionPipeline.__init__` contain deferred imports buried inside the constructor body:

```python
# engine.py __init__
from orket.orket import ConfigLoader
...
from orket.orket import ExecutionPipeline
```

This is not a performance optimization — it is a circular-import workaround masquerading as code. The module graph has a cycle that nobody has fixed. Lazy imports inside `__init__` are the Python equivalent of commenting "TODO: fix this properly" but shipping it anyway. The correct fix is to break the cycle via dependency inversion, not to defer it until runtime.

---

## 2. `GiteaStateAdapter.__getattr__` Is Dead Code (Critical)

**File:** `orket/adapters/storage/gitea_state_adapter.py`

The class defines a `__getattr__` dispatch table mapping string names to already-defined instance methods:

```python
def __getattr__(self, name: str) -> Any:
    delegated = {
        "acquire_lease": self.leases.acquire_lease,
        "transition_state": self.transitions.transition_state,
        ...
    }
```

`__getattr__` is only called when normal attribute lookup fails. But every single method in that dispatch table is **also defined as a real method** on the class (e.g., `async def acquire_lease(...)`). The real methods win every time. The `__getattr__` block is never reached. It is dead code that creates a false impression the class has a deliberate delegation architecture when it actually doesn't. Delete it or replace the real methods with a true delegation pattern — not both.

---

## 3. Sync File I/O Blocking the Event Loop (Critical)

**File:** `orket/streaming/manager.py` — `CommitOrchestrator._write_commit_artifact`

```python
@staticmethod
def _write_commit_artifact(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(...), encoding="utf-8")
```

This is called from `async def commit(...)`. A synchronous `path.write_text()` inside an async method blocks the entire event loop for the duration of the disk write. Under any real load this degrades all concurrent sessions. Use `aiofiles` or `asyncio.to_thread(path.write_text, ...)` for all I/O inside async methods.

---

## 4. `auth_service.py` Raises at Import Time (Critical)

**File:** `orket/services/auth_service.py`

```python
SECRET_KEY = os.getenv("ORKET_AUTH_SECRET")
if not SECRET_KEY:
    raise RuntimeError("ORKET_AUTH_SECRET environment variable is not set...")
```

This executes at module import time. Any test, script, or tool that imports *anything* that transitively imports `auth_service` will crash unless the env var is set. This is an anti-pattern. Move the check into a factory function or application startup hook. Failing fast is good; failing at `import` is not.

---

## 5. Settings Cache Is Not Thread-Safe and Leaks Between Tests (High)

**File:** `orket/settings.py`

`_SETTINGS_CACHE`, `_PREFERENCES_CACHE`, and `_ENV_LOADED` are module-level mutable globals. There is no lock protecting `_ENV_LOADED`:

```python
_ENV_LOADED = False

def load_env() -> None:
    if _ENV_LOADED:
        return
    ...
    _ENV_LOADED = True
```

A concurrent caller can pass the guard before the flag is set. More practically, these caches persist across test cases in the same process, causing test pollution — even though the code checks `PYTEST_CURRENT_TEST` in `load_env()`, the settings/preferences caches have no equivalent guard.

---

## 6. `_run_async_settings_call` Is an Anti-Pattern (High)

**File:** `orket/settings.py`

```python
def _run_async_settings_call(awaitable: Any, *, operation: str) -> Any:
    if _is_running_in_event_loop():
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, awaitable).result()
    return asyncio.run(awaitable)
```

When called from an async context, this spawns a `ThreadPoolExecutor`, starts a *new* event loop inside that thread via `asyncio.run()`, and blocks the calling thread waiting for the result. This defeats the entire purpose of async I/O, can deadlock under some schedulers, and adds unnecessary thread overhead for simple file reads. The correct fix is to make all settings functions properly `async` and await them from callers.

---

## 7. `active_tasks` Dict Overwrites on Multiple Tasks per Session (High)

**File:** `orket/state.py`, `orket/interfaces/api.py`

```python
self.active_tasks: Dict[str, asyncio.Task] = {}

async def add_task(self, session_id: str, task: asyncio.Task) -> None:
    async with self._tasks_lock:
        self.active_tasks[session_id] = task
```

The dict maps `session_id → Task`. If a session spawns a second task before the first completes, the reference to the first task is silently overwritten. There is no cancellation of the displaced task, no collection into a list, no error. The first task becomes an orphan — it runs to completion (or fails silently) with no way to observe or cancel it. This should be `Dict[str, List[asyncio.Task]]`.

---

## 8. Two Parallel Domain Modules That Were Never Reconciled (High)

The repository has both `orket/domain/` and `orket/core/domain/`. Both contain overlapping files:

- `orket/domain/state_machine.py` and `orket/core/domain/state_machine.py`
- `orket/domain/records.py` and `orket/core/domain/records.py`
- `orket/domain/sandbox.py` and `orket/core/domain/sandbox_lifecycle.py`

This is the residue of an incomplete modularity refactor. Both modules are imported by production code. There is no single source of truth for domain objects. Adding a field to `state_machine.py` requires asking: "which one?" The old `orket/domain/` package should be migrated into `orket/core/domain/` and deleted.

---

## 9. `_resolve_cards_control_plane_workload_from_contract` Cross-Module Private Import (Medium)

**File:** `orket/runtime/execution_pipeline.py`

```python
from orket.application.services.control_plane_workload_catalog import (
    _resolve_cards_control_plane_workload_from_contract,  # leading underscore = private
    ...
)
```

A module is importing a private function (leading underscore) from another module. This is a broken encapsulation boundary. Either make the function public and document its contract, or move the call site inside `control_plane_workload_catalog` and expose a higher-level public function.

---

## 10. `OrchestrationEngine` and `ExecutionPipeline` Duplicate Construction Logic (Medium)

**Files:** `orket/orchestration/engine.py`, `orket/runtime/execution_pipeline.py`

Both classes independently resolve:

- `db_path` via `resolve_runtime_db_path()`
- `config_root`, `org`, `state_backend_mode`, `run_ledger_mode`, `gitea_state_pilot_enabled`
- All repository objects: `AsyncCardRepository`, `AsyncSessionRepository`, etc.
- The control-plane stack: `AsyncControlPlaneRecordRepository`, `ControlPlanePublicationService`, etc.

This is hundreds of lines of near-identical initialization. If either list of repositories changes, both classes need updating. Extract a `RuntimeContext` or `OrketRuntimeConfig` dataclass that encapsulates this wiring, and construct it once.

---

## 11. `TurnExecutor` Has Extensive Thin Pass-Through Methods (Medium)

**File:** `orket/application/workflows/turn_executor.py`

The class defines ~8 private methods that do nothing except forward to sub-components:

```python
def _write_turn_artifact(self, session_id, issue_id, role_name, ...):
    self.artifact_writer.write_turn_artifact(session_id=session_id, ...)

async def _prepare_messages(self, issue, role, context, system_prompt):
    return await self.message_builder.prepare_messages(issue=issue, ...)
```

These are not adapters (signatures match), not decorators (no wrapping logic), and not abstractions (they expose the exact same interface). They are noise. Callers should reference the sub-components directly, or the delegation should do something. Delete the wrappers.

---

## 12. `PROJECT_ROOT` Resolved at Module Level in `api.py` (Medium)

**File:** `orket/interfaces/api.py`

```python
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
```

This is evaluated at import time and baked into the module's global state. Any tool, test, or deployment that imports `api.py` from a different working directory gets a path relative to the source file location — not the actual project root. It also makes testing in isolation difficult without monkeypatching module-level globals. Pass the project root as a configuration argument to the application factory.

---

## 13. CORS Misconfiguration — No `allow_credentials` (Medium)

**File:** `orket/interfaces/api.py`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)
```

`allow_credentials` is not set (defaults to `False`). If any frontend uses `fetch` with `credentials: 'include'` or the API relies on cookies, preflight requests will be rejected. More critically, CORS with `allow_credentials=True` requires that `allow_origins` be an explicit list — not `["*"]`. The current code may silently fail in browser contexts depending on the resolved `origins` value. This should be explicit and tested.

---

## 14. Pillow Is a Core Dependency (Medium)

**File:** `pyproject.toml`

```toml
dependencies = [
    ...
    "Pillow>=10.0.0,<13.0.0",
]
```

Pillow (~15 MB) is in the base `dependencies`, not in `[vision]` optional extras. A tool described as a "local-first workflow runtime for card-based execution" ships image-processing libraries to every user by default. This inflates install size, increases attack surface, and slows down CI. Move it to an optional extra or remove it if it is not used in the critical path.

---

## 15. Ruff Lint Rules Are Too Narrow (Medium)

**File:** `pyproject.toml`

```toml
[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "E722",   # bare except
]
```

This misses entire categories of bugs and anti-patterns: `B` (flake8-bugbear — catches real bugs like mutable default arguments), `I` (import sorting), `UP` (pyupgrade), `SIM` (simplify), `N` (naming conventions), `PTH` (pathlib over os.path), `ASYNC` (async anti-patterns). The `E722` rule is already covered by `E`, making it a no-op duplicate. Given the codebase has real issues like sync I/O in async paths, `ASYNC` rules would catch several of them automatically.

---

## 16. `mypy` Is Not Enforced in CI (Medium)

**File:** `pyproject.toml`, CI config

`mypy` is listed as a dev dependency with `warn_return_any = true` and `warn_unused_configs = true`, but CI only runs `ruff check`. The mypy step is missing from `.gitea/workflows/quality.yml`. Type annotations are present throughout the codebase but there is no guarantee they are correct. Either run mypy in CI or remove it from dev deps to avoid a false sense of security.

---

## 17. Gitea Token Stored in Plain Dict on `self.headers` (Medium)

**File:** `orket/adapters/storage/gitea_state_adapter.py`

```python
self.headers = {
    "Authorization": f"token {token}",
    ...
}
```

The raw API token is stored as a plain string attribute on the object. Any `repr()`, logging, or serialization of the adapter instance leaks the credential. Use a wrapper type (e.g., `SecretStr` from Pydantic) that redacts the value in `__repr__` and `__str__`.

---

## 18. JWT `ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24` (Low)

**File:** `orket/services/auth_service.py`

Tokens expire after 24 hours. There is no refresh token mechanism. A compromised token is valid for a full day. For an operator-facing API that controls sandboxes and code execution, shorter-lived tokens with a refresh flow are strongly preferred.

---

## 19. `asyncio.create_task` Inside a Done Callback (Low)

**File:** `orket/interfaces/api.py` — `_schedule_async_invocation_task`

```python
def _cleanup(_done_task: asyncio.Task):
    asyncio.create_task(runtime_state.remove_task(session_id))

task.add_done_callback(_cleanup)
```

`asyncio.create_task()` requires a running event loop, which is typically available in a done callback — but there is no guarantee when the callback fires in relation to loop shutdown. If the loop is shutting down when a task completes, `create_task` raises `RuntimeError`. Use `loop.call_soon_threadsafe` or ensure the removal is idempotent and scheduled safely.

---

## 20. `mesh_orchestration/` Package Is an Undocumented Experimental Module (Low)

**Directory:** `mesh_orchestration/`

A `mesh_orchestration/` package at the repository root is included in the install (it matches `include = ["orket*"]` — actually it may not, since `orket*` won't match `mesh_orchestration`). Regardless, the directory exists with `card.py`, `coordinator.py`, `worker.py`, and `run_demo.py`, but it has no tests, no documentation, and its README says it's an experimental concept. If it is not production code, it should not be in the repository root. Move it to `docs/experiments/` or delete it.

---

## 21. `GlobalState` Asyncio Locks Created at Module Import Time (Low)

**File:** `orket/state.py`

```python
self._ws_lock = asyncio.Lock()
self._tasks_lock = asyncio.Lock()
```

The code comment correctly notes this is "safe on Python 3.11" because asyncio locks no longer bind to a running loop at construction time. However, this is version-specific behavior being relied upon without a version guard, and it will silently break if the minimum Python version is ever lowered. The code comment admits the problem but ships it anyway. If this must remain, add a `sys.version_info >= (3, 10)` assertion at module level.

---

## 22. Missing `[tool.coverage]` Configuration (Low)

**File:** `pyproject.toml`

`pytest-cov` is a dev dependency and `coverage.json` exists in the repository, but there is no `[tool.coverage.run]` or `[tool.coverage.report]` section in `pyproject.toml`. Coverage is being collected without exclusions, source mapping, or branch tracking defined. `coverage.json` being committed to the repository means stale coverage data will mislead contributors.

---

## Summary Table

| # | Severity | File(s) | Issue |
|---|----------|---------|-------|
| 1 | Critical | `engine.py`, `execution_pipeline.py` | Circular imports via deferred `__init__` imports |
| 2 | Critical | `gitea_state_adapter.py` | `__getattr__` is dead code — real methods shadow it |
| 3 | Critical | `streaming/manager.py` | Sync file I/O blocking the async event loop |
| 4 | Critical | `auth_service.py` | Module-level `raise` at import time |
| 5 | High | `settings.py` | Cache globals not thread-safe, leak between tests |
| 6 | High | `settings.py` | `ThreadPoolExecutor` + `asyncio.run` anti-pattern |
| 7 | High | `state.py`, `api.py` | One task per session — overwrites, orphans tasks |
| 8 | High | `orket/domain/`, `orket/core/domain/` | Two parallel domain packages, never merged |
| 9 | Medium | `execution_pipeline.py` | Private function imported across module boundary |
| 10 | Medium | `engine.py`, `execution_pipeline.py` | Massive duplicated construction logic |
| 11 | Medium | `turn_executor.py` | Thin pass-through wrapper methods that do nothing |
| 12 | Medium | `api.py` | `PROJECT_ROOT` baked in at import time |
| 13 | Medium | `api.py` | CORS config missing explicit `allow_credentials` |
| 14 | Medium | `pyproject.toml` | Pillow in core dependencies, not optional |
| 15 | Medium | `pyproject.toml` | Ruff lint rules too narrow, missing real-bug catchers |
| 16 | Medium | CI + `pyproject.toml` | `mypy` not enforced in CI |
| 17 | Medium | `gitea_state_adapter.py` | Raw API token stored in plain dict |
| 18 | Low | `auth_service.py` | 24-hour JWT, no refresh mechanism |
| 19 | Low | `api.py` | `create_task` inside a done callback |
| 20 | Low | `mesh_orchestration/` | Experimental package in repository root |
| 21 | Low | `state.py` | asyncio lock creation relies on Python 3.11 behavior |
| 22 | Low | `pyproject.toml` | Missing `[tool.coverage]` configuration |
