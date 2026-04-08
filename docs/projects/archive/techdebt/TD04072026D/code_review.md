# Orket — Brutal Code Review

> Reviewed files: `streaming/`, `agents/`, `services/`, `adapters/`, `application/review/`, `webhook_server.py`, `settings.py`, `state.py`, `schema.py`, `session.py`, `tools.py`, `utils.py`, `workloads/`

---

## 🔴 Critical / Security

### 1. Gitea HMAC signature comparison strips the `sha256=` prefix incorrectly (`webhook_server.py`)

```python
# webhook_server.py – validate_signature()
expected_signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
return hmac.compare_digest(signature, expected_signature)
```

Gitea sends the signature header as `sha256=<hexdigest>`. The code compares the raw hex digest against the full header value (which includes the `sha256=` prefix), so every legitimate Gitea webhook will fail validation and every empty-prefix attacker string of the correct hex could theoretically be crafted. The comparison should be `hmac.compare_digest(f"sha256={expected_signature}", signature)`.

---

### 2. `_WebhookHandlerProxy._get()` is not thread/coroutine safe (`webhook_server.py`)

```python
def _get(self) -> GiteaWebhookHandler:
    if self._handler is None:
        self._handler = self._create_handler()
    return self._handler
```

There is no lock. Under concurrent FastAPI requests two coroutines can both see `_handler is None` simultaneously, call `_create_handler()`, and instantiate two handlers. The first one created is silently orphaned (leaking its `httpx.AsyncClient`). An `asyncio.Lock` guarding lazy initialization is required.

---

### 3. JWT tokens expire after 24 hours with no revocation mechanism (`auth_service.py`)

```python
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day
```

Twenty-four hours is an extremely long session window. There is no token blacklist, no refresh-token flow, and no `jti` claim. A stolen token is valid for up to a day with no remediation path short of rotating `ORKET_AUTH_SECRET` (which invalidates every user simultaneously).

---

### 4. Module-level `SECRET_KEY` double-checked locking is non-atomic (`auth_service.py`)

```python
SECRET_KEY: str | None = None
_SECRET_KEY_LOCK = threading.Lock()

def get_secret_key() -> str:
    global SECRET_KEY
    if SECRET_KEY:          # ← non-atomic pre-check
        return SECRET_KEY
    with _SECRET_KEY_LOCK:
        if SECRET_KEY:
            return SECRET_KEY
        ...
```

The outer `if SECRET_KEY` read is unsynchronized. While CPython's GIL makes this unlikely to corrupt in practice, this is undefined behavior under asyncio + threading hybrid code and violates the documented semantics of double-checked locking.

---

### 5. `MemoryStore._initialized` has no concurrency guard (`services/memory_store.py`)

```python
async def _ensure_initialized(self) -> None:
    if self._initialized:
        return
    async with aiosqlite.connect(self.db_path) as conn:
        await conn.execute("CREATE TABLE IF NOT EXISTS project_memory ...")
        await conn.commit()
    self._initialized = True
```

Between the `if self._initialized` check and `self._initialized = True` there are multiple `await` points. Two concurrent callers will both see `False` and both execute the initialization. `CREATE TABLE IF NOT EXISTS` is idempotent so data corruption is avoided, but this is a semantic race that can silently run initialization code twice.

---

### 6. Prompt injection via unescaped context dict (`agents/agent.py`)

```python
messages.append({"role": "user", "content": f"Context: {context}"})
```

`context` is a plain Python dict stringified with `str()`. If any value in `context` contains adversarial text (e.g., `"Ignore all previous instructions and..."`) it is injected verbatim into the model's user turn. There is no sanitization, no escaping, and no structural boundary between operator-supplied data and the model's instruction surface.

---

### 7. `NullControlPlaneAuthorityService` calls an undefined function (`agents/agent.py`)

```python
class NullControlPlaneAuthorityService:
    def append_effect_journal_entry(self, **_kwargs: Any) -> EffectJournalEntryRecord:
        return _null_effect_journal_entry()   # ← not defined in this file
```

`_null_effect_journal_entry` is not imported and not defined anywhere visible in `agent.py`. This is a `NameError` waiting to happen at runtime whenever any code path reaches this branch.

