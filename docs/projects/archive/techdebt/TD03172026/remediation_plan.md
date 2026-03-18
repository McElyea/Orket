# Remediation Plan — Orket Code Review Findings

Last updated: 2026-03-17
Status: Archived (closeout complete; superseded by standing maintenance)
Cycle ID: TD03172026

> Sequenced for safe, incremental delivery. Each task is self-contained and testable in isolation.
> Prerequisites are noted where one fix unblocks another.
> Read [docs/projects/archive/techdebt/TD03172026/code_review_orket.md](docs/projects/archive/techdebt/TD03172026/code_review_orket.md) to view the code review this document is based on.
---

## Sequencing Overview

```
Phase 1 (Foundation)        Phase 2 (Runtime Safety)     Phase 3 (Confidence)
──────────────────────       ────────────────────────      ─────────────────────
[1] Fix imports / stubs  →   [4] Async settings I/O   →   [7] Coverage floor
[2] Fix context=None     →   [5] Dedup provider env   →   [8] load_env tests
[3] Fix crash handler    →   [6] board.py threading   →   [9] Benchmark signal
                             [10] Swallowed telemetry
```

Issues 11–16 (self-deception, config hygiene) are independent and can be done in any phase.

---

## Phase 1 — Low-Risk, High-Value Fixes

These are contained changes with minimal blast radius. Do these first to build a clean foundation.

---

### Task 1 · Fix mid-module import and hardcoded log level in `utils.py`

**Finding:** #10 (mid-module import), #4 (hardcoded DEBUG level)

**Files:** `orket/utils.py`

**Steps:**

1. Move `from orket.naming import sanitize_name` to the top of the file with the other imports. No logic change.

2. Replace the hardcoded log level with an env-var-driven default:

   ```python
   # Before
   CURRENT_LEVEL = CONSOLE_LEVELS.get("debug", 10)  # adjust as needed

   # After
   def _resolve_log_level() -> int:
       raw = os.getenv("ORKET_LOG_LEVEL", "info").strip().lower()
       return CONSOLE_LEVELS.get(raw, CONSOLE_LEVELS["info"])

   CURRENT_LEVEL = _resolve_log_level()
   ```

3. Audit all callers of `CURRENT_LEVEL` to confirm they still behave correctly when the level is not DEBUG. There should be no behavioral change in production once the env var is absent (defaults to INFO).

**Verification:** `python -m pytest tests/ -q -k utils` passes. Manually confirm `ORKET_LOG_LEVEL=debug python -c "from orket.utils import CURRENT_LEVEL; print(CURRENT_LEVEL)"` returns `10` and `ORKET_LOG_LEVEL=warn` returns `30`.

**Test label:** `unit`

---

### Task 2 · Fix `context=None` type lie in `ToolBox.execute()`

**Finding:** #3

**Files:** `orket/tools.py`

**Steps:**

1. Update the signature and add a guard:

   ```python
   # Before
   async def execute(self, tool_name: str, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
       ...
       return await self.runtime_executor.invoke(tool_fn, args, context=context)

   # After
   async def execute(
       self,
       tool_name: str,
       args: Dict[str, Any],
       context: Optional[Dict[str, Any]] = None,
   ) -> Dict[str, Any]:
       resolved_context = context or {}
       ...
       return await self.runtime_executor.invoke(tool_fn, args, context=resolved_context)
   ```

2. Check the three sync delegation methods (`nominate_card`, `refinement_proposal`, `request_excuse`) for the same `context=None` pattern and apply the same guard.

3. Trace into `ToolRuntimeExecutor.invoke()` to confirm it does not also pass `context` directly to downstream tools without a guard. If it does, fix there too — but do not change the interface, only add a guard.

**Verification:** Existing toolbox tests pass. Add a unit test: `toolbox.execute("some_tool", {}, context=None)` must not raise `TypeError`.

**Test label:** `unit`

---

