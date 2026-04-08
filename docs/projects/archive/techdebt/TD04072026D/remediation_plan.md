# Orket — Remediation Plan

Last updated: 2026-04-07
Status: Archived (closeout complete)
Archive: `docs/projects/archive/techdebt/TD04072026D/`

Issues are sequenced by dependency and risk. Fix blockers first, then systemic, then hygiene. Estimated effort ratings: **S** (< 2h), **M** (half day), **L** (1–2 days), **XL** (3+ days).

Status snapshot (2026-04-07):
- Phase 1 complete.
- Phase 2 complete.
- Phase 3 complete.
- Phase 4 complete.
- Phase 5 complete.

---

## Phase 1 — Security Blockers (Do First, Nothing Else Ships Until These Are Done)

### P1-1 · Fix HMAC signature comparison in webhook validation
Status: Fixed 2026-04-07.

**File:** `orket/webhook_server.py` — `validate_signature()`
**Effort:** S

Change:
```python
expected_signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
return hmac.compare_digest(signature, expected_signature)
```
To:
```python
expected_hex = hmac.new(secret, payload, hashlib.sha256).hexdigest()
expected_signature = f"sha256={expected_hex}"
return hmac.compare_digest(signature, expected_signature)
```
Add a test that sends a correctly signed webhook and asserts it passes. Add a test that sends a raw hex-only signature and asserts it fails.

---

### P1-2 · Fix `_WebhookHandlerProxy._get()` race condition
Status: Fixed 2026-04-07.

**File:** `orket/webhook_server.py` — `_WebhookHandlerProxy`
**Effort:** S

Replace the lazy init with an `asyncio.Lock`-guarded pattern:
```python
self._lock = asyncio.Lock()

async def _get_async(self) -> GiteaWebhookHandler:
    async with self._lock:
        if self._handler is None:
            self._handler = self._create_handler()
        return self._handler
```
Update `handle_webhook()` to `await self._get_async()`. Remove the dead `self.client` from `GiteaWebhookHandler.__init__`.

---

### P1-3 · Fix undefined `_null_effect_journal_entry` in `NullControlPlaneAuthorityService`
Status: Verified fixed in current tree on 2026-04-07.

**File:** `orket/agents/agent.py`
**Effort:** S

Either import the function from its correct module or inline the construction:
```python
from orket.core.contracts import EffectJournalEntryRecord

class NullControlPlaneAuthorityService:
    def append_effect_journal_entry(self, **_kwargs: Any) -> EffectJournalEntryRecord:
        return EffectJournalEntryRecord(...)   # fill required fields with null/sentinel values
```
Add a unit test that constructs `NullControlPlaneAuthorityService` and calls `append_effect_journal_entry()`.

---

### P1-4 · Reduce JWT token lifetime and add revocation groundwork
Status: Fixed 2026-04-07.

**File:** `orket/services/auth_service.py`
**Effort:** M

1. Reduce `ACCESS_TOKEN_EXPIRE_MINUTES` to `60` (1 hour) or make it configurable via `ORKET_AUTH_TOKEN_EXPIRE_MINUTES`.
2. Add a `jti` (JWT ID) UUID claim to every issued token.
3. Create a `TokenBlocklist` (SQLite-backed or Redis-backed) with `revoke(jti)` and `is_revoked(jti) -> bool`.
4. Check `is_revoked()` in the token verification path.
5. Fix the double-checked locking in `get_secret_key()` — move the outer check inside the lock or use `functools.lru_cache`.

---

### P1-5 · Sanitize agent context injection to prevent prompt injection
Status: Fixed 2026-04-07.

**File:** `orket/agents/agent.py` — `Agent.run()`
**Effort:** M

1. Create a `_render_context(context: dict) -> str` function that formats context as a structured, delimited block:
   ```
   <context>
   key: value
   ...
   </context>
   ```
2. Replace `f"Context: {context}"` with the rendered output.
3. Identify which context keys come from user-controlled surfaces vs. system surfaces and document the trust boundary explicitly.
4. Add a regression test with an adversarial context value containing `"Ignore all previous instructions"` and assert it does not alter model behavior (this may be a behavioral test against a stub provider).

---

## Phase 2 — Critical Correctness Bugs

### P2-1 · Fix issue ID collision risk in `create_issue()`
Status: Fixed 2026-04-07.

**File:** `orket/adapters/tools/families/cards.py`
**Effort:** S

