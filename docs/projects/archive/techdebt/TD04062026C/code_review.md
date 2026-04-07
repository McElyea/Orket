# Orket Code Review — Brutal Edition

**Scope:** Full codebase scan via project dump. Reviewed against stated rules in `AGENTS.md` (400-line file cap, 70-line function cap, no raw sync I/O on async-reachable paths, no duplicate authority, no stale shims, no god classes) and general production-quality standards.

---

## 1. `execution_pipeline.py` — The God File

**Severity: Critical**

`orket/runtime/execution_pipeline.py` is **72,998 characters** of source. At roughly 80 chars/line that is ~900 lines — more than double the 400-line ceiling mandated in `AGENTS.md`. It imports from at least 30 distinct modules at the top level and appears to house orchestration logic, control-plane service wiring, Gitea state worker startup, epic orchestration, run summary writing, artifact provenance normalization, and phase-C runtime truth collection — all in one file.

This is the single biggest structural violation in the repo. Every other architectural ambition the codebase expresses gets undercut by this file existing. It is a maintenance trap, a merge-conflict magnet, and a test-surface nightmare.

---

## 2. `agent_factory.py` — Dead Loop Checked In

**Severity: High**

```python
for _role_name in seat.roles:
    # Placeholder: In the real traction loop, we load RoleConfigs.
    # Here we just register what tools are in the tool_map.
    pass
```

This is a committed, do-nothing loop with a comment explaining what it *should* do. `build_team_agents` is exported from the public surface. Any caller trusting that roles get correctly wired through this factory will get silently incorrect behavior — every agent gets the full `tool_map` regardless of its declared roles. The function's primary job (seat-scoped tool gating) does not happen.

---

## 3. `StateMachine._TRANSITIONS` — Missing Card Types

**Severity: High**

`orket/core/types.py` defines five `CardType` members:

```python
ROCK, EPIC, ISSUE, UTILITY, APP
```

`StateMachine._TRANSITIONS` only covers `ISSUE`, `EPIC`, and `ROCK`. `UTILITY` and `APP` have no transition table entries. Any card of those types that hits `validate_transition` will either `KeyError` or silently accept any transition depending on the lookup pattern. The schema and the enforcer are out of sync.

---

## 4. `AsyncCardRepository.__getattr__` Delegation — Opaque Anti-Pattern

**Severity: High**

```python
def __getattr__(self, name: str) -> Any:
    delegated = {
        "archive_card": self._archive_ops.archive_card,
        ...
        "add_credits": self._misc_ops.add_credits,
    }
    target = delegated.get(name)
    if target is not None:
        return target
    raise AttributeError(name)
```

Every attribute access that isn't found normally goes through a runtime dictionary lookup that reconstructs the delegation map on each call. This means:

- Mypy and Pyright cannot see these methods — they are invisible to static analysis.
- The pattern hides the class's actual public interface.
- `delegated` is rebuilt on every `__getattr__` call. Under concurrent access this is wasteful.
- The correct pattern is direct composition with explicit methods.

---

## 5. `AsyncCardRepository._execute` — Serialized Reads Under Global Lock

**Severity: High**

```python
async def _execute(self, operation, *, row_factory=False, commit=False) -> ResultT:
    async with self._lock, aiosqlite.connect(self.db_path) as conn:
        ...
```

A single `asyncio.Lock()` gates every database operation — reads and writes alike. Concurrent read operations that could safely run in parallel are forced to serialize. Under even modest card-execution concurrency this becomes the bottleneck. Read-only operations should bypass the write lock entirely.

---

## 6. `logging.py` — Sync File I/O on Async-Reachable Path

**Severity: High**

```python
def _append_line_sync(path: Path, line: str) -> None:
    _ensure_log_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
```

`AGENTS.md` is explicit: *"Do not use `Path.read_text()`, `Path.write_text()`, or raw `open()`"* on async-reachable paths. The queue-plus-thread approach avoids blocking the event loop directly, but the write is performed in a daemon thread with no back-pressure, no bounded queue depth, and no shutdown signal. Log entries can be silently lost on process kill. The thread also holds an open file handle serially — concurrent log bursts serialize through a single writer.

---

## 7. `ToolParser._recover_truncated_tool_calls` — Hardcoded Tool Registry

**Severity: High**