### Task 3 · Fix crash handler in `main.py`

**Finding:** #5

**Files:** `main.py`

**Steps:**

1. Move `import traceback` to the top of the file.

2. Replace the deferred `from orket.logging import log_crash` with a top-level import wrapped in a safe fallback:

   ```python
   # Top of file
   import traceback
   from orket.logging import log_crash
   ```

3. If `orket.logging` is genuinely not always importable at module load time (e.g., optional deps), use a try/except at import time and fall back to a file-write:

   ```python
   try:
       from orket.logging import log_crash as _log_crash
   except ImportError:
       def _log_crash(exc: Exception, tb: str) -> None:
           try:
               with open("orket_crash.log", "a", encoding="utf-8") as fh:
                   fh.write(f"{tb}\n")
           except OSError:
               pass
   ```

4. Update the except block to use `_log_crash`.

**Verification:** Simulate a crash by monkeypatching the CLI entrypoint to raise. Confirm that `orket_crash.log` is written and `sys.exit(1)` is called without a secondary traceback.

**Test label:** `unit`

---

## Phase 2 — Runtime Safety Fixes

These require more care as they touch async infrastructure and I/O paths.

---

### Task 4 · Replace banned sync I/O in `settings.py`

**Finding:** #1, #2 (related)

**Files:** `orket/settings.py`

This is the highest-priority fix in the entire list. It has two sub-parts.

#### 4a · Fix `_read_json()` and all write paths

Replace each sync `open()` call with async-safe alternatives. Since `settings.py` is also called from sync contexts (CLI startup), you have two options:

**Option A (preferred):** Create `async_read_json()` and `async_save_*()` variants and migrate all async callers to them. Keep the sync variants only for CLI startup (where no event loop is running) and add an assertion:

```python
def _read_json_sync(path: Path) -> Dict[str, Any]:
    # Only safe from non-async context (CLI startup).
    assert not _is_running_in_event_loop(), \
        "_read_json_sync called from async context; use async variant"
    ...

def _is_running_in_event_loop() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False
```

**Option B (faster):** Wrap the sync calls in `asyncio.to_thread()` for the async paths:

```python
async def load_user_settings_async() -> Dict[str, Any]:
    return await asyncio.to_thread(load_user_settings)
```

Option A is safer long-term. Option B is a bridge.

#### 4b · Fix `load_env()` — async context crash risk

```python
# Before (will RuntimeError if called from async context)
fs = AsyncFileTools(Path("."))
for line in fs.read_file_sync(str(ENV_FILE)).splitlines():

# After
def load_env() -> None:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    if not ENV_FILE.exists():
        return
    try:
        # load_env is always called at startup, before the event loop starts.
        # Use direct sync read here intentionally; document the invariant.
        content = ENV_FILE.read_text(encoding="utf-8")  # safe: called pre-loop
    except OSError:
        return
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())
```

Add a comment explicitly asserting that `load_env()` must only be called before the event loop starts, and add a runtime assertion using `_is_running_in_event_loop()` from 4a.

#### 4c · Fix module-level path resolution (finding #2)

Defer `SETTINGS_FILE` and `PREFERENCES_FILE` resolution until first use:

```python
# Before (resolved at import time)
SETTINGS_FILE = resolve_user_settings_path(create_parent=False, migrate_legacy=False)

# After (resolved lazily)
_SETTINGS_FILE: Path | None = None

def _get_settings_file() -> Path:
    global _SETTINGS_FILE
    if _SETTINGS_FILE is None:
        _SETTINGS_FILE = resolve_user_settings_path(create_parent=False, migrate_legacy=False)
    return _SETTINGS_FILE
```

Replace all direct uses of `SETTINGS_FILE` with `_get_settings_file()`. Keep `set_settings_file()` as-is but have it set `_SETTINGS_FILE`.

