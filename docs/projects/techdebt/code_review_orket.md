# Code Review — Orket (v0.4.12)

> Reviewed against the project's own AGENTS.md rules, code discipline section, and stated governance contracts.
> Findings are grouped as **Ship-risk debt**, **Exploration-safe debt**, and **Self-deception debt**, per the project's own review convention.

---

## Ship-Risk Debt

These are issues that can cause silent failures, incorrect behavior in production, or violated contracts at runtime.

### 1. `orket/settings.py` — Banned sync I/O throughout

AGENTS.md §Code Discipline explicitly bans raw `open()` in async-reachable paths. `settings.py` is reachable from the async server runtime and violates this rule in at least three places:

- `_read_json(path)` uses a raw `with path.open(...)` read.
- `save_user_settings()` uses a raw `with settings_path.open("w", ...)` write.
- `save_user_preferences()` does the same.

None of these use `aiofiles` or `AsyncFileTools`. The `AsyncFileTools` class is imported at the top of `settings.py` but is only used in `load_env()` — and even there it uses the blocking sync bridge (`read_file_sync`), which will raise a `RuntimeError` if called from a running event loop. Since `load_env()` can be triggered during server startup (an async context), this is a latent crash, not just a style issue.

**Fix:** Replace raw `open()` calls with `aiofiles` or proper async equivalents. Remove the `_run_async` bridge path from `load_env()`.

---

### 2. `orket/settings.py` — Module-level path resolution at import time

```python
SETTINGS_FILE = resolve_user_settings_path(create_parent=False, migrate_legacy=False)
PREFERENCES_FILE = resolve_user_preferences_path(create_parent=False)
```

These run at import time, before any workspace configuration. In tests or alternate-workspace scenarios this resolves to the wrong path, silently. The `set_settings_file()` escape hatch exists but requires callers to know they need it — an opt-in override for a default that's already wrong is a bug waiting to be forgotten.

---

### 3. `orket/tools.py` — `None` passed as `Dict` at API boundary

```python
async def execute(self, tool_name: str, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
```

The type annotation says `Dict[str, Any]` but the default is `None`. This is a lie the type checker accepts only because `mypy` is run with `--ignore-missing-imports` and the project's mypy config may not be strict. More concretely, `context` is passed directly to `runtime_executor.invoke(tool_fn, args, context=context)` — if `invoke` passes `context` to downstream tools that do `context["key"]`, a `None` default causes a `TypeError` at runtime, not at call site.

**Fix:** `context: Optional[Dict[str, Any]] = None` and add a `resolved_context = context or {}` guard before passing it downstream.

---

### 4. `orket/utils.py` — Log level hardcoded to DEBUG, forever

```python
CURRENT_LEVEL = CONSOLE_LEVELS.get("debug", 10)  # adjust as needed
```

"Adjust as needed" is a comment, not a mechanism. This constant is set to `10` (DEBUG) at module load time and is never wired to any environment variable, config file, or runtime setting. Every deployment runs at DEBUG verbosity. This is a correctness and performance issue in production.

---

### 5. `main.py` — Crash handler can crash itself

```python
except Exception as e:
    print(f"\n[CRITICAL ERROR] Orket CLI crashed: {e}")
    import traceback
    from orket.logging import log_crash
    log_crash(e, traceback.format_exc())
```

`traceback` is deferred into the exception handler rather than imported at the top of the module. More critically, `from orket.logging import log_crash` is also deferred. If `orket.logging` fails to import (broken install, bad `__init__`, circular import during crash), the crash handler itself raises an `ImportError`, swallowing the original exception and printing nothing useful. The `traceback` import is harmless to move up; the `log_crash` deferral is the dangerous one.

---

### 6. `async_dual_write_run_ledger.py` — Silent exception swallowing in `_emit`

```python
except (RuntimeError, ValueError, TypeError, OSError, AttributeError):
    return
```

AGENTS.md §Exceptions and security rule 4: "Never silently swallow exceptions." This telemetry sink eats all of those error types with no log, no counter, and no trace. A broken telemetry path becomes invisible, which defeats the purpose of telemetry in a "truthful runtime." At minimum this should log the error type and a truncated message.

---

### 7. Coverage floor set at 60%

```
pytest tests/ --cov=orket --cov-fail-under=60
```

For a project whose core identity is governed contracts, truthful runtime, and determinism lanes, a 60% coverage floor is structurally inconsistent. The CI can be green while 40% of the runtime goes untested. This is not a style note — it means the governance gates can pass on code that has never been exercised by a test.

---

## Exploration-Safe Debt

These won't typically cause immediate failures but create technical drag, inconsistency, or mask real problems over time.

### 8. `orket/board.py` — Sync blocking inside the async runtime

