# Orket Issue Remediation Plan

Issues are grouped by wave. Each wave is independently releasable. Wave 1 addresses production-blocking behavioral issues. Wave 2 addresses architectural debt that creates ongoing drag. Wave 3 addresses configuration, observability, and maintainability improvements.

Cross-references: [CR] = Code Review item number, [BR] = Behavioral Review item number.

---

## Wave 1 â€” Production Blockers (Fix Before Next Run)

### W1-A: Make Tool Recovery Fail-Closed or All-Or-Nothing
**Source:** BR-1, CR-7
**Files:** `orket/application/services/tool_parser.py`, execution call sites

**What to do:**
1. Add a `recovery_complete: bool` field to the recovery result. Set it `True` only if all detected tool markers were successfully parsed, `False` if any were skipped.
2. In the execution pipeline, treat a `recovery_complete=False` result as a partial-execution event. Log a structured `tool_recovery_partial` event with the list of skipped tools and reasons.
3. Emit an explicit `add_issue_comment` tool call with a blocked-state comment if recovery was partial, rather than proceeding silently.
4. Optionally: gate recovery behavior behind a config flag (`ORKET_ALLOW_PARTIAL_RECOVERY=false` by default).

---

### W1-B: Add Per-Tool-Call Timeout
**Source:** BR-2
**File:** `orket/adapters/tools/runtime.py`

**What to do:**
1. Add a `tool_timeout_seconds: float` parameter to `ToolRuntimeExecutor.invoke` (default: 60.0).
2. Wrap the `await tool_fn(...)` call in `asyncio.wait_for(..., timeout=tool_timeout_seconds)`.
3. Catch `asyncio.TimeoutError` and return `{"ok": False, "error": "tool_timeout", "tool": tool_name}`.
4. Log a `tool_timeout` event via `log_event`.
5. Wire the timeout value through the execution context so it is configurable per-organization.

---

### W1-C: Enforce Lease-Not-None at All Acquisition Sites
**Source:** BR-5
**Files:** `orket/adapters/storage/gitea_state_adapter.py`, execution pipeline call sites

**What to do:**
1. Audit every call site of `acquire_lease`. Add a `if lease is None: ...` guard that logs a `lease_acquisition_failed` event and raises a typed `LeaseNotAvailableError`.
2. Consider making `acquire_lease` raise rather than return `None` â€” the `None` return type in the contract is the root cause. Update `StateBackendContract` to raise `LeaseNotAvailableError` on failure.
3. Ensure the exception is caught at the card-dispatch loop boundary and transitions the card to `blocked` with `wait_reason=system`.

---

### W1-D: Add Turn-Level Retry with Backoff
**Source:** BR-8
**Files:** `orket/runtime/execution_pipeline.py`, agent turn execution site

**What to do:**
1. Wrap the model call in a retry loop with configurable `max_retries` (default: 2) and exponential backoff starting at 1s.
2. Catch `ModelTimeoutError`, `ModelConnectionError`, and `ModelProviderError` from `orket/exceptions.py` â€” these already exist.
3. On exhaustion, surface a `turn_retry_exhausted` event and transition the card to `blocked`.
4. Do NOT retry on semantic failures (malformed tool calls, policy violations) â€” only on transient infrastructure failures.

---

### W1-E: Isolate Middleware Interceptor Failures
**Source:** BR-3
**File:** `orket/application/middleware/hooks.py`

**What to do:**
1. Wrap each interceptor call in `TurnLifecycleInterceptors` with `try/except Exception`:
   ```python
   try:
       outcome = interceptor.before_prompt(...)
   except Exception as exc:
       log_event("interceptor_error", {"interceptor": type(interceptor).__name__, "error": str(exc)}, ...)
       continue
   ```
2. Ensure `on_turn_failure` hooks are still called even when a prior interceptor raised.
3. Add a test: inject a broken interceptor that raises, assert the turn still completes.

---

### W1-F: Move AST Validation Off the Event Loop
**Source:** BR-7, CR-9
**File:** `orket/core/policies/tool_gate.py`

**What to do:**
1. Replace the direct `ASTValidator.validate_code(content, filename)` call with:
   ```python
   violations = await asyncio.to_thread(ASTValidator.validate_code, content, filename)
   ```
2. Ensure `_validate_file_write` is `async` (it must be if it awaits).
3. Update all callers of `ToolGate.validate` to `await` it.
4. Move the deferred imports to the top of the file.

---

## Wave 2 â€” Architectural Debt (Next Sprint)

### W2-A: Split `execution_pipeline.py`
**Source:** CR-1
**File:** `orket/runtime/execution_pipeline.py`