---

## 🟠 High — Correctness & Data Integrity

### 8. `renew_lease()` does not guard `int(card_id)` conversion (`adapters/storage/gitea_lease_manager.py`)

```python
async def renew_lease(self, card_id: str, *, owner_id: str, ...) -> dict[str, Any] | None:
    issue_number = int(card_id)   # ← unguarded, raises ValueError on non-numeric
```

`acquire_lease()` in the same class has `try: issue_number = int(card_id) except ValueError: ... return None`. `renew_lease()` omits this guard entirely — a non-numeric `card_id` will propagate a bare `ValueError` to callers that are not expecting it.

---

### 9. `StreamBus.publish()` silently drops the primary event when advisory fires (`streaming/bus.py`)

```python
outgoing_event = advisory_event or event
if outgoing_event is not None:
    for queue in subscribers:
        await queue.put(outgoing_event)
return event
```

When a best-effort event is dropped and `advisory_event` (STREAM_TRUNCATED) is emitted, the `or` operator means only the advisory is delivered to subscribers. The original event is returned to the caller, giving a false signal that the event was published, while subscribers only receive the advisory. The token delta that triggered the budget exhaustion is silently lost.

---

### 10. `create_issue()` generates IDs from 4 UUID hex characters — catastrophic collision risk (`adapters/tools/families/cards.py`)

```python
issue_id = f"ISSUE-{str(uuid.uuid4())[:4].upper()}"
```

A 4-character hex prefix gives 65,536 possible IDs. Birthday paradox collision probability exceeds 50% at ~256 issues in a build. The `save()` call uses `INSERT OR REPLACE`, so a collision silently overwrites an existing issue. This is a data integrity time bomb.

---

### 11. `finalize_run()` has no rollback on run-graph reconstruction failure (`adapters/storage/async_protocol_run_ledger.py`)

The function appends a finalize event to `pending_events`, calls `reconstruct_run_graph()`, and if reconstruction fails mid-flight, the state is partially committed with no cleanup. A failed finalization leaves the run in an inconsistent state with a finalized event in the ledger but an absent or corrupt run graph artifact.

---

### 12. `get_task()` returns a completed task when all tasks are done (`state.py`)

```python
async def get_task(self, session_id: str) -> asyncio.Task[Any] | None:
    ...
    for task in reversed(tasks):
        if not task.done():
            return task
    return tasks[-1] if tasks else None   # ← returns a DONE task
```

Callers expecting an active task get a task that has already completed. If callers then check `.done()` or call `.result()` without guarding, behavior is undefined. The method should return `None` when no active task exists.

---

### 13. Blocking subprocess call in async review service (`application/review/run_service.py`)

```python
def _run_git_command(repo_root: Path, args: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, ...)
```

`_run_git_command()` is called from synchronous helpers that are in turn called from the async review flow. This blocks the event loop for the duration of the git command (up to `GIT_COMMAND_TIMEOUT_SECONDS = 30`). All other coroutines stall during this window. Should be `await asyncio.to_thread(subprocess.run, ...)`.

---

### 14. `purge_turn()` calls `queue.put_nowait()` inside an async context, can raise `QueueFull` (`streaming/bus.py`)

```python
def _drain_queue_for_turn(queue, *, session_id, turn_id):
    retained = []
    while True:
        try:
            event = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        if event.session_id != session_id or event.turn_id != turn_id:
            retained.append(event)
    for event in retained:
        queue.put_nowait(event)   # ← raises QueueFull if queue is at capacity
```

After draining, re-inserting retained events uses `put_nowait()`. If the queue was at capacity and the retained events fill it back up, `asyncio.QueueFull` is raised — uncaught, propagating through `purge_turn()` and crashing the caller.

---

### 15. Forbidden pattern matching produces false positives on removed lines (`application/review/lanes/deterministic.py`)

The lane first searches `added_lines` for a pattern match. If not found there, it falls back to `regex.search(snapshot.diff_unified)` — the raw unified diff, which includes removed lines prefixed with `-`. A pattern appearing only in deleted code generates a spurious `PATTERN_MATCHED` finding.

---

### 16. `GiteaHTTPClient` creates a new `httpx.AsyncClient` on every request — no connection pooling

