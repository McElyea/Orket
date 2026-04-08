# Orket — Brutal Code Review

> Reviewed from project dump. Covers `orket/`, `orket_extension_sdk/`, adapters, streaming, kernel, review pipeline, and toolchain. Issues are numbered for reference in the remediation plan.

---

## 1. `card_migrations.py` — Split try/except leaves DB in partial-migration state

```python
try:
    await conn.execute("ALTER TABLE issues ADD COLUMN retry_count INTEGER DEFAULT 0")
    await conn.execute("ALTER TABLE issues ADD COLUMN max_retries INTEGER DEFAULT 3")
except aiosqlite.OperationalError:
    pass
```

Both `ALTER TABLE` calls share one `try/except`. If `retry_count` already exists and `max_retries` does not, the `OperationalError` on the first statement silently swallows the second. `self.initialized = True` is set regardless, so subsequent calls skip migrations entirely. The DB permanently lacks `max_retries`. Contrast with the correct pattern used two lines earlier: one `contextlib.suppress` per statement. This needs to be split into two separate suppressed calls.

---

## 2. `card_migrations.py` — `initialized` flag is instance-level, not DB-level

`CardMigrations.initialized` is set on the Python object. If the object is reused across test runs that wipe and recreate the DB file, migrations are never re-applied. `AsyncCardRepository` stores a single `CardMigrations` instance for its lifetime. In test harnesses that share a repository instance across tests with fresh DB files, the schema simply doesn't exist.

---

## 3. `async_repositories.py` — `AsyncSessionRepository._initialized` flag is connection-unsafe

`_ensure_initialized` checks `if self._initialized: return` but opens a new `aiosqlite.connect()` on every call. The flag reflects "we ran migrations once on some connection" not "the current database file has the schema." Wipe the DB in tests or on first deploy to a new path and the flag stays `True`, silently skipping table creation.

---

## 4. `run_service.py` — Hand-rolled ULID has incorrect bit encoding

```python
value = timestamp_ms
for _ in range(10):
    time_chars.append(alphabet[value % 32])
    value //= 32
```

The algorithm repeatedly divides the raw millisecond timestamp — which is a ~44-bit integer — and extracts 10 Crockford base-32 digits by modulo. The correct ULID time encoding packs the 48-bit timestamp into 10 characters by isolating bits in order from most-significant to least-significant before encoding. This implementation does the reverse (least-significant first), then reverses the list at the end. For timestamps where the value exceeds `32^10` (all current Unix timestamps in milliseconds), the encoding is *wrong* — the upper timestamp bits are silently discarded because `44-bit timestamp // 32^9 ≈ 2`, not the intended top digit. Use the `python-ulid` package or a bit-manipulation approach instead.

---

## 5. `run_service.py` — `time.time()` used for ULID monotonicity

`time.time() * 1000` is wall-clock time, subject to NTP steps and backwards jumps. Two rapid calls can return the same or a decreasing millisecond value, breaking ULID monotonicity guarantees. Use `time.monotonic_ns()` for the entropy component or track the last-issued timestamp and bump it on collision.

---

## 6. `gitea_webhook_handler.py` — BasicAuth sent over plaintext HTTP

```python
self.auth = (self.gitea_user, self.gitea_password)
self.client = httpx.AsyncClient(auth=self.auth, timeout=10.0)
```

The default `gitea_url` is `http://localhost:3000`. Nothing in the constructor enforces HTTPS. Admin credentials are sent in plaintext to any non-TLS URL. The constructor should reject `http://` URLs unless an explicit `allow_insecure` flag is passed, consistent with how `ORKET_ALLOW_INSECURE_NO_API_KEY` is handled elsewhere.

---

## 7. `gitea_webhook_handler.py` — `httpx.AsyncClient` is never closed

`self.client` is created in `__init__` but there is no `async def close()`, `__aenter__`/`__aexit__`, or `lifespan` hook. Every instantiation of `GiteaWebhookHandler` leaks a connection pool. In the API composition path this handler is likely a singleton, but in tests or webhook retries it will accumulate unclosed pools and file descriptors.

---

## 8. `gitea_lease_manager.py` — Unguarded `int(card_id)` raises on non-numeric IDs

```python
issue_number = int(card_id)
```

If `card_id` is a non-numeric string (e.g., `"ISSUE-A3F2"`), this raises `ValueError` with no except clause. Every other failure path in `acquire_lease` returns `None`. This one exception propagates uncaught to the caller and likely surfaces as a 500 or crashes the agent turn. The method contract should either validate the format at entry or wrap the cast.

---

## 9. `model_assisted.py` — `TypeError` caught in provider exception handler

```python
except (RuntimeError, ValueError, TypeError, OSError) as exc:
    advisory_errors.append(f"model_provider_error:{exc}")
```

`TypeError` is a programming error (wrong argument types), not a runtime provider failure. Catching it here masks bugs in the caller or provider implementation. A mistyped call signature on the `ModelProvider` callable will silently produce an empty critique with an advisory error, making it look like a provider timeout rather than a code bug. Remove `TypeError` from the except clause.

---

## 10. `openai_compat_runtime.py` — Stop-marker regex will false-positive on legitimate output