**What to do:**
1. Identify the distinct responsibility groups in the file. Based on imports, these are at minimum:
   - **Gitea worker lifecycle** (`GiteaStateWorker`, `GiteaStateWorkerCoordinator`, `build_gitea_state_*`)
   - **Epic orchestration** (`EpicRunOrchestrator`, epic-related flows)
   - **Run summary and artifact provenance** (`run_summary`, `run_summary_artifact_provenance`, `protocol_receipt_materializer`)
   - **Phase-C runtime truth** (`collect_phase_c_packet2_facts`)
   - **Core card execution loop** (the actual orchestration)
2. Extract each group into its own file under `orket/runtime/`, each under 400 lines.
3. `execution_pipeline.py` becomes a thin coordinator that imports and delegates.
4. All extracted files must have individual test coverage.

---

### W2-B: Fix `agent_factory.py` Dead Loop â€” Implement Role-Scoped Tool Gating
**Source:** CR-2
**File:** `orket/agents/agent_factory.py`

**What to do:**
1. Load `RoleConfig` for each `_role_name` in `seat.roles` (this is what the comment says should happen).
2. Collect the union of allowed tools from each role's `SkillConfig.tools` list.
3. Filter `tool_map` to only those allowed tools before passing to `Agent(...)`.
4. If `seat.roles` is empty, log a `seat_no_roles_configured` warning and assign no tools (fail-closed).
5. Add a unit test: agent built for a seat with a restricted role must not have tools outside that role's allowlist.

---

### W2-C: Add UTILITY and APP to `StateMachine._TRANSITIONS`
**Source:** CR-3
**File:** `orket/core/domain/state_machine.py`

**What to do:**
1. Define transition tables for `CardType.UTILITY` and `CardType.APP`. Determine appropriate lifecycles â€” likely simpler than `ISSUE` (e.g., `READY â†’ IN_PROGRESS â†’ DONE â†’ ARCHIVED`).
2. If the lifecycle is intentionally simple, reuse a profile and document that choice.
3. Add a `validate_transition` test for each new card type.
4. Remove the implicit `KeyError` risk.

---

### W2-D: Replace `AsyncCardRepository.__getattr__` with Explicit Composition
**Source:** CR-4
**File:** `orket/adapters/storage/async_card_repository.py`

**What to do:**
1. Add explicit methods for each delegated operation (`archive_card`, `archive_cards`, `archive_build`, etc.) that call through to the appropriate ops object.
2. Delete `__getattr__`.
3. Add type stubs or typed protocol extensions so static analysis can see the full interface.
4. This is a mechanical change â€” no behavioral difference â€” so no new tests needed beyond confirming existing tests still pass.

---

### W2-E: Add Read/Write Lock Segregation to `AsyncCardRepository`
**Source:** CR-5, BR-4
**File:** `orket/adapters/storage/async_card_repository.py`

**What to do:**
1. Replace the single `asyncio.Lock` with a read/write lock pattern. Python's standard library does not have one, so use `asyncio.Lock` for writes and allow concurrent reads by only acquiring the lock on write operations.
2. Alternatively, use `aiosqlite`'s WAL mode (`PRAGMA journal_mode=WAL`) which allows concurrent readers with a single writer without lock contention at the Python layer.
3. Update `_execute` to accept a `write: bool = False` flag and only acquire the lock for write operations.

---

### W2-F: Add State Reconciliation Between SQLite and Gitea
**Source:** BR-4
**Files:** New `orket/application/services/state_reconciliation_service.py`, CI/scheduled job

**What to do:**
1. Create a `StateReconciliationService` that, given a set of card IDs, fetches state from both SQLite and the Gitea adapter and compares.
2. Log divergences as `state_reconciliation_conflict` events.
3. Define an authority resolution policy: SQLite wins, or Gitea wins, or halt-and-alert.
4. Wire this as a scheduled task (existing weekly CI job is a natural home) or an on-demand script.

---

### W2-G: Make `iDesignValidator.ALLOWED_CATEGORIES` Configuration-Driven
**Source:** CR-15
**Files:** `orket/services/idesign_validator.py`, `orket/schema.py`

**What to do:**
1. Add an `allowed_idesign_categories: list[str] | None` field to `OrganizationConfig` (defaults to `None` â†’ use the hardcoded set as fallback).
2. Thread the organization config into `iDesignValidator` at construction time.
3. Use the configured set if present, fall back to the built-in set if not.

---

### W2-H: Replace `AssertionError` in `settings.py` with Typed Exception
**Source:** CR-12
**File:** `orket/settings.py`

**What to do:**
1. Add `class SettingsBridgeError(RuntimeError): pass` to `orket/exceptions.py`.
2. Replace the `AssertionError` raise with `raise SettingsBridgeError(...)`.
3. Update any catch sites that were catching `AssertionError` for this case.