**Verification:** Run the full test suite. Add a test that calls `load_env()` from inside `asyncio.run()` and confirms it raises `AssertionError` (from the guard), not `RuntimeError`. Add a separate test that calls it before the loop and confirms it parses correctly.

**Test label:** `unit` (4a, 4b), `integration` (confirming server startup with a real `.env` file)

---

### Task 5 · De-duplicate provider env resolution in `local_model_provider.py`

**Finding:** #9

**Files:** `orket/adapters/llm/local_model_provider.py`

**Steps:**

1. Extract a single shared helper at module level:

   ```python
   def _read_provider_env() -> str:
       return str(
           os.getenv("ORKET_LLM_PROVIDER")
           or os.getenv("ORKET_MODEL_PROVIDER")
           or "ollama"
       ).strip().lower()

   def _map_provider_backend(raw: str) -> str:
       if raw in {"openai_compat", "lmstudio"}:
           return "openai_compat"
       return "ollama"

   def _map_provider_name(raw: str) -> str:
       if raw == "lmstudio":
           return "lmstudio"
       if raw == "openai_compat":
           return "openai_compat"
       return "ollama"
   ```

2. Replace `_resolve_provider_backend()` and `_resolve_provider_name()` with single-line calls to the above:

   ```python
   def _resolve_provider_backend(self) -> str:
       return _map_provider_backend(_read_provider_env())

   def _resolve_provider_name(self) -> str:
       return _map_provider_name(_read_provider_env())
   ```

3. Confirm that `_read_provider_env()` is called twice during `__init__` — this is acceptable since it reads env vars (cheap). If you want to avoid that, cache it in `__init__` first.

**Verification:** Existing provider unit tests pass. Add a parameterized test covering all valid and invalid env values for both backend and name resolution.

**Test label:** `unit`

---

### Task 6 · Wrap `get_board_hierarchy()` to unblock the event loop

**Finding:** #8

**Files:** `orket/board.py`

**Steps:**

1. Add an async entry point that offloads the sync work:

   ```python
   async def get_board_hierarchy_async(
       department: str = "core",
       auto_fix: bool = False,
   ) -> Dict[str, Any]:
       return await asyncio.to_thread(get_board_hierarchy, department, auto_fix)
   ```

2. In all API route handlers that currently call `get_board_hierarchy()`, replace with `await get_board_hierarchy_async()`.

3. Do not delete the sync version — it is still valid for CLI and test contexts. Document the sync version as "CLI/test only — blocks the calling thread."

4. In the medium term, convert the internal file loads in `get_board_hierarchy()` to async and eliminate the `asyncio.to_thread()` wrapper. That's a larger refactor; the thread wrapper is the correct minimal fix for now.

**Verification:** Add an integration test that calls the API board endpoint and asserts it returns within a threshold without blocking other concurrent requests.

**Test label:** `integration`

---

### Task 7 · Stop swallowing exceptions silently in `async_dual_write_run_ledger.py`

**Finding:** #6

**Files:** `orket/adapters/storage/async_dual_write_run_ledger.py`

**Steps:**

1. In `_emit()`, replace the silent swallow with a logged warning:

   ```python
   except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as exc:
       # Telemetry sink failure must not crash the caller, but must not be invisible.
       try:
           from orket.logging import log_event
           log_event("WARN", "telemetry_sink_error", {
               "error_type": type(exc).__name__,
               "error": str(exc),
           })
       except Exception:  # noqa: BLE001 - true top-level boundary
           pass
       return
   ```

2. In `_safe_call()`, apply the same treatment — replace the bare emit-on-error with a logged warning before the `return None` fallback.

3. Add a counter or metric emission if the project has an observable counter mechanism. Even a module-level `_sink_failure_count` that tests can inspect is better than nothing.

**Verification:** Add a unit test that injects a broken telemetry sink (raises `RuntimeError`) and asserts that (a) the caller is not interrupted, and (b) the warning is logged.

**Test label:** `unit`

---