```python
_RECOVERY_STOP_MARKER = re.compile(
    r"(?im)^\s*(?:(?:[*-]|(?:\d+\.))\s+)?(?:\*+)?"
    r"(?:wait\b|let's\b|self-correction\b|..."
    r"formatting\b)"
)
```

The word `formatting` will match any line that starts with "formatting" in any context, including a code review comment that begins "Formatting rules for this module...". `wait\b` will match a code comment like "wait for lock acquisition". These patterns are applied to raw LLM output before section parsing, silently truncating responses that happen to use these words at line starts. There are no tests that verify a false-positive can't occur. The patterns need to be scoped more tightly (e.g., require a preceding bullet, colon, or specific heading structure) and covered by unit tests with adversarial examples.

---

## 11. `agent.py` — `config_root` defaults to CWD at call time, not module directory

```python
self.config_root = config_root or Path().resolve()
```

`Path().resolve()` is the process working directory, not the project or module root. If the application is started from an arbitrary directory (a CI runner, a Docker entrypoint, a relative path invocation), role and dialect asset loading silently fails or loads the wrong files. The default should be explicit and documented — either the user must pass it, or the runtime composition layer must inject it. A default of "wherever the process was started" is a reliable source of "works on my machine" bugs.

---

## 12. `agent_factory.py` — `strict_config=False` for toolless agents silently swallows config errors

```python
agents[seat_name] = Agent(
    ...
    strict_config=bool(scoped_tool_map),
)
```

A seat with no resolved tools gets `strict_config=False`, which means all role and dialect asset load failures are logged and swallowed. A misconfigured role that accidentally resolves to zero tools (e.g., a typo in the tools list) will create a silently broken agent that produces no tool calls and no errors. The factory should log a warning at minimum when a seat ends up with zero tools — empty `scoped_tool_map` should be a loud signal, not quiet permission to skip validation.

---

## 13. `streaming/bus.py` — `_turn_states` dict grows without bound

```python
state = self._turn_states.setdefault(state_key, _TurnBusState())
```

`_turn_states` is keyed by `(session_id, turn_id)` and is never cleaned up. In a long-running process with many sessions, this is a memory leak. There is no TTL, no eviction on session close, and no `purge_turn()` method. After a turn reaches a terminal state, its entry should be removed or the dict should use a `weakref` or LRU structure.

---

## 14. `streaming/bus.py` — `COMMIT_FINAL` can be published multiple times

The terminal-emission guard only prevents *non*-`COMMIT_FINAL` events after terminal:

```python
if state.terminal_emitted and event_type != StreamEventType.COMMIT_FINAL:
    raise ValueError(...)
```

Nothing prevents a second `COMMIT_FINAL` from being published. Subscribers that treat `COMMIT_FINAL` as a once-and-done signal will process two terminal events, potentially triggering double-commit logic in the session manager.

---

## 15. `streaming/manager.py` — Two module-level dicts are dead code

```python
_INTERACTION_MEMORY_SCOPE_BOUNDARY = {
    "session_memory": "host_owned_session_continuity",
    ...
}
_INTERACTION_REPLAY_BOUNDARY = {
    "timeline_view": "inspection_only",
    ...
}
```

No function, method, or test in the visible codebase references these dicts. They are either stale documentation-as-code (should be in a docstring or spec doc) or incomplete enforcement (should be runtime-checked). As dead constants they create the false impression that replay and memory scope boundaries are enforced here.

---

## 16. `control_plane_authority_service.py` — `publish_checkpoint` is a no-op passthrough

```python
def publish_checkpoint(self, *, checkpoint: CheckpointRecord) -> CheckpointRecord:
    return checkpoint
```

This method takes a checkpoint, does nothing with it, and returns it unchanged. The method name implies durable publication. If callers rely on `publish_checkpoint` to record a checkpoint before acting on it, they get a silent no-op. Either this method must delegate to a repository or it must be removed and callers must call the repository directly.

---

## 17. `async_dual_write_run_ledger.py` — Manual file-based WAL is redundant and introduces a new failure mode

The dual-write ledger implements its own intent log on top of SQLite. SQLite already provides WAL durability. The file-based intent mechanism adds a second partial-failure window: if the process crashes after writing the intent file but before clearing it, recovery replays operations that may already be committed, potentially creating duplicate records. The correct pattern for dual-write consistency is a two-phase commit protocol or idempotent record IDs, not a separate intent log.

---

## 18. `cards_odr_stage.py` — Cache comparison will silently miss on type mismatch

```python
if isinstance(cached, dict) and str(cached.get("odr_run_id") or "").strip() == str(run_id).strip():
```

This defensively casts both sides to `str`, which is correct — but only if the cache hit matters. If `run_id` is always passed as a string and cached values are always strings, the `str()` cast is redundant. If they diverge in type in the future, the cache will always miss silently with no log. Given the ODR loop is expensive, a cache miss is a significant performance regression with no diagnostic signal.

---

## 19. `review/policy_resolver.py` — Malformed policy file silently falls back to defaults

```python
except (OSError, json.JSONDecodeError):
    return {}
```