```python
async with httpx.AsyncClient(timeout=self.adapter.timeout_seconds) as client:
    response = await client.request(...)
```

Every Gitea API call opens a new TCP connection. For a system that calls Gitea for every state transition, lease operation, and event append, this is O(N) TCP handshakes per workflow. In production this will hit OS connection limits and make response times erratic. An `httpx.AsyncClient` should be constructed once and shared (or managed via a pool).

---

## 🟡 Medium — Quality & Design

### 17. `Agent.__init__` does synchronous file I/O in constructor

`_load_configs()` calls `ConfigLoader.load_asset()` which reads from disk. If `Agent` is constructed in an async context (e.g., inside a request handler), this blocks the event loop. Construction should be deferred or the config loading should be lazy/async.

---

### 18. `MemoryStore.search()` fetches `limit * 20` rows from SQLite with no SQL-level filtering

```python
cursor = await conn.execute(
    "SELECT * FROM project_memory ORDER BY created_at DESC, id DESC LIMIT ?",
    (limit * 20,),
)
```

All filtering is done in Python after fetching up to `limit * 20` rows. For a large store this means pulling potentially thousands of rows across the SQLite/Python boundary only to discard most. A `keywords LIKE` or FTS5 WHERE clause should do first-pass filtering in SQL.

---

### 19. `settings.py` mixes threading primitives with async code

`_SETTINGS_CACHE_LOCK = threading.RLock()` is acquired inside `_read_cache()` and `_set_cache()`, which are called from both sync and async paths. Holding an `RLock` across `await` points deadlocks any other coroutine that tries to acquire the same lock on the same thread. The correct primitive is `asyncio.Lock` for async callers.

---

### 20. `stream_enabled()` reads env var on every call (`streaming/manager.py`)

```python
def stream_enabled(self) -> bool:
    raw = (os.getenv("ORKET_STREAM_EVENTS_V1", "false") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}
```

This is called on the hot path (per turn). `os.getenv()` on every invocation is unnecessary; the value should be resolved once at construction time and cached.

---

### 21. `marshaller_v0.py` emits a SHA-256 hash digest as a TOKEN_DELTA

```python
await interaction_context.emit_event(
    StreamEventType.TOKEN_DELTA,
    {"delta": hashlib.sha256(str(result).encode()).hexdigest()[:16], ...},
)
```

`TOKEN_DELTA` events carry incremental text to be rendered to users. Emitting a hex digest here means any consumer that renders token deltas will display `a3f9c12b8e4d7f01` to the user. This is semantically wrong and will confuse any frontend that naively streams deltas.

---

### 22. `ConfigPrecedenceResolver.SECTION_KEYS` is shared mutable class state

```python
class ConfigPrecedenceResolver:
    SECTION_KEYS: set[str] = {"mode", "memory", "voice"}

    @classmethod
    def register_section(cls, name: str) -> None:
        cls.SECTION_KEYS.add(section_name)
```

`register_section()` modifies the class-level set, which is shared across all instances and all tests. A section registered in one test bleeds into all subsequent tests. This should be instance state or a frozen class constant.

---

### 23. `async_card_repository.py` calls `_ensure_initialized()` on every read

`_execute()` always calls `_ensure_initialized()` which runs `CardMigrations.ensure_initialized()` on every single read/write operation. Even if migrations are idempotent, the overhead of checking migration state per query on a hot repository is significant. Should be guarded by an instance-level `_initialized` flag with a proper async lock.

---

### 24. `GiteaStateTransitioner.validate_transition()` hardcodes `WaitReason.SYSTEM`

```python
if requested in {CardStatus.BLOCKED, CardStatus.WAITING_FOR_DEVELOPER}:
    wait_reason = WaitReason.SYSTEM
```

The wait reason is hardcoded to `SYSTEM` regardless of what the actual caller intended. If the state machine enforces wait_reason semantics, this silently overrides legitimate business reasons (e.g., `WAITING_FOR_DEVELOPER` due to a human review request might have a different wait reason).

---

### 25. `build_packet1_provider_lineage()` always marks first two providers as `present: True` (`streaming/session_context.py`)