The recovery method has bespoke, by-name handling for `update_issue_status`, `read_file`, `write_file`. Any tool not in that allowlist is skipped with `"unsupported_tool"`. Adding a new tool to the system requires also editing the parser's internal recovery logic — a hidden coupling that will be forgotten. The tool registry and the recovery logic must be the same source of truth.

---

## 8. `GiteaStateTransitioner` — Double-Fetch Race Window

**Severity: High**

Both `transition_state` and `release_or_fail` do:

```python
issue_response = await self.adapter._request_response_with_retry("GET", f"/issues/{issue_number}")
issue = issue_response.json()
snapshot = decode_snapshot(...)
# ... compute new snapshot ...
await self.adapter._request_json("PATCH", ...)
```

The ETag/If-Match guard is applied only on the PATCH, not on the initial GET. Between the GET and the PATCH another process can change the issue body. The `If-Match` header mitigates this on the write, but the stale-read branch (`if str(snapshot.state) == str(to_state): return`) can return success while the actual current state is a third value not yet visible. The idempotency short-circuit is wrong.

---

## 9. `ToolGate._validate_file_write` — Deferred Imports in Hot Path

**Severity: Medium**

```python
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.services.ast_validator import ASTValidator
from orket.services.idesign_validator import iDesignValidator
```

These three imports happen inside `_validate_file_write`, which is called on every `write_file` tool call. Python caches imports so repeated overhead is small, but the pattern hides dependencies, prevents static analysis from seeing the full import graph, and is explicitly discouraged by the size/structure rules in `AGENTS.md`.

---

## 10. `GovernanceTools` — Double-Dereference `.cards.cards`

**Severity: Medium**

```python
await self.cards.cards.update_status(issue_id, CardStatus.WAITING_FOR_DEVELOPER)
```

`self.cards` is the injected dependency. `self.cards.cards` reaches into that dependency's internal sub-object. This is a Law of Demeter violation and means `GovernanceTools` is coupled to the internal structure of whatever it receives, not its interface.

---

## 11. `agent.py` — Substring Model Family Detection

**Severity: Medium**

```python
if "deepseek" in model_name:
    family = "deepseek-r1"
elif "llama" in model_name:
    family = "llama3"
elif "phi" in model_name:
    family = "phi"
elif "qwen" in model_name:
    family = "qwen"
```

Model names are user-supplied strings. A model named `"deepseek-qwen-custom"` would match `deepseek` first — fine. But `"phi-3-mini-qwen-finetuned"` would match `phi` and never reach `qwen`. Silent mis-dispatch to the wrong dialect with no warning. A registry-based approach with explicit model prefixes and a fallthrough warning is the correct fix.

---

## 12. `settings.py` — `AssertionError` as a User-Facing Error

**Severity: Medium**

```python
raise AssertionError(
    f"{operation} must run before the event loop starts or after set_runtime_settings_context()."
)
```

`AssertionError` is for programmer assertions, not for user-facing operational errors. It also gets stripped by `python -O`. This should be a typed custom exception (`SettingsUsageError` or similar) so callers can catch it selectively.

---

## 13. `orket/orket.py` — Undated Compatibility Shim

**Severity: Medium**

The file is labeled *"Compatibility shim for legacy imports"* with no removal date, no deprecation warning, no tracking ticket, and no reference in `CURRENT_AUTHORITY.md`. Per `AGENTS.md`: *"Do not add compatibility shims without explicit user approval or a tracked removal ticket."* The shim is here and has neither.

---

## 14. `BaseCardConfig.priority` — `float | str` Leak

**Severity: Medium**

```python
priority: float | str = Field(default=2.0)
```

The validator converts legacy strings to floats but the declared type remains `float | str`. Downstream code that assumes `priority` is always a float will fail at runtime if the validator path isn't hit (e.g., when constructing from trusted internal data). The field should be `float` after conversion is guaranteed.

---

## 15. `iDesignValidator.ALLOWED_CATEGORIES` — Hardcoded Configuration

**Severity: Medium**

```python
ALLOWED_CATEGORIES = {
    "managers", "engines", "accessors", "utils", "controllers",
    "tests", "schemas", "models", "infrastructure", "services",
    "agent_output", "verification",
}
```

Adding a new allowed directory category — something that happens as projects grow — requires a code change and a test suite run. This should be configuration-driven (loadable from `OrganizationConfig`) so project operators can extend it without touching the validator.

