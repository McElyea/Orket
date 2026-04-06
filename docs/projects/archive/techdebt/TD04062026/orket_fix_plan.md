# Orket — Fix Plan

Last updated: 2026-04-06
Status: Completed
Owner: Orket Core

> Derived from the brutal code review. Issues are grouped into three waves. Each wave is safe to ship independently and leaves the codebase in a better state than before. Work within a wave can be parallelized; do not start Wave 2 until Wave 1 is merged and green.

---

## Wave 1 — Stop the Bleeding (Critical + Safety)

These are the issues most likely to cause production incidents, data loss, or security problems. Fix all of them before any feature work.

---

### W1-A: Break the Circular Import Cycle
**Issue #1** | `orket/orchestration/engine.py`, `orket/runtime/execution_pipeline.py`

**Goal:** Remove the deferred `from orket.orket import ConfigLoader / ExecutionPipeline` inside `__init__`.

**Steps:**
1. Map the full import cycle using `pydeps` or `importlab` to see exactly what causes it.
2. Extract a `OrketRuntimeContext` dataclass (see W2-A) to cut the cycle at its root.
3. Move `ConfigLoader` to `orket/runtime/config_loader.py` — it likely already lives there; the import in `engine.py` should be updating to the direct path.
4. Delete the lazy `__init__` imports once the cycle is broken.
5. Add an `import orket.orchestration.engine` smoke test to catch future regressions.

**Done when:** `python -c "from orket.orchestration.engine import OrchestrationEngine"` succeeds without deferred imports.

---

### W1-B: Move Auth Check Out of Module Scope
**Issue #4** | `orket/services/auth_service.py`

**Goal:** Stop crashing at import time when `ORKET_AUTH_SECRET` is unset.

**Steps:**
1. Remove the module-level `raise`.
2. Replace `SECRET_KEY = os.getenv(...)` with `SECRET_KEY: str | None = None`.
3. Create `def get_secret_key() -> str:` that reads, validates, and caches the env var on first call.
4. Update `create_access_token` to call `get_secret_key()` internally.
5. Add a unit test that imports the module without the env var and confirms no exception.

**Done when:** `import orket.services.auth_service` works in a clean environment.

---

### W1-C: Fix Sync I/O in `CommitOrchestrator`
**Issue #3** | `orket/streaming/manager.py`

**Goal:** Remove synchronous `path.write_text()` from async code paths.

**Steps:**
1. Convert `_write_commit_artifact` to `async def _write_commit_artifact(...)`.
2. Replace `path.parent.mkdir(...)` with `await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)`.
3. Replace `path.write_text(...)` with `async with aiofiles.open(path, "w") as f: await f.write(...)`.
4. Propagate the `await` up through `commit()`.
5. Run the streaming tests; check for event-loop-blocked warnings.

**Done when:** No synchronous disk I/O occurs on the async thread in the streaming hot path.

---

### W1-D: Fix `active_tasks` Overwrite Bug
**Issue #7** | `orket/state.py`

**Goal:** Prevent orphaned tasks when a session spawns more than one concurrent operation.

**Steps:**
1. Change `active_tasks: Dict[str, asyncio.Task]` to `active_tasks: Dict[str, list[asyncio.Task]]`.
2. Update `add_task` to append to the list.
3. Update `remove_task` to remove a specific task instance (not the whole entry).
4. Update callers in `api.py` that reference `get_task(session_id)` — return the list and handle accordingly.
5. Add a test: start two tasks on the same session, cancel both, confirm both are cancelled.

**Done when:** Two concurrent tasks on the same session ID can both be tracked and cancelled.

---

### W1-E: Fix Settings Thread Safety and Test Isolation
**Issues #5, #6** | `orket/settings.py`

**Goal:** Make settings safe across threads and isolated between test cases.

**Steps:**
1. Replace `_run_async_settings_call` with proper `async`/`await` in all internal helpers. Settings reads are already using `aiofiles`; expose all public functions as `async def`.
2. For legacy sync callers: provide a `load_settings_sync()` helper that explicitly uses `asyncio.run()` only (not the `ThreadPoolExecutor` hack), documented as "call only before the event loop starts."
3. Protect `_ENV_LOADED` with `threading.Lock()`.
4. Add a `clear_settings_cache()` function for test teardown and call it in a pytest autouse fixture.
5. Add a `PYTEST_CURRENT_TEST` guard to `load_user_settings` and `load_user_preferences`.