### Task 8 · Raise coverage floor to a meaningful threshold

**Finding:** #7

**Files:** `.gitea/workflows/quality.yml` (or equivalent CI config), `pyproject.toml` if coverage config lives there

**Steps:**

1. Run `pytest tests/ --cov=orket --cov-report=term-missing` locally to get the current real baseline. Record it.

2. Set the floor 5 points above the current actual (not 60%). If the actual is 72%, set the floor to 77%. This makes the floor meaningful — it fails when coverage regresses.

3. Add per-module coverage excludes for known untestable or deliberately untested paths (e.g. `# pragma: no cover` on the `__main__` block in `server.py`). Do not use excludes to paper over real gaps.

4. Create a `COVERAGE_DEBT.md` in `docs/internal/` (gitignored) that lists every module currently below 80% and the specific uncovered lines, so the gaps are visible and tracked — even if not yet fixed.

5. Annotate the CI step:

   ```yaml
   - name: Run tests with coverage
     run: pytest tests/ --cov=orket --cov-fail-under=<new_floor>
     # Floor is set 5pts above current baseline. See docs/internal/COVERAGE_DEBT.md.
   ```

**Verification:** The CI step fails if coverage drops below the new floor. A deliberate test deletion causes the check to fail.

**Test label:** `unit` (the coverage infrastructure itself)

---

## Phase 3 — Confidence and Hygiene Fixes

---

### Task 9 · Fix the `load_env()` test blind spot

**Finding:** #14

**Files:** `tests/` (new test file), `orket/settings.py`

**Steps:**

1. Add `tests/unit/test_settings_load_env.py` with the following cases:

   - Happy path: a temp `.env` file with `KEY=VALUE` is parsed and injected into `os.environ`.
   - Comment lines are ignored.
   - Blank lines are ignored.
   - A key already present in `os.environ` is not overwritten (`setdefault` behavior).
   - The function does nothing when `PYTEST_CURRENT_TEST` is set — but this test should **temporarily unset** that env var to exercise the real path, then restore it.

2. To test the real path without permanently removing the pytest guard, use a context manager:

   ```python
   import contextlib

   @contextlib.contextmanager
   def unset_pytest_marker():
       val = os.environ.pop("PYTEST_CURRENT_TEST", None)
       try:
           yield
       finally:
           if val is not None:
               os.environ["PYTEST_CURRENT_TEST"] = val
   ```

3. Confirm all tests pass with the `PYTEST_CURRENT_TEST` guard still in place for the rest of the suite.

**Verification:** The new tests cover the load path. `pytest tests/unit/test_settings_load_env.py -v` passes.

**Test label:** `unit`

---

### Task 10 · Fix false determinism signal in benchmark results

**Finding:** #13

**Files:** Benchmark scoring logic (likely `scripts/benchmarks/check_volatility_boundaries.py` or equivalent), benchmark result JSON generation

**Steps:**

1. Find the code that sets `"deterministic": true`. Locate the condition that computes it.

2. Add a minimum run count guard:

   ```python
   MINIMUM_RUNS_FOR_DETERMINISM_CLAIM = 2

   is_deterministic = (
       result["unique_hashes"] == 1
       and result["run_count"] >= MINIMUM_RUNS_FOR_DETERMINISM_CLAIM
   )
   ```

3. For entries where `run_count == 1`, set `"deterministic": null` or `"deterministic": false` with an explanatory field:

   ```json
   {
     "run_count": 1,
     "unique_hashes": 1,
     "deterministic": null,
     "determinism_note": "single_run_insufficient"
   }
   ```

4. Audit all downstream gates that read `"deterministic": true` and confirm they handle `null` correctly (treat it as not proven, not as false).

5. Update the volatility boundary script to require at least 2 runs before emitting a determinism pass for tier-2 and above tasks.

**Verification:** Re-run the benchmark on a single known task twice and confirm `deterministic: true` only appears when both hashes match. Run once and confirm `deterministic: null`.

