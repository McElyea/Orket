# Agent Instructions

## Response Formatting
When referencing files in chat responses, use clickable Markdown links with absolute Windows paths in URL form.

Required style (preferred):
1. `[Label](/C:/absolute/path/to/file.ext)`
2. Example: `[Local Prompting Requirements](/C:/Source/Orket/docs/projects/protocol-governed/local-prompting-requirements.md)`
3. Example with line suffix (only if the client supports it): `[File:120](/C:/Source/Orket/docs/projects/protocol-governed/local-prompting-requirements.md:120)`

Rules:
1. Prefer `/C:/...` (Style 2). `/c:/...` is acceptable if needed.
2. Do not use `file://` links.
3. Do not use plain backticked paths unless explicitly requested by the user.

## Live Integration Verification (Required)
For any new or changed integration/automation (CI, APIs, webhooks, runners, external services), the agent must verify behavior with a live run against the real configured system before declaring completion.

### Required Proof
1. Run the real command/flow end-to-end (not compile-only or dry-run-only).
2. Record observed mode/path and result (for example: primary API path vs fallback path).
3. If live run fails, capture exact failing step/error and either fix it or report the concrete blocker.

### Testing Policy Reference
1. `docs/CONTRIBUTOR.md` defines execution expectations.
2. `AGENTS.md` defines execution discipline (including required live verification).

## Script Output Conventions (Required)
1. Any new script that writes rerunnable JSON results must use `scripts.common.rerun_diff_ledger.write_payload_with_diff_ledger` (or `write_json_with_diff_ledger` for JSON text payloads).
2. Keep a stable canonical output file path for each script output; reruns must append `diff_ledger` entries instead of creating timestamp-only files.
3. Default major-diff rollover policy for canonical files is:
   - `paths_total_reference <= 250`: threshold `0.93`
   - `251-1200`: threshold `0.88`
   - `>1200`: threshold `0.80`
   - Rollover also requires `churn_paths >= 20`.
4. If a script overrides rollover thresholds or minimum changed paths, include a short code comment explaining why.

## Resource Efficiency

Token usage matters. When delegating to subagents or choosing how to approach a task, use the minimum model tier that gets the job done.

| Task Type | Model Tier | Examples |
|-----------|-----------|----------|
| **Search / Retrieval** | Low (GPT-5.3-Codex:Low/Haiku) | File search, grep, reading code, exploring structure |
| **Coding / Execution** | Medium (GPT-5.3-Codex:Medium/Sonnet) | Writing code, editing files, running tests, fixing bugs |
| **Planning / Architecture** | High (GPT-5.3-Codex:Extra High/Opus) | Design decisions, multi-file refactors, code reviews, complex reasoning |

When the agent framework supports model selection on subtasks (e.g. Claude Code subagent `model` parameter), apply these tiers explicitly. When it does not, prefer targeted reads over broad exploration to reduce context size.

## Code Discipline (Required)

These rules are non-negotiable. Violations must be fixed before declaring a task complete.

### Async Purity
Orket is an **async-first codebase** (FastAPI + asyncio). Blocking calls stall the entire event loop.

1. **Never use `subprocess.run()` or `subprocess.call()`** inside any code path reachable from an async context. Use `asyncio.create_subprocess_exec()` or `await asyncio.to_thread(subprocess.run, ...)` instead.
2. **Never use `Path.read_text()`, `Path.write_text()`, or `open()`** in async code paths. Use `aiofiles` or `AsyncFileTools` or `await asyncio.to_thread()`.
3. **Never use `requests`** (sync HTTP). Use `httpx.AsyncClient`.
4. **Never use `time.sleep()`** in async code. Use `await asyncio.sleep()`.
5. **Never put `lru_cache` on a function that bridges sync-to-async**. Cache at the async layer or not at all.
6. If you are unsure whether a call site is async-reachable, assume it is.

### File Size Limits
God files are the #1 maintainability killer in this codebase.

1. **No Python file may exceed 400 lines.** If your change would push a file past 400 lines, split it first.
2. **No single class may have more than 10 public methods.** If it needs more, it has more than one responsibility -- split it into focused classes.
3. **No single function may exceed 70 lines.** Extract helpers.
4. **API routers**: Each FastAPI router file should own one resource domain (cards, sessions, system, etc.), not all of them.

### DRY / Single Source of Truth
1. **Never duplicate a definition** (exception class, transition table, enum, constant) across files. Define once, import everywhere.
2. **Never create a compatibility shim** (`from new_location import X; __all__ = ["X"]`) without a tracked ticket to remove it. Shims are debt.
3. **Never copy-paste a function** and rename it. If two functions are identical, extract the common logic.

### Exception Handling
1. **Never use bare `except Exception`** unless the function is a top-level entry point (CLI main, API endpoint, background task loop). Document why.
2. Catch the **narrowest reasonable exception type**. If you need to catch 5+ types, reconsider the control flow.
3. **Never silently swallow exceptions.** At minimum, log them.

### Security Boundaries
1. **Never embed credentials in URLs, log messages, or string interpolations.** Use credential helpers or environment variables at point of use.
2. **Never pass unsanitized user input to `subprocess`** commands. Whitelist valid values.
3. **Never use `importlib.exec_module()`** on user-controlled paths without OS-level sandboxing (Docker or equivalent).
4. **Always use `Path.is_relative_to()`** for path containment checks, never `str.startswith()`.

### Naming and Proxies
1. **Never use `__getattr__` delegation** to forward methods to another object. Define explicit methods or properties. `__getattr__` is invisible to IDEs, type checkers, and grep.
2. Proxy/lazy-init patterns are acceptable only in module-level singletons, and must have a comment explaining why.