Replace:
```python
issue_id = f"ISSUE-{str(uuid.uuid4())[:4].upper()}"
```
With:
```python
issue_id = f"ISSUE-{uuid.uuid4().hex[:12].upper()}"
```
12 hex characters gives 16^12 ≈ 281 trillion possible IDs, making collision probability negligible. Alternatively, use a ULID (already present in the codebase via `_generate_ulid()`).

---

### P2-2 · Guard `int(card_id)` in `renew_lease()` to match `acquire_lease()`
Status: Fixed 2026-04-07.

**File:** `orket/adapters/storage/gitea_lease_manager.py`
**Effort:** S

Wrap `issue_number = int(card_id)` in a try/except identical to `acquire_lease()`. Return `None` on `ValueError`. Add a unit test for non-numeric `card_id` on both methods.

---

### P2-3 · Fix `get_task()` to return `None` when no active task exists
Status: Fixed 2026-04-07.

**File:** `orket/state.py`
**Effort:** S

Change:
```python
return tasks[-1] if tasks else None
```
To:
```python
return None
```
The fallback `tasks[-1]` returns a completed task, which is semantically wrong for callers expecting an active task. Update all callers that currently don't check `.done()` on the return value.

---

### P2-4 · Fix `StreamBus.publish()` event delivery when advisory fires
Status: Verified fixed in current tree on 2026-04-07.

**File:** `orket/streaming/bus.py`
**Effort:** M

When a best-effort event is dropped and `STREAM_TRUNCATED` is issued as an advisory, deliver the advisory to subscribers but do not discard the return value contract. The current `outgoing_event = advisory_event or event` means the caller's return value (`event`) is still returned, but subscribers see only the advisory. Options:

1. Deliver both the advisory and the event (advisory first, then event), subject to the "post-terminal forbidden" rule.
2. Deliver only the advisory and return `None` to the caller so the caller knows the event was dropped.

Option 2 is simpler. Update callers that check the return value. Add a test that drives an event budget to exhaustion and asserts advisory fires exactly once, and primary events after the limit return `None`.

---

### P2-5 · Fix `purge_turn()` `put_nowait()` crash on full queue
Status: Fixed 2026-04-07.

**File:** `orket/streaming/bus.py`
**Effort:** S

In `_drain_queue_for_turn()`, replace `queue.put_nowait(event)` with a guard:
```python
try:
    queue.put_nowait(event)
except asyncio.QueueFull:
    pass   # best-effort retention; drop on overflow
```
This matches the bus's overall best-effort philosophy for non-MUST_DELIVER events.

---

### P2-6 · Make `_ensure_initialized()` in `MemoryStore` concurrency-safe
Status: Fixed 2026-04-07.

**File:** `orket/services/memory_store.py`
**Effort:** S

Add an `asyncio.Lock` to guard initialization:
```python
self._init_lock = asyncio.Lock()

async def _ensure_initialized(self) -> None:
    if self._initialized:
        return
    async with self._init_lock:
        if self._initialized:
            return
        async with aiosqlite.connect(self.db_path) as conn:
            ...
        self._initialized = True
```

---

### P2-7 · Make `_run_git_command()` non-blocking
Status: Fixed 2026-04-07.

**File:** `orket/application/review/run_service.py`
**Effort:** S

Wrap the `subprocess.run` call in `asyncio.to_thread`:
```python
async def _run_git_command_async(repo_root: Path, args: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
    return await asyncio.to_thread(_run_git_command, repo_root, args, check=check)
```
Update all callers to `await _run_git_command_async(...)`.

---

### P2-8 · Add atomic write guarantee to `CommitOrchestrator`
Status: Fixed 2026-04-07.

**File:** `orket/streaming/manager.py` — `CommitOrchestrator._write_commit_artifact()`
**Effort:** S

Use write-to-temp-then-rename:
```python
import tempfile, os

tmp_path = path.with_suffix(".tmp")
async with aiofiles.open(tmp_path, "w", encoding="utf-8") as handle:
    await handle.write(json.dumps(payload, indent=2, sort_keys=True))
await asyncio.to_thread(os.replace, str(tmp_path), str(path))
```
`os.replace` is atomic on POSIX. On Windows it may not be — document the platform assumption.

---

### P2-9 · Fix forbidden pattern false positive on removed lines
Status: Fixed 2026-04-07.