**Test label:** `contract` (against the benchmark scoring contract)

---

### Task 11 · Gitignore the pytest live probe directories

**Finding:** #15

**Files:** `.gitignore`

**Steps:**

1. Confirm the probe directories are artifacts, not intentionally versioned fixtures:

   ```
   .pytest_live_runtime_probe/
   .pytest_live_runtime_probe_protocol/
   .pytest_live_runtime_probe_protocol_enforce/
   ```

2. Add the following to `.gitignore`:

   ```
   # Live pytest runtime probe workspaces (generated by acceptance tests)
   .pytest_live_runtime_probe*/
   ```

3. Remove the committed directories from the tree:

   ```bash
   git rm -r --cached .pytest_live_runtime_probe
   git rm -r --cached .pytest_live_runtime_probe_protocol
   git rm -r --cached .pytest_live_runtime_probe_protocol_enforce
   ```

4. Confirm the acceptance tests that generate these directories still work after they're gitignored (they should create them fresh on each run).

**Verification:** After `git rm --cached`, `git status` shows no tracked files in those paths. After running acceptance tests, the directories are recreated locally and `git status` still shows them as untracked.

**Test label:** `end-to-end` (run acceptance suite to confirm probe directories are recreated)

---

### Task 12 · Exclude `.claude/settings.local.json` from the dump script

**Finding:** #16

**Files:** `project_dump.py`

**Steps:**

1. The dump script (`project_dump.py`) apparently does not honor `.gitignore` before including files, or the `.claude/settings.local.json` gitignore rule is evaluated too late. Confirm which:

   ```bash
   git check-ignore -v .claude/settings.local.json
   ```

   If the file is correctly gitignored but the dump script bypasses git, fix the dump script to use `git ls-files` as its file source:

   ```python
   import subprocess
   result = subprocess.run(
       ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
       capture_output=True, text=True
   )
   files = result.stdout.splitlines()
   ```

   This guarantees the dump only includes files git would track, and respects `.gitignore` automatically.

2. If the file was committed by accident, remove it:

   ```bash
   git rm --cached .claude/settings.local.json
   ```

3. Add `.claude/` to `.gitignore` at the directory level rather than just `settings.local.json`:

   ```
   .claude/
   ```

   The only exception would be if `.claude/settings.json` (without `.local`) is intentionally versioned.

**Verification:** Run the dump script and confirm `.claude/settings.local.json` is absent from the output. `git status` shows the file as untracked.

**Test label:** `unit` (add a test to the dump script that asserts gitignored files are excluded)

---

### Task 13 · Clarify `asyncio.Lock` singleton lifecycle in `state.py`

**Finding:** #12

**Steps:**

1. Add an explicit comment to `GlobalState.__init__` explaining the lifecycle assumption:

   ```python
   def __init__(self):
       # Locks are created at module import time. This is safe on Python 3.10+
       # because asyncio.Lock no longer binds to a specific event loop at creation.
       # Invariant: do not replace the running event loop after this object is created.
       # Tests that create a new event loop must also create a fresh GlobalState.
       ...
   ```

2. In test fixtures that reset global state, ensure `runtime_state` is reset:

   ```python
   @pytest.fixture(autouse=True)
   def reset_runtime_state(monkeypatch):
       from orket import state
       monkeypatch.setattr(state, "runtime_state", state.GlobalState())
   ```

3. This is documentation + test hygiene; no code change to the class itself is required unless tests are currently failing due to stale locks.

**Verification:** Confirm `pytest tests/ -q` passes with the autouse fixture in place.

**Test label:** `unit`

---

### Task 14 · Document and tighten the `subprocess.run` rule for test code

**Finding:** #11

**Files:** `AGENTS.md`, `tools/ci/test_sentinel.py`

The cleanest resolution here is to clarify the rule rather than convert the test sentinel.