The lineage record claims the first two providers (`host_continuity`, `turn_request`) are always `"present": True` without checking whether the fields are actually populated. An empty `session_params` or `input_config` will still show `present: True` in the lineage, undermining its correctness as an audit trail.

---

### 26. `SlidingWindowRateLimiter` is per-process only (`webhook_server.py`)

The limiter lives in module memory. With multiple uvicorn worker processes, each worker enforces its own limit independently. Effective rate is `N * limit` for N workers, making the configured limit meaningless in any production multi-worker deployment.

---

### 27. `_load_required_review_json_object()` swallows `FileNotFoundError` into a generic `ValueError` (`application/review/bundle_validation.py`)

```python
try:
    payload = _load_review_json(path)
except FileNotFoundError as exc:
    raise ValueError(f"{field_name}_missing") from exc
```

All error distinctions (missing file vs. malformed JSON) are collapsed into `ValueError` with an error-code string. Callers cannot distinguish "the file wasn't there" from "the file contained bad JSON" without parsing the string, which is brittle.

---

### 28. `_deep_merge` in `policy_resolver.py` does not validate override types before merging

If a policy file sets a key to `null` or a scalar that was previously a dict, `_deep_merge()` will silently replace the entire subtree with the scalar. A malformed policy file can zero out large sections of the default policy with no warning.

---

### 29. `LocalModelProvider` leaks `httpx.AsyncClient` on construction failure or test teardown

The client is constructed in `__init__` and assigned to `self.client`. There is a `_closed` flag but no `__del__`, no context manager, and no `aclose()` method visible. If the provider is constructed and then discarded (e.g., on configuration error), the underlying connection pool and file descriptors leak.

---

### 30. `agent_factory.py` double-reports tool scope errors

```python
log_event("seat_tool_scope_empty", ..., level="error")
raise AgentConfigurationError(...)
```

The error is both logged at `error` level and raised as an exception. The caller will likely log the exception too, producing duplicate error entries in observability systems for the same event.

---

### 31. `get_eos_sprint()` has a hardcoded base date that silently drifts wrong (`utils.py`)

```python
base_date = datetime(2026, 2, 2, tzinfo=base_tz)
base_q, base_s = 1, 6
```

The sprint calculation is anchored to a specific date that must be manually updated as the project evolves. If this function is used past the expected date range without the constant being updated, it silently returns wrong sprint labels. The base date should be configuration-driven or derived from a canonical sprint schedule.

---

### 32. `cards.py` `update_issue_status()` has brittle context-spreading

```python
gate_context = {**context, "current_status": current_status.value, "card_type": card_type.value}
```

If `context` already has `current_status` or `card_type` keys, the spread `**context` puts them in first and the explicit keys override them — which is the intended behavior. However, if `context` has keys that conflict with internal gate fields in the future (e.g., `roles`), behavior will silently change. This should use explicit key assignment rather than dict unpacking.

---

### 33. `InteractionContext.session_params()` deep-copies on every access

```python
def session_params(self) -> dict[str, Any]:
    return deepcopy(self._session_params)
```

`deepcopy` of a potentially large params dict is called every time `session_params()` is accessed. If this is called frequently per turn (e.g., in tool handlers), it accumulates significant GC pressure. The params should be exposed as a read-only view or frozen at construction.

---

### 34. `AsyncDualModeLedgerRepository` protocol errors are silently swallowed

Protocol ledger write failures emit parity telemetry but are never surfaced to callers:

```python
protocol_error = await self._try_protocol_write(...)
if protocol_error is None:
    ...
else:
    await self._update_intent(intent_id, protocol_error=protocol_error)
await self._emit_parity(phase="start_run", ...)
```

The protocol ledger can drift from SQLite permanently with no caller-visible error. Only someone watching parity telemetry will notice the divergence.

---

### 35. `_parse_bool()` in `local_prompting_policy.py` treats any non-truthy string as `False` without warning

```python
def _parse_bool(value: Any) -> bool:
    token = str(value or "").strip().lower()
    return token in {"1", "true", "yes", "on", "enabled"}
```

The string `"falze"` (a typo) silently returns `False`. There is no validation that the input is one of a recognized set. Configuration errors will go undetected.