**File:** `orket/application/review/lanes/deterministic.py`
**Effort:** S

Remove the fallback `regex.search(snapshot.diff_unified)` search and restrict matching exclusively to `added_lines`. The intent of the check is to prevent *introducing* forbidden patterns, not to flag their removal.

---

### P2-10 · Fix `_ns_to_ms()` stub in `openai_compat_runtime.py`
Status: Verified fixed in current tree on 2026-04-07.

**File:** `orket/adapters/llm/openai_compat_runtime.py`
**Effort:** S

Complete the function:
```python
def _ns_to_ms(value: Any) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    return float(value) / 1_000_000.0
```
Add a unit test asserting `_ns_to_ms(1_000_000) == 1.0`.

---

## Phase 3 — Architecture & Systemic Issues

### P3-1 · Replace per-request `httpx.AsyncClient` creation in `GiteaHTTPClient` with connection pooling
Status: Fixed 2026-04-07.

**File:** `orket/adapters/storage/gitea_http_client.py`
**Effort:** M

1. Move `httpx.AsyncClient` construction into the `GiteaHTTPClient.__init__()` (or the parent adapter).
2. Store it as `self._client`.
3. Add `async def close(self)` that calls `await self._client.aclose()`.
4. Ensure the adapter's lifecycle (constructor/close) is managed by its owner.
5. Remove the dead `self.client` from `GiteaWebhookHandler`.

---

### P3-2 · Consolidate duplicate session-state systems (`GlobalState` + `InteractionManager`)
Status: Fixed 2026-04-07.

**File:** `orket/state.py`, `orket/streaming/manager.py`
**Effort:** XL

The two systems must be either merged or given explicit, non-overlapping responsibilities with documented handoff contracts:

1. **Option A (merge):** Make `InteractionManager` the single source of truth. Migrate WebSocket tracking from `GlobalState.active_websockets` into `InteractionManager` as a subscriber registry keyed by session ID. Remove `GlobalState.active_tasks` (task management moves into `InteractionManager`).
2. **Option B (split by concern):** Document `GlobalState` as the "transport layer" (WebSocket lifecycle) and `InteractionManager` as the "session layer" (turn state). Add explicit join/leave hooks so both systems stay in sync.

Option A is recommended. Effort is XL due to call-site migrations.

---

### P3-3 · Replace `MemoryStore` with a real retrieval backend
Status: Fixed 2026-04-07.

**File:** `orket/services/memory_store.py`
**Effort:** XL

The current implementation cannot fulfill the stated "RAG" contract. Choose one:

1. **Lightweight path:** Replace keyword splitting with SQLite FTS5 (`CREATE VIRTUAL TABLE project_memory USING fts5(content, metadata_json)`). This provides BM25 ranking with no external dependencies. Requires SQLite 3.9+.
2. **Full vector path:** Integrate `chromadb` or `hnswlib` + sentence-transformer embeddings. Add an `embed(content: str) -> list[float]` abstraction so the backend is swappable.

Regardless of choice: remove the `limit * 20` over-fetch and use SQL-level filtering.

---

### P3-4 · Fix `ConfigPrecedenceResolver.SECTION_KEYS` to be instance state
Status: Fixed 2026-04-07.

**File:** `orket/application/services/config_precedence_resolver.py`
**Effort:** S

Move `SECTION_KEYS` to an instance variable with a class-level default:

```python
_DEFAULT_SECTION_KEYS: frozenset[str] = frozenset({"mode", "memory", "voice"})

def __init__(self, ..., extra_sections: set[str] | None = None) -> None:
    self._section_keys = set(self._DEFAULT_SECTION_KEYS) | (extra_sections or set())
```

Remove `register_section()` as a class method. Any test calling it currently must be updated to pass `extra_sections` at construction time.

---

### P3-5 · Fix `Agent.__init__` blocking file I/O and add null guard for `_null_effect_journal_entry`
Status: Fixed 2026-04-07.

**File:** `orket/agents/agent.py`
**Effort:** M

1. Make `_load_configs()` a lazy method called on first use of `self.skill` / `self.dialect`, or provide an `async classmethod` factory (`Agent.create(...)`) that awaits the config load via `asyncio.to_thread`.
2. Ensure `NullControlPlaneAuthorityService` returns a fully constructed `EffectJournalEntryRecord` (see P1-3).

---

### P3-6 · Add a token delta semantic layer to `marshaller_v0.py`
Status: Fixed 2026-04-07.