---

### W2-I: Register and Retire `orket/orket.py` Shim
**Source:** CR-13
**File:** `orket/orket.py`, `docs/ROADMAP.md`

**What to do:**
1. Add a `DeprecationWarning` to each re-exported name in `orket/orket.py`:
   ```python
   import warnings
   warnings.warn("Import from orket.runtime directly.", DeprecationWarning, stacklevel=2)
   ```
2. Add a removal ticket to the roadmap with a target sprint.
3. Update `CURRENT_AUTHORITY.md` to document that `orket.orket` is a deprecated surface.

---

### W2-J: Add Webhook Payload Schema Validation
**Source:** BR-14
**File:** `orket/adapters/vcs/gitea_webhook_handler.py`

**What to do:**
1. Define Pydantic models for the Gitea webhook payloads the handler consumes (PR open, PR merge, PR review).
2. Validate incoming `payload` dicts at the top of each handler method before any key access.
3. Return a structured error response on validation failure rather than propagating `KeyError`.

---

## Wave 3 â€” Observability and Hardening (Ongoing)

### W3-A: Add Tool Registry as Single Source of Truth for Recovery
**Source:** CR-7, BR-1
**Files:** `orket/adapters/tools/`, `orket/application/services/tool_parser.py`

Define a `ToolRegistry` that maps tool names to their required argument schemas. `ToolParser._recover_truncated_tool_calls` consults the registry instead of having hardcoded per-tool logic. Adding a new tool requires only registering it â€” no changes to the parser.

---

### W3-B: Add Backpressure to the Log Write Queue
**Source:** BR-15
**File:** `orket/logging.py`

Replace `queue.SimpleQueue` with `queue.Queue(maxsize=N)` where N is configurable via `ORKET_LOG_QUEUE_MAX`. On queue full, either drop with a `dropped_log_entries` counter (lossy) or block with a timeout (back-pressure). Document the chosen policy.

---

### W3-C: Fix Import-Time Environment Read for Log Level
**Source:** CR-19
**File:** `orket/utils.py`

Convert `CURRENT_LEVEL` from a module-level constant to a function `get_current_level()` that reads `ORKET_LOG_LEVEL` at call time with an internal cache invalidated by a test fixture helper. This makes test isolation possible without module reimporting.

---

### W3-D: Add Model Family Registry
**Source:** CR-11, BR-13
**File:** `orket/agents/agent.py`

Replace the `if "deepseek" in model_name` chain with a registry:
```python
_FAMILY_PATTERNS = [
    ("deepseek", "deepseek-r1"),
    ("llama", "llama3"),
    ("phi", "phi"),
    ("qwen", "qwen"),
]
```
Iterate and match. If no pattern matches, log a `model_family_unrecognized` event at `warn` level and use `"generic"`. Make the registry loadable from config so operators can add families without code changes.

---

### W3-E: Persist Sandbox Registry
**Source:** BR-11
**Files:** `orket/core/domain/sandbox.py`, `orket/adapters/vcs/gitea_webhook_handler.py`

`SandboxRegistry` needs to persist state across handler instantiations. Options:
1. Store sandbox state in the existing SQLite database via a `sandbox_lifecycle` table (already exists: `async_sandbox_lifecycle_repository.py`).
2. Inject the repository into `GiteaWebhookHandler` at app startup so it is shared across requests.
3. Update `SandboxOrchestrator` to read/write through the repository rather than the in-memory registry.

---

### W3-F: Narrow `BaseCardConfig.priority` to `float`
**Source:** CR-14
**File:** `orket/schema.py`

After confirming the `convert_priority` validator is hit on all construction paths, change `priority: float | str` to `priority: float`. Add a migration note for any persisted data that might have string priorities.

---

### W3-G: Replace Roll-Your-Own CRC32c
**Source:** CR-18
**File:** `orket/adapters/storage/protocol_append_only_ledger.py`

Use `struct.pack(">I", binascii.crc32(payload_bytes) & 0xFFFFFFFF)` from the standard library. The Castagnoli polynomial (`crc32c`) is not the same as the standard `crc32`, but Python's `binascii.crc32` uses the IEEE polynomial. If Castagnoli is required for compatibility with an external reader, document this explicitly and add a comment referencing the RFC. Either way, remove the hand-rolled table.

---

## Effort Estimates

| Wave | Items | Estimated Effort |
|------|-------|-----------------|
| Wave 1 | W1-A through W1-F | 2â€“3 days |
| Wave 2 | W2-A through W2-J | 1â€“2 sprints |
| Wave 3 | W3-A through W3-G | Ongoing, ~1 item per sprint |

Wave 1 items should not wait for Wave 2. Each W1 item is independently deployable and addresses a live production risk.