---

## 16. `ConfigLoader._run_async` — Thread-Per-Call Pattern

**Severity: Medium**

```python
with ThreadPoolExecutor(max_workers=1) as pool:
    return pool.submit(lambda: asyncio.run(coro)).result()
```

`ThreadPoolExecutor` is created and destroyed on every synchronous config load call. This spawns, runs, and joins a thread for every config access from a sync context. Under concurrent card execution, this multiplies thread overhead. A shared executor or a proper sync/async bridge is needed.

---

## 17. `openai_compat_runtime.py` — Module-Level Side Effects

**Severity: Low**

`_RECOVERY_STOP_MARKER`, `_ARCHITECT_LABELS`, and `_AUDITOR_LABELS` are compiled/defined at module import time. This is not wrong per se, but they are used only in recovery paths and their presence at module level means any test that imports the module incurs the side effects. The labels especially (`_ARCHITECT_LABELS`, `_AUDITOR_LABELS`) are conceptually configuration that lives in source — they should be in a config file or registry.

---

## 18. `protocol_append_only_ledger.py` — Roll-Your-Own CRC32c

**Severity: Low**

```python
def _build_crc32c_table() -> list[int]:
    polynomial = 0x82F63B78
    ...
```

A hand-rolled CRC32c implementation where a Python standard library function (`binascii.crc32`) or a well-tested library (`crcmod`) could be used. The risk is a subtle bug in the table construction producing wrong checksums that are not caught at write time — only discovered on corrupt-ledger recovery.

---

## 19. `utils.py` — Import-Time Environment Read

**Severity: Low**

```python
CURRENT_LEVEL = _resolve_log_level()
```

`CURRENT_LEVEL` is computed once at import time. Any test or runtime that sets `ORKET_LOG_LEVEL` after the module is first imported will see the stale value. Tests that rely on changing the log level per-test are silently broken.

---

## 20. `GiteaWebhookHandler` — Stateless Sandbox Registry Per Instantiation

**Severity: Low**

```python
self.sandbox_registry = SandboxRegistry()
self.sandbox_orchestrator = SandboxOrchestrator(...)
```

`SandboxRegistry` is constructed fresh on every `GiteaWebhookHandler` instantiation. If the handler is created per-request (common in ASGI frameworks), the registry holds no memory of sandboxes created in prior requests. Any multi-request sandbox lifecycle (create → poll → destroy) requires external persistence, and there is no evidence that persistence is wired.

---

## Summary Table

| # | File | Issue | Severity |
|---|------|-------|----------|
| 1 | `runtime/execution_pipeline.py` | God file, ~900+ lines | Critical |
| 2 | `agents/agent_factory.py` | Dead loop, tool gating never runs | High |
| 3 | `core/domain/state_machine.py` | UTILITY/APP types have no transition table | High |
| 4 | `adapters/storage/async_card_repository.py` | `__getattr__` delegation, invisible to types | High |
| 5 | `adapters/storage/async_card_repository.py` | Global lock serializes reads | High |
| 6 | `logging.py` | Raw `open()` on async-reachable path | High |
| 7 | `application/services/tool_parser.py` | Hardcoded tool registry in recovery | High |
| 8 | `adapters/storage/gitea_state_transitioner.py` | Double-fetch race window | High |
| 9 | `core/policies/tool_gate.py` | Deferred imports in hot path | Medium |
| 10 | `adapters/tools/families/governance.py` | `.cards.cards` double-dereference | Medium |
| 11 | `agents/agent.py` | Substring model family detection | Medium |
| 12 | `settings.py` | `AssertionError` as user-facing error | Medium |
| 13 | `orket/orket.py` | Undated, untracked compat shim | Medium |
| 14 | `schema.py` | `priority: float \| str` type leak | Medium |
| 15 | `services/idesign_validator.py` | Hardcoded allowed categories | Medium |
| 16 | `runtime/config_loader.py` | Thread-per-call sync bridge | Medium |
| 17 | `adapters/llm/openai_compat_runtime.py` | Module-level config side effects | Low |
| 18 | `adapters/storage/protocol_append_only_ledger.py` | Roll-your-own CRC32c | Low |
| 19 | `utils.py` | Import-time env read for log level | Low |
| 20 | `adapters/vcs/gitea_webhook_handler.py` | Stateless sandbox registry | Low |