`get_board_hierarchy()` is a fully synchronous function that drives potentially slow I/O (file loads for rocks, epics, issues) in a loop. It is called from API handlers. Every call blocks the event loop for the duration of all those file reads. This should be either wrapped in `await asyncio.to_thread(...)` or converted to an async function using async I/O.

---

### 9. `local_model_provider.py` — Duplicated env-var resolution logic

`_resolve_provider_backend()` and `_resolve_provider_name()` both independently parse `ORKET_LLM_PROVIDER` and `ORKET_MODEL_PROVIDER` with the same logic. This means they can drift independently. The `lmstudio` → `openai_compat` mapping is present in one and absent from the other in a different form. Extract a single `_parse_provider_env()` helper.

---

### 10. `orket/utils.py` — Mid-module import

```python
CONSOLE_LEVELS = {"debug": 10, ...}
CURRENT_LEVEL = ...

from orket.naming import sanitize_name  # ← here, between module-level statements
```

Imports belong at the top of the file. This one sits between two constant definitions, which means any linter run without `--select=E402` will silently miss it, and anyone reading the file will be surprised to find an import buried in the middle.

---

### 11. `test_sentinel.py` — `subprocess.run()` in test code

```python
proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
```

AGENTS.md §Code Discipline bans `subprocess.run()` and adds "If reachability is ambiguous, assume the path is async-reachable." This is a test file, so it's likely considered non-async, but the rule is written as a blanket ban with the ambiguity clause. The codebase should either explicitly exempt test scripts from this rule (which it currently doesn't) or use `asyncio.create_subprocess_exec`.

---

### 12. `orket/state.py` — Module-level asyncio.Lock() instantiation

```python
runtime_state = GlobalState()
```

`GlobalState.__init__` creates `asyncio.Lock()` instances. In Python ≥ 3.10, locks no longer bind to a running loop at creation time, so this is safe on 3.11. However, the singleton is created at module import time, which happens before the server's event loop starts. If the event loop is ever replaced (e.g. by `asyncio.set_event_loop` in tests), the pre-created locks reference a stale loop. This is a low-probability issue but a footgun worth documenting.

---

## Self-Deception Debt

These are patterns that produce green signals without doing the work those signals imply.

### 13. Benchmark `run_count: 1` reported as `deterministic: true`

Dozens of benchmark entries follow this pattern:

```json
{
  "run_count": 1,
  "unique_hashes": 1,
  "deterministic": true
}
```

A single run with one unique hash cannot establish determinism. It establishes that the output was consistent with itself, which is always true. The `deterministic: true` field is structurally false for `run_count < 2`. If any downstream gate relies on this field to make a "determinism proven" decision, those gates are reading manufactured confidence.

---

### 14. `load_env()` silenced in all test runs

```python
def load_env():
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
```

Silencing the env loader during pytest means no test ever exercises the `.env` loading path. If `load_env()` has a bug (e.g. incorrect key parsing, the sync-in-async crash described in finding #2), it will never be caught by the test suite. The fix isn't to remove the guard but to add a targeted integration test that calls `load_env()` with a controlled `.env` fixture.

---

### 15. `.pytest_live_runtime_probe*` directories committed to the tree

At least three probe workspace directories are included in the dump:

- `.pytest_live_runtime_probe/`
- `.pytest_live_runtime_probe_protocol/`
- `.pytest_live_runtime_probe_protocol_enforce/`

These appear to be leftover live test artifacts. They're committed, not gitignored, and contain duplicated fixture JSON. They should be gitignored under `.pytest_*` (which is already in `.gitignore` as `.pytest_*`) — except they aren't matching that pattern because the prefix is `.pytest_live_runtime_probe` not `.pytest_cache`. Add the glob or rename the directories to match the existing ignore rule.

---

### 16. `.claude/settings.local.json` in the dump

This file is listed in `.gitignore` as `.claude/settings.local.json`, yet it appears in the project dump. It exposes the full local source path (`C:/Source/Orket`) and a list of explicitly allowed shell commands. The dump script (`project_dump.py`) likely doesn't read `.gitignore` before including files. The dump is probably not shared externally, but if it ever is, this is a real information leak.

---

## What Was Not Reviewed

The dump is ~350,000 lines. The following areas were not fully reviewed:

- `orket/core/` domain models and policy layer (partially read)
- `orket/adapters/storage/async_repositories.py` and `async_card_repository.py`
- `orket/application/` orchestration services
- `orket/interfaces/` API routers
- All `scripts/` governance and benchmark tooling
- The full test suite

The findings above are based on the files that were sampled. The same rule violations (sync I/O in async paths, swallowed exceptions, hardcoded values) likely recur in the unreviewed portions.

---

## Summary by Category

| Category | Count | Highest Severity |
|---|---|---|
| Ship-risk debt | 7 | Silent crash in error handler, banned sync I/O |
| Exploration-safe debt | 5 | Blocking sync in event loop, duplicated logic |
| Self-deception debt | 4 | False determinism signal, silenced env loader |