A malformed `.orket/review_policy.json` silently returns an empty dict, which causes the policy to fall back to defaults without any user-visible warning. A developer who misconfigures their policy file will believe it's being applied. At minimum, `json.JSONDecodeError` should produce a warning log with the file path and the parse error.

---

## 20. `exceptions.py` — Inconsistent exception hierarchy breaks catch-all patterns

```python
class OrketInfrastructureError(RuntimeError): ...
class LeaseNotAvailableError(OrketInfrastructureError): ...
class SettingsBridgeError(RuntimeError): ...
```

`OrketInfrastructureError` and `SettingsBridgeError` inherit from `RuntimeError`, not from `OrketError`. Any `except OrketError` catch site will not catch lease failures or settings bridge errors. This is a latent bug — infrastructure failures that should be handled as domain errors will propagate as uncaught `RuntimeError`. `OrketInfrastructureError` should inherit from `OrketError` (or both via MRO), and `SettingsBridgeError` should be evaluated for the same treatment.

---

## 21. `gitea_webhook_handlers.py` — Magic number `3` for escalation threshold

```python
if cycles == 3:
    escalation_error = await self.escalate_to_architect(repo, pr_number)
```

The review cycle escalation threshold is hardcoded to `3` with no configuration point, no constant, and no documentation. If `increment_pr_cycle` is not idempotent (i.e., called multiple times for the same event due to retry), the threshold check with `==` (not `>=`) means a retry bumping the count from 3 to 4 will *never* trigger escalation again. The check should be `>= MAX_PR_REVIEW_CYCLES` where the constant is configurable.

---

## 22. `snapshot_loader.py` — `subprocess.CalledProcessError` from git is unhandled

```python
def _run_git(repo_root: Path, args: list[str]) -> str:
    proc = subprocess.run([...], check=True, ...)
```

`check=True` raises `subprocess.CalledProcessError` on any git failure. None of the callers (`load_from_diff`, `load_from_pr`, etc.) catch this exception. A missing ref, a non-git directory, or a permission error will surface as an unstructured traceback rather than a `ReviewError` with context about what failed and why.

---

## 23. `async_card_repository.py` — Read connections hold implicit transactions on non-WAL SQLite

`aiosqlite.connect()` defaults to deferred transaction mode. Read-only operations that don't call `commit()` hold an implicit read transaction open for the duration of the connection context. On a default SQLite database without WAL, this blocks concurrent writers. The migrations should set `PRAGMA journal_mode=WAL` once during initialization to make concurrent readers and writers safe. Alternatively, read connections should use `isolation_level=None`.

---

## 24. `agent.py` — `NullControlPlaneAuthorityService.append_effect_journal_entry` returns `None`, typed as `EffectJournalEntryRecord`

```python
def append_effect_journal_entry(self, **_kwargs: Any) -> None:
    return None
```

The real `ControlPlaneAuthorityService.append_effect_journal_entry` returns an `EffectJournalEntryRecord`. Any downstream code that calls `journal.append_effect_journal_entry(...)` and chains on the result (e.g., to pass as `previous_entry` to a subsequent call) will receive `None` and `AttributeError` at the next chain access. The null implementation should return a sentinel `EffectJournalEntryRecord` or the type annotation should explicitly reflect the divergence.

---

## 25. `gitea_webhook_handler.py` — `WebhookDatabase()` initialized with no path

```python
self.db = WebhookDatabase()
```

If `WebhookDatabase` defaults to an in-memory SQLite or a CWD-relative path, PR cycle counts are not durable across process restarts. The escalation logic (cycle count reaching 3) depends on persistent state. A restart resets the counter to zero, and a PR that was two cycles deep can avoid escalation indefinitely by triggering a restart. The database path must be explicitly injected or derived from the workspace root.

---

## 26. `review/policy_resolver.py` — Unknown policy keys are silently merged with no validation

`_deep_merge` will accept any key from the repo or user policy file. A typo like `"lane"` instead of `"lanes"` gets merged as a new top-level key that is never read, while the real `"lanes"` key retains its default. The resolved policy has no schema validation step. A `pydantic` model validation pass after merging — or at least a warning for unrecognized top-level keys — would surface misconfiguration early.

---

## 27. `local_model_provider.py` — `connect_timeout_seconds` and `timeout` have different units, undocumented

`timeout: int = 300` is implicitly seconds. `connect_timeout_seconds: float = 30.0` is explicitly named. But `timeout` is passed through to the ollama and openai clients, where the semantic differs (some clients treat it as a total timeout, others as a read timeout). The docstring is absent and no type alias or unit annotation clarifies the distinction. This is a footgun for callers who assume `timeout=30` is 30 seconds of overall call time.

---

## 28. `streaming/bus.py` — Drop notification has no producer-facing feedback path

When a best-effort event is dropped, `publish()` returns `None`. The protocol offers no mechanism for the producer to learn that its event budget is exhausted short of checking the return value. The `StreamBusConfig` limits are per-turn but there is no circuit-breaker that raises or signals the producer to slow down. A runaway agent emitting events will silently lose all events after the first 256 without any runtime feedback.

---

*Total issues: 28*