**File:** `orket/workloads/marshaller_v0.py`
**Effort:** S

Replace the SHA-256 hash token delta with a human-readable summary:
```python
summary = f"marshaller result: accept={result['accept']} attempts={result['attempt_count']}"
await interaction_context.emit_event(
    StreamEventType.TOKEN_DELTA,
    {"delta": summary, "index": 0, "authoritative": False},
)
```
Or omit the `TOKEN_DELTA` entirely for deterministic workloads that don't produce token streams, and emit only `MODEL_READY` and `COMMIT_FINAL`.

---

### P3-7 · Make `StreamBus` token budget configurable per workload type
Status: Fixed 2026-04-07.

**File:** `orket/streaming/bus.py`, `orket/workloads/model_stream_v1.py`
**Effort:** M

1. Add `best_effort_max_events_per_turn` override support to `StreamBusConfig`.
2. Allow the workload to negotiate its budget at turn start (e.g., via `turn_params["stream_budget"]`).
3. For `model_stream_v1`, default to a budget of at least 2048 token deltas.
4. Add a test that streams 300 events and verifies none are dropped with a 512-event budget.

---

### P3-8 · Add async-safe locking to `settings.py` cache paths
Status: Fixed 2026-04-07.

**File:** `orket/settings.py`
**Effort:** M

1. Replace `threading.RLock()` in `_SETTINGS_CACHE_LOCK` with `asyncio.Lock()` for all async call sites.
2. Keep a separate `threading.Lock()` for the sync-only `load_env()` path.
3. Document clearly which functions are safe to call from async contexts and which are not.

---

### P3-9 · Wire `SlidingWindowRateLimiter` to a shared backend for multi-worker safety
Status: Fixed 2026-04-07 (documented degraded per-process mode).

**File:** `orket/webhook_server.py`
**Effort:** L

1. If Redis is available: use a Redis INCR+EXPIRE sliding window.
2. If Redis is not available: document the per-process limitation explicitly in `.env.example` and deployment runbook, and set `ORKET_RATE_LIMIT` accounting for worker count.
3. Add the worker count consideration to the health endpoint response for observability.

---

## Phase 4 — Medium Quality Improvements

### P4-1 · Add SQL-level keyword filtering to `MemoryStore.search()`
Status: Fixed 2026-04-07.

**File:** `orket/services/memory_store.py`
**Effort:** S

As an interim fix (before P3-3), add a WHERE clause that filters rows to those whose `keywords` column contains at least one query word:

```sql
SELECT * FROM project_memory WHERE keywords LIKE ? OR keywords LIKE ? ...
ORDER BY created_at DESC LIMIT ?
```

This reduces the over-fetch from `limit * 20` rows to a query-matched subset.

---

### P4-2 · Deduplicate `MemoryStore.remember()` writes
Status: Fixed 2026-04-07.

**File:** `orket/services/memory_store.py`
**Effort:** S

Add a content hash column and use `INSERT OR IGNORE`:
```sql
ALTER TABLE project_memory ADD COLUMN content_hash TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_content_hash ON project_memory(content_hash);
```
Hash content before insert; skip if already present.

---

### P4-3 · Standardize error types in `bundle_validation.py`
Status: Fixed 2026-04-07.

**File:** `orket/application/review/bundle_validation.py`
**Effort:** M

1. Create a `ReviewBundleError(Exception)` base with `error_code: str` and `field: str` attributes.
2. Replace all `raise ValueError("error_code_string")` with `raise ReviewBundleError(error_code="...", field="...")`.
3. Update all callers to catch `ReviewBundleError` and access `.error_code` directly.

---

### P4-4 · Fix `IssueMetrics.grade` typing
Status: Fixed 2026-04-07.

**File:** `orket/schema.py`
**Effort:** S

```python
from typing import Literal
grade: Literal["Shippable", "Non-Shippable", "Pending"] = "Pending"
```

---

### P4-5 · Cache `stream_enabled()` at construction time
Status: Fixed 2026-04-07.

**File:** `orket/streaming/manager.py`
**Effort:** S

```python
def __init__(self, ...) -> None:
    ...
    self._stream_enabled: bool = self._resolve_stream_enabled()

@staticmethod
def _resolve_stream_enabled() -> bool:
    raw = (os.getenv("ORKET_STREAM_EVENTS_V1", "false") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}
```