**Done when:** Running the test suite twice in the same process produces identical results.

---

## Wave 2 — Architecture Cleanup

Fix the structural problems that create ongoing maintenance drag. These require more planning but have no production risk if Wave 1 is complete.

---

### W2-A: Extract `OrketRuntimeContext` (Deduplication)
**Issue #10** | `orket/orchestration/engine.py`, `orket/runtime/execution_pipeline.py`

**Goal:** Eliminate the ~200 lines of near-identical init logic in both classes.

**Steps:**
1. Create `orket/runtime/runtime_context.py` with a `@dataclass class OrketRuntimeContext`.
2. Fields: `workspace`, `department`, `db_path`, `config_root`, `org`, `state_backend_mode`, `run_ledger_mode`, `gitea_state_pilot_enabled`, all repo instances, control plane stack.
3. Add a `@classmethod OrketRuntimeContext.from_env(workspace, department, ...)` factory.
4. Refactor `ExecutionPipeline.__init__` to accept an `OrketRuntimeContext`.
5. Refactor `OrchestrationEngine.__init__` to accept the same context.
6. This also resolves W1-A because the cycle was caused by mutual initialization dependencies.

**Done when:** Both classes have <20 lines of init logic; all repo wiring lives in the context factory.

---

### W2-B: Merge `orket/domain/` into `orket/core/domain/`
**Issue #8** | `orket/domain/`, `orket/core/domain/`

**Goal:** Single source of truth for domain objects.

**Steps:**
1. Audit all imports of `orket.domain.*` vs `orket.core.domain.*` across the codebase (use `grep -r "from orket.domain"` and `from orket.core.domain`).
2. For each file in `orket/domain/`: if a counterpart exists in `orket/core/domain/`, diff them and merge into `orket/core/domain/`.
3. If no counterpart exists, move the file into `orket/core/domain/`.
4. Add re-exports in `orket/domain/__init__.py` with deprecation warnings using `warnings.warn(..., DeprecationWarning)`.
5. Update all import sites to use `orket.core.domain`.
6. In a follow-up PR, delete `orket/domain/` entirely.

**Done when:** `orket/domain/` contains only `__init__.py` with deprecation re-exports.

---

### W2-C: Delete `GiteaStateAdapter.__getattr__`
**Issue #2** | `orket/adapters/storage/gitea_state_adapter.py`

**Goal:** Remove dead code and clarify the true delegation architecture.

**Steps:**
1. Confirm via unit tests that removing `__getattr__` does not break any existing test.
2. Delete the entire `__getattr__` method body.
3. Decide: either keep the duplicate real method definitions (current state, slightly verbose) or replace them with true `__getattr__` delegation by removing the real methods.
4. The cleaner path is to keep real methods and delete the `__getattr__`. Do not implement both patterns simultaneously.

**Done when:** `__getattr__` is deleted; all existing tests pass.

---

### W2-D: Fix Private Function Cross-Module Import
**Issue #9** | `orket/runtime/execution_pipeline.py`

**Steps:**
1. In `orket/application/services/control_plane_workload_catalog.py`, rename `_resolve_cards_control_plane_workload_from_contract` to `resolve_cards_control_plane_workload_from_contract` (remove leading underscore).
2. Add a docstring documenting its contract.
3. Update the import in `execution_pipeline.py`.

**Done when:** No leading-underscore names are imported across module boundaries.

---

### W2-E: Remove Pillow from Core Dependencies
**Issue #14** | `pyproject.toml`

**Steps:**
1. Search for all `from PIL import` and `import PIL` across `orket/` (not `vision/` extras).
2. If Pillow is only used by vision/companion features, move it to `[vision]` or a new `[companion]` extra.
3. If Pillow is used in the core critical path, document exactly why.
4. Update installation docs to mention the extras.

**Done when:** `pip install orket` does not pull in Pillow.