---

### 36. `GiteaWebhookHandler` constructs and stores a redundant `httpx.AsyncClient` that is never used for actual requests

```python
self.client = httpx.AsyncClient(auth=self.auth, timeout=10.0)
```

`GiteaHTTPClient.request_response()` creates its own `AsyncClient` per request. `self.client` in `GiteaWebhookHandler` is never passed to or used by `GiteaHTTPClient`. It is a dead object that consumes resources and is never closed (no `aclose()` call in the visible `close()` method).

---

### 37. `review/lanes/model_assisted.py` catches bare `(RuntimeError, ValueError, OSError)` from the model provider

```python
try:
    raw_payload = provider(request)
except (RuntimeError, ValueError, OSError) as exc:
    advisory_errors.append(f"model_provider_error:{exc}")
    return ModelAssistedCritiquePayload(...)
```

Swallowing `RuntimeError` and `ValueError` from a provider is dangerous — these could be programming errors (bad argument types, assertion failures) masquerading as advisory failures. The lane will return an empty critique instead of surfacing the bug. At minimum, unexpected exception types should be re-raised or logged at error level.

---

### 38. `workloads/model_stream_v1.py` — `_build_provider()` raises for "real" mode with a confusing error

```python
if mode == "real":
    raise ValueError("Real provider construction is async-only. Use run_model_stream_v1.")
```

The function is named `_build_provider()` with no indication it's synchronous-only. A caller that doesn't read the error message will be confused. The function should be removed or documented as sync-only in its signature, and the async path should be the only entry point.

---

### 39. `StreamBus._turn_states` grows without bound

`_turn_states` accumulates one `_TurnBusState` per `(session_id, turn_id)` pair and is never pruned except by explicit `purge_turn()`. In a long-running instance with many sessions, this dictionary grows indefinitely until the process OOMs. There should be a TTL or LRU eviction policy.

---

### 40. `validate_openai_messages()` normalizes roles to lowercase before comparing against an `allowed_roles` set that already contains lowercase values — but the comparison string is computed on the wrong value

```python
role = str(message.get("role") or "").strip().lower()
if role not in allowed_roles:
    invalid.append(f"{index}:{role or '<missing>'}")
```

The appended role is already lowercased. If the original message had `"role": "System"` it will be reported as `"0:system"` rather than `"0:System"`. This makes the diagnostic output misleading — the reported role doesn't match what was in the original message.

---

## 🔵 Low — Style & Hygiene

### 41. `_ns_to_ms()` at the bottom of `openai_compat_runtime.py` is an empty stub

```python
def _ns_to_ms(value: Any) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    # falls through — returns None implicitly
```

The conversion logic is missing. This function returns `None` for valid numeric values, silently producing wrong timing data wherever it's used.

---

### 42. Module-level global assignment `runtime_state = GlobalState()` in `state.py` makes testing painful

The singleton is initialized at import time. Tests that want a fresh `GlobalState` must either import before setting up test state or patch `state.runtime_state` with a fresh instance. There's no factory function, no `reset()` method, and no dependency injection entry point.

---

### 43. `utils.py` `get_current_level()` uses a module-level global tuple as a cache

```python
_current_level_cache: tuple[str, int] | None = None
```

Module-level mutable state again. The cache is invalidated via `reset_current_level_cache()` but that function must be called manually. In tests that change `ORKET_LOG_LEVEL` mid-run, the cached value will be stale.

---

### 44. `review/run_service.py` `_generate_ulid()` uses module-level global state with a threading lock — not async-aware

The `_ulid_lock` is a `threading.Lock`, not an `asyncio.Lock`. If `_generate_ulid()` is called from async code (directly or via `asyncio.to_thread`), the threading lock works correctly but is inconsistent with the rest of the async codebase's locking strategy.

---

### 45. `schema.py` `IssueMetrics.grade` is typed as `str` with a comment listing valid values but no enforcement

```python
grade: str = "Pending"  # e.g. "Shippable", "Non-Shippable"
```

This should be a `Literal["Shippable", "Non-Shippable", "Pending"]` or an enum. Currently any string is accepted silently.

---

*45 issues found across critical security, correctness, design, and hygiene categories.*