---

### P4-6 · Fix `validate_openai_messages()` diagnostic output to show original role value
Status: Fixed 2026-04-07.

**File:** `orket/adapters/llm/openai_compat_runtime.py`
**Effort:** S

```python
original_role = str(message.get("role") or "")
role = original_role.strip().lower()
if role not in allowed_roles:
    invalid.append(f"{index}:{original_role or '<missing>'}")
```

---

### P4-7 · Add `_recovery_run_once` guard to `AsyncDualModeLedgerRepository`
Status: Fixed 2026-04-07.

**File:** `orket/adapters/storage/async_dual_write_run_ledger.py`
**Effort:** S

`_recover_pending_intents()` should run once at startup via an explicit `await repo.initialize()` call, not at the top of every write operation. Add an init method that callers must await before first use, guarded by `_recovery_complete`.

---

### P4-8 · Document and enforce `_allowed_log_services` via configuration
Status: Fixed 2026-04-07.

**File:** `orket/services/sandbox_orchestrator.py`
**Effort:** S

Read allowed log services from organization config or a dedicated environment variable:
```python
self._allowed_log_services = set(
    os.getenv("ORKET_SANDBOX_ALLOWED_LOG_SERVICES", "api,frontend,db,database,pgadmin,mongo,mongo-express").split(",")
)
```

---

### P4-9 · Revise default forbidden pattern policy to reduce false positives
Status: Fixed 2026-04-07.

**File:** `orket/application/review/policy_resolver.py` — `DEFAULT_POLICY`
**Effort:** S

Replace:
```json
{"pattern": "(?i)password\\s*=", "severity": "high"}
```
With a pattern that requires a string literal on the right side:
```json
{"pattern": "(?i)password\\s*=\\s*['\\\"](?!\\s*['\\\"])", "severity": "high"}
```
This matches `password = "actual_string"` but not `password = get_from_vault()` or `password = None`.

---

### P4-10 · Remove `tasks[-1]` fallback from `GlobalState.get_task()`
Already covered by P2-3. No additional work needed.

---

## Phase 5 — Hygiene & Long-Tail

| ID | Item | File | Effort |
|----|------|------|--------|
| P5-1 | Move `runtime_state = GlobalState()` into a factory function; add `reset()` | `state.py` | Fixed 2026-04-07 |
| P5-2 | Add `aclose()` to `LocalModelProvider`; add context manager support | `adapters/llm/local_model_provider.py` | Fixed 2026-04-07 |
| P5-3 | Make `get_eos_sprint()` base date configuration-driven | `utils.py` | Fixed 2026-04-07 |
| P5-4 | Add TTL/LRU eviction to `StreamBus._turn_states` | `streaming/bus.py` | Fixed 2026-04-07 |
| P5-5 | Add `frozenset` guard to `EnvironmentConfig.warn_on_unknown_keys` — use `model_fields` not `set(cls.model_fields)` | `schema.py` | Fixed 2026-04-07 |
| P5-6 | Fix `_parse_bool()` to reject unrecognized values with a warning | `adapters/llm/local_prompting_policy.py` | Fixed 2026-04-07 |
| P5-7 | Add Gitea issue body size check before encoding snapshot | `adapters/storage/gitea_lease_manager.py` | Fixed 2026-04-07 |
| P5-8 | Fix `build_packet1_provider_lineage()` to set `present` based on actual field population | `streaming/session_context.py` | Fixed 2026-04-07 |
| P5-9 | Remove `_current_level_cache` module global in `utils.py`; use `functools.lru_cache` | `utils.py` | Fixed 2026-04-07 |
| P5-10 | Add `max_occurrences` cap to forbidden pattern findings in deterministic lane | `application/review/lanes/deterministic.py` | Fixed 2026-04-07 |

---

## Execution Order Summary

```
Phase 1 (security)  ──▶  Phase 2 (correctness)  ──▶  Phase 3 (architecture)
     ↑                           ↑                           ↑
P1-1 through P1-5          P2-1 through P2-10         P3-1 through P3-9
must ship before            unblock Phase 3            enable Phase 4+
anything else
```

Phase 1 is non-negotiable before any production traffic. Phase 2 prevents data corruption and incorrect behavior. Phase 3 addresses systemic patterns that will regenerate Phase 2-class bugs if left unresolved. Phases 4 and 5 are quality work that can be spread across normal sprint cycles.