---

## Wave 3 — Quality and Hygiene

These fixes improve long-term maintainability without changing behavior. Schedule during a low-pressure sprint.

---

### W3-A: Expand Ruff Rule Set
**Issue #15** | `pyproject.toml`

Add to `[tool.ruff.lint] select`:
```toml
select = [
    "E", "W", "F",         # existing
    "B",                    # bugbear — real bug patterns
    "I",                    # import sorting
    "UP",                   # pyupgrade
    "SIM",                  # simplify
    "ASYNC",                # async anti-patterns (catches sync I/O in async)
    "PTH",                  # prefer pathlib over os.path
]
```

Fix all newly-reported violations before merging. Expect ~50–200 auto-fixable with `ruff --fix`.

---

### W3-B: Enforce mypy in CI
**Issue #16** | `.gitea/workflows/quality.yml`

Add a mypy step to the quality workflow:
```yaml
- name: Type check
  run: python -m mypy orket/ --ignore-missing-imports
```

Start with `--ignore-missing-imports` to avoid blocking on third-party stubs. Add a `mypy.ini` or expand `[tool.mypy]` in `pyproject.toml` with `exclude` patterns for test fixtures.

---

### W3-C: Redact Gitea Token in Storage Adapter
**Issue #17** | `orket/adapters/storage/gitea_state_adapter.py`

**Steps:**
1. Add a `SecretToken` wrapper: `class SecretToken(str): def __repr__(self): return "SecretToken(***)"`.
2. Store `self._token = SecretToken(token)`.
3. Build the headers dict inside the HTTP client, not on `self`, so it is never a long-lived attribute.

---

### W3-D: Delete Thin Pass-Through Methods in `TurnExecutor`
**Issue #11** | `orket/application/workflows/turn_executor.py`

Go through each private `_method` on `TurnExecutor` that does nothing except delegate to a sub-component. Either:
- Delete the wrapper and have `turn_executor_ops` reference the sub-component directly, or
- Keep the wrapper only if it adds observable value (adapting signatures, logging, metric capture).

Target: reduce `turn_executor.py` by at least 60 lines.

---

### W3-E: Add `[tool.coverage]` and Remove Committed `coverage.json`
**Issue #22** | `pyproject.toml`, `coverage.json`

1. Add to `pyproject.toml`:
   ```toml
   [tool.coverage.run]
   source = ["orket"]
   branch = true
   omit = ["tests/*", "scripts/*", "benchmarks/*"]

   [tool.coverage.report]
   fail_under = 60
   show_missing = true
   ```
2. Add `coverage.json` to `.gitignore`.
3. Delete `coverage.json` from the repository.

---

### W3-F: Protect `PROJECT_ROOT` in `api.py`
**Issue #12** | `orket/interfaces/api.py`

Move `PROJECT_ROOT` resolution into the `lifespan` context manager or into a `create_app(project_root: Path)` factory function. Pass it as a dependency to routers rather than referencing the module global.

---

## Tracking

Closeout status:
1. All Wave 1, Wave 2, and Wave 3 plan items are complete.
2. Structural proof for the cycle was refreshed on 2026-04-06 before archive closeout.
3. Archive authority for this cycle is `docs/projects/archive/techdebt/TD04062026/`.

| ID | Wave | Owner | Status |
|----|------|-------|--------|
| W1-A | 1 | — | `[ ]` |
| W1-B | 1 | — | `[ ]` |
| W1-C | 1 | — | `[ ]` |
| W1-D | 1 | — | `[ ]` |
| W1-E | 1 | — | `[ ]` |
| W2-A | 2 | — | `[ ]` |
| W2-B | 2 | — | `[ ]` |
| W2-C | 2 | — | `[ ]` |
| W2-D | 2 | — | `[ ]` |
| W2-E | 2 | — | `[ ]` |
| W3-A | 3 | — | `[ ]` |
| W3-B | 3 | — | `[ ]` |
| W3-C | 3 | — | `[ ]` |
| W3-D | 3 | — | `[ ]` |
| W3-E | 3 | — | `[ ]` |
| W3-F | 3 | — | `[ ]` |