**Steps:**

1. Add an explicit exception to the AGENTS.md async discipline section:

   ```markdown
   ### Async reachability exemptions
   The following contexts are explicitly exempt from the async-reachable path rules:
   - `tools/ci/` scripts and their test wrappers (these run as standalone subprocesses, never inside the server event loop).
   - `scripts/` tooling that is invoked exclusively from CI or the command line.
   In all other cases, assume async reachability.
   ```

2. If the project decides instead to convert `test_sentinel.py` to use `asyncio.create_subprocess_exec`, do so — but this is a larger change and the documentation fix is equally valid for this use case.

3. Do not do both. Pick one and document the decision.

**Verification:** No code change required if going with option 1. If converting the test, verify all four scenarios still pass.

**Test label:** `unit` (the sentinel test itself verifies this)

---

## Execution Order Summary

| Priority | Task | Finding(s) | Effort | Risk |
|---|---|---|---|---|
| 1 | Task 1 — `utils.py` log level + import | #10, #4 | Small | None |
| 2 | Task 2 — `context=None` lie | #3 | Small | None |
| 3 | Task 3 — Crash handler imports | #5 | Small | None |
| 4 | Task 11 — Gitignore probe dirs | #15 | Trivial | None |
| 5 | Task 12 — Exclude `.claude` from dump | #16 | Trivial | None |
| 6 | Task 14 — Document subprocess exemption | #11 | Trivial | None |
| 7 | Task 5 — Dedup provider env resolution | #9 | Small | Low |
| 8 | Task 7 — Stop swallowing telemetry errors | #6 | Small | Low |
| 9 | Task 13 — Document Lock lifecycle | #12 | Trivial | None |
| 10 | Task 4 — Async settings I/O (all three parts) | #1, #2 | Medium | Medium |
| 11 | Task 6 — `get_board_hierarchy` thread wrapper | #8 | Small | Low |
| 12 | Task 8 — Coverage floor | #7 | Small | None |
| 13 | Task 9 — `load_env` test coverage | #14 | Small | None |
| 14 | Task 10 — Fix false determinism signal | #13 | Medium | Medium |

---

## Definition of Done per Task

A task is complete when:

1. The code change is made and passes `ruff check orket/` with no new violations.
2. At least one test covering the fix exists and is labeled with the correct tier (`unit`, `contract`, `integration`, `end-to-end`).
3. If the fix touches a path listed in `CURRENT_AUTHORITY.md`, that file is updated in the same change.
4. The corresponding finding number is referenced in the commit message (e.g. `fix: resolve context=None type lie in ToolBox.execute [finding-3]`).
5. `python -m pytest -q` passes.

---

## Closeout Status (2026-03-17)

Implemented remediation status:

1. Tasks 1 through 14 have landed with targeted code and test coverage for the findings addressed in this plan.
2. Touched-surface verification is green for the remediation slice, including targeted pytest coverage and targeted `ruff check` on modified runtime files.
3. Repo-wide `ruff check orket/` now passes.
4. `python -m pytest -q` now passes (`2751 passed, 40 skipped`).
5. Task 8 raised the CI coverage floor to `89%` and recorded module debt in `docs/internal/COVERAGE_DEBT.md`.
6. This cycle is complete under the Definition of Done above and is archived to [docs/projects/archive/techdebt/TD03172026/](docs/projects/archive/techdebt/TD03172026/).

Residual recurring-maintenance debt:

1. Measured repo coverage from `python -m pytest tests/ --cov=orket --cov-report=term --cov-fail-under=89 -q` is `83.90%`, below the truthful CI floor of `89%`.
2. The red coverage gate is continuing techdebt maintenance debt and remains tracked in `docs/internal/COVERAGE_DEBT.md`.
3. Because the plan’s Definition of Done is now satisfied, that ongoing coverage debt returns to the standing recurring maintenance lane instead of keeping this finite remediation cycle active.
