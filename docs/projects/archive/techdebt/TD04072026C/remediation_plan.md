# Orket — Remediation Plan

> Addresses all 28 code issues (C1–C28) and 18 behavioral issues (B1–B18) from the paired reviews.
> Items are grouped by theme and ordered by risk. Each item specifies the file(s), the fix, and the acceptance criterion.

---

## Phase 1 — Correctness Blockers (do these first; all are silent data-loss or correctness bugs)

### P1-A: Fix split-migration try/except (`card_migrations.py`) → **C1, C2**

**File:** `orket/adapters/storage/card_migrations.py`

**Fix:** Replace the shared `try/except` block covering both `retry_count` and `max_retries` `ALTER TABLE` with two separate `contextlib.suppress(aiosqlite.OperationalError)` calls, one per statement — consistent with the `depends_on_json` migration above it. Remove the instance-level `self.initialized` flag entirely and replace with a per-connection `PRAGMA user_version` check so migration state is stored in the database file, not in the Python object.

**Acceptance:** A test that creates a fresh `AsyncCardRepository`, runs migrations, drops the `retry_count` column manually via raw SQL, creates a new `AsyncCardRepository` instance pointing to the same file, and verifies migrations are re-applied correctly.

---

### P1-B: Fix `AsyncSessionRepository._initialized` flag (`async_repositories.py`) → **C3**

**File:** `orket/adapters/storage/async_repositories.py`

**Fix:** Replace the Python-object `_initialized` flag with the same `PRAGMA user_version` pattern. Alternatively, use `CREATE TABLE IF NOT EXISTS` exclusively (which is already idempotent) and remove the flag altogether since it provides no correctness benefit and creates false safety.

**Acceptance:** Test creates session repo, wipes DB file, creates new session repo pointing to same path, and verifies `start_session` succeeds.

---

### P1-C: Replace hand-rolled ULID (`run_service.py`) → **C4, C5**

**File:** `orket/application/review/run_service.py`

**Fix:** Remove `_ulid()` entirely. Add `python-ulid` (or `ulid-py`) to `pyproject.toml` and use `ulid.new().str` or equivalent. If adding a dependency is blocked, implement ULID using bit-manipulation per the spec (48-bit timestamp shifted into top 10 Crockford chars, not divided iteratively) and add a unit test that verifies the output against the reference spec test vectors.

**Acceptance:** Unit test asserts that 1000 rapid ULID calls produce monotonically increasing values. Test verifies correct character count (26), valid Crockford alphabet, and that the timestamp component decodes to a value within 1 second of the current time.

---

### P1-D: Fix `publish_checkpoint` no-op (`control_plane_authority_service.py`) → **C16, B12**

**File:** `orket/application/services/control_plane_authority_service.py`

**Fix:** Either (a) wire `publish_checkpoint` to delegate to the record repository (matching `accept_checkpoint` behavior), or (b) remove the method and require callers to call the repository directly. Option (b) is cleaner. Audit all call sites and replace with direct repository saves. Add a test that verifies a published checkpoint is retrievable after a crash-recovery simulation.

**Acceptance:** No test or production call site calls a method named `publish_checkpoint` that does not result in a durable write.

---

### P1-E: Fix `NullControlPlaneAuthorityService` return type mismatch → **C24, B5**

**File:** `orket/agents/agent.py`

**Fix:** Change `NullControlPlaneAuthorityService.append_effect_journal_entry` to return a sentinel `EffectJournalEntryRecord` with zeroed IDs rather than `None`. Log at `warn` level that journaling is disabled when the null seam is used. Update the type annotation to reflect that `journal=None` is accepted but is a degraded mode.

**Acceptance:** Any code that chains `previous_entry=journal.append_effect_journal_entry(...)` passes the sentinel without `AttributeError`. Test asserts the warn log appears exactly once per agent construction when `journal=None`.

---

### P1-F: Fix exception hierarchy (`exceptions.py`) → **C20**

**File:** `orket/exceptions.py`

**Fix:** Change `OrketInfrastructureError` to inherit from `(RuntimeError, OrketError)` via MRO. Change `SettingsBridgeError` to inherit from `OrketError` as well (or from `(RuntimeError, OrketError)`). Audit all `except OrketError` catch sites to verify they now catch lease and settings errors as intended, or add explicit `except (OrketError, RuntimeError)` where the intent was to catch both.

**Acceptance:** `assert issubclass(LeaseNotAvailableError, OrketError)` passes. Existing tests that catch `OrketError` must catch `LeaseNotAvailableError`.

---

## Phase 2 — Security and Credential Safety

### P2-A: Enforce HTTPS for Gitea credentials (`gitea_webhook_handler.py`) → **C6**

**File:** `orket/adapters/vcs/gitea_webhook_handler.py`

**Fix:** In `__init__`, validate that `gitea_url` starts with `https://` unless `allow_insecure=True` is explicitly passed. Raise `ValueError` on plaintext URLs in the absence of the flag. Document that `allow_insecure` is for local development only.

**Acceptance:** Test asserts `GiteaWebhookHandler(gitea_url="http://example.com")` raises `ValueError`. Test asserts `GiteaWebhookHandler(gitea_url="http://...", allow_insecure=True)` succeeds with a warning log.

---

### P2-B: Mask `SecretToken.__str__` (`gitea_state_adapter.py`) → **B14**

**File:** `orket/adapters/storage/gitea_state_adapter.py`

**Fix:** Add `__str__` and `__format__` overrides to `SecretToken` that both return `"***"`. Add a test that verifies `str(SecretToken("mytoken")) == "***"` and `f"{SecretToken('mytoken')}" == "***"`.

**Acceptance:** `SecretToken` in an f-string, `str()`, and `repr()` all produce masked output.

---

### P2-C: Fix `httpx.AsyncClient` resource leak (`gitea_webhook_handler.py`) → **C7**

**File:** `orket/adapters/vcs/gitea_webhook_handler.py`

**Fix:** Add `async def close(self) -> None: await self.client.aclose()` and make `GiteaWebhookHandler` usable as an async context manager via `__aenter__`/`__aexit__`. Wire the close call into the application lifespan (FastAPI/Starlette `on_shutdown` hook or equivalent).

**Acceptance:** Test using `async with GiteaWebhookHandler(...) as handler:` passes without resource warning. Application startup/shutdown integration test verifies no open connections after shutdown.

---

## Phase 3 — Robustness and Error Surface

### P3-A: Guard `int(card_id)` in lease manager → **C8**

**File:** `orket/adapters/storage/gitea_lease_manager.py`

**Fix:** Wrap `int(card_id)` in a try/except and return `None` on `ValueError`, consistent with all other failure paths in `acquire_lease`. Add a log entry at `warn` level identifying the non-numeric card ID.

**Acceptance:** Test passes non-numeric card ID and asserts `None` is returned without exception.

---

### P3-B: Remove `TypeError` from model provider exception handler → **C9**

**File:** `orket/application/review/lanes/model_assisted.py`

**Fix:** Remove `TypeError` from `except (RuntimeError, ValueError, TypeError, OSError)`. Let `TypeError` propagate as a programming error. If the provider callable is user-supplied, document that callers are responsible for ensuring correct calling convention.

**Acceptance:** Test that passes a provider callable with wrong signature raises `TypeError` rather than returning an advisory error.

---

### P3-C: Tighten recovery stop-marker regex and add adversarial tests → **C10**

**File:** `orket/adapters/llm/openai_compat_runtime.py`

**Fix:** Require the stop-marker pattern to appear only after a section-end anchor (e.g., after `### PATCHES` or `### EDGE_CASES` sections) rather than anywhere in the output. Alternatively, elevate the confidence threshold by requiring a colon after the keyword rather than `\b`. Add unit tests with inputs known to false-positive: `"formatting rules"`, `"wait for lock"`, `"let's refactor"`.

**Acceptance:** All adversarial test cases produce untruncated output. Existing recovery tests still pass.

---

### P3-D: Fix `config_root` default in Agent → **C11**

**File:** `orket/agents/agent.py`

**Fix:** Remove the `Path().resolve()` default. Make `config_root` a required parameter, or have the runtime composition layer (`create_engine`, `create_api_app`) always inject the project root explicitly. Document that `None` is not a safe default.

**Acceptance:** Agent construction without `config_root` raises `TypeError` (required arg) or the runtime always injects it. Existing tests that relied on `Path().resolve()` default are updated to pass explicit root.

---

### P3-E: Log warning when seat produces zero tools; don't silently set `strict_config=False` → **C12, B11**

**File:** `orket/agents/agent_factory.py`

**Fix:** After `scoped_tool_map` is computed, add: if empty, log at `error` level identifying team, seat, and role names, and either raise a configuration error or return the seat as a failed agent that will refuse all work. Remove the `strict_config=bool(scoped_tool_map)` pattern.

**Acceptance:** Test with misconfigured role (role name exists in team but not in `role_configs`) asserts a log entry at error level and either raises or returns a no-op agent that raises on turn dispatch.

---

### P3-F: Bound and evict `StreamBus._turn_states` → **C13, C14, C17 (subscriber queues)**

**File:** `orket/streaming/bus.py`

**Fix:**
1. Add a `purge_turn(session_id, turn_id)` method that removes the `_turn_states` entry and drains subscriber queues for that key. Call it from `InteractionSessionManager` after a turn reaches terminal state.
2. Add a guard that prevents `COMMIT_FINAL` from being published twice: set a `commit_final_emitted` flag alongside `terminal_emitted` and raise if it's already set.
3. Set `maxsize` on subscriber `asyncio.Queue` to match `best_effort_max_events_per_turn + bounded_max_events_per_turn`.

**Acceptance:** Long-running integration test verifies `_turn_states` size does not grow after turns complete. Test verifies second `COMMIT_FINAL` raises. Test verifies subscriber queue is bounded.

---

### P3-G: Remove or enforce dead constants in `streaming/manager.py` → **C15**

**File:** `orket/streaming/manager.py`

**Fix:** If `_INTERACTION_MEMORY_SCOPE_BOUNDARY` and `_INTERACTION_REPLAY_BOUNDARY` are not referenced, delete them. If they represent intended constraints, add enforcement code (e.g., validate against them in `InteractionContext` construction) and add tests.

**Acceptance:** `grep -r "_INTERACTION_MEMORY_SCOPE_BOUNDARY" orket/` returns only definition and enforcement sites, no orphan definitions.

---

### P3-H: Add subprocess timeout to `_run_git` and `_git_paths` → **B15, C22**

**Files:** `orket/application/review/snapshot_loader.py`, `orket/application/review/run_service.py`

**Fix:** Add `timeout=30` to both `subprocess.run` calls. Catch `subprocess.CalledProcessError`, `subprocess.TimeoutExpired`, and `FileNotFoundError` and raise a structured `ReviewError` with the command, return code, and stderr captured.

**Acceptance:** Test that mocks git to hang for 60 seconds asserts `ReviewError` is raised within 35 seconds.

---

### P3-I: Warn on malformed review policy file → **C19, B7**

**File:** `orket/application/review/policy_resolver.py`

**Fix:** In `_read_json_file`, catch `json.JSONDecodeError` separately from `OSError` and emit a `log_event` at `warn` level with the file path and error message. Optionally add a schema validation pass after merging using a `pydantic` model for the known top-level keys, emitting a warning for unrecognized keys.

**Acceptance:** Test with malformed JSON in policy file asserts a `warn` log entry is emitted containing the file path. Test with unknown key `"lane"` asserts a `warn` log entry about unrecognized config keys.

---

### P3-J: Fix `EnvironmentConfig` warning type → **B16**

**File:** `orket/schema.py`

**Fix:** Change `DeprecationWarning` to `UserWarning` in `EnvironmentConfig.warn_on_unknown_keys`. Alternatively, add a `strict` mode that raises `ValidationError`. Update any test that used `pytest.warns(DeprecationWarning)`.

**Acceptance:** Test asserts `UserWarning` is raised (visible by default) when unknown keys are present.

---

### P3-K: Add WAL mode pragma to SQLite initialization → **C23**

**Files:** `orket/adapters/storage/card_migrations.py`, `orket/adapters/storage/async_repositories.py`

**Fix:** In both migration/initialization paths, add `await conn.execute("PRAGMA journal_mode=WAL")` as the first operation. This eliminates reader-writer lock contention without requiring isolation-level changes.

**Acceptance:** Concurrent test with 10 reader coroutines and 1 writer coroutine running simultaneously against the same SQLite file completes without `OperationalError: database is locked`.

---

## Phase 4 — Behavioral and Policy Correctness

### P4-A: Block prebuild acceptance on `MAX_ROUNDS` ODR exit without convergence → **B1**

**File:** `orket/application/services/cards_odr_stage.py`

**Fix:** In `_odr_prebuild_accepted`, remove `MAX_ROUNDS` from the acceptable-if-valid path. A run that exits at max rounds without reaching `STABLE_DIFF_FLOOR` or `LOOP_DETECTED` should fail prebuild acceptance unconditionally. Add a separate `odr_max_rounds_accepted` flag to the issue params that an operator can set to explicitly override, requiring intentional opt-in.

**Acceptance:** Test with a simulated ODR run that exits with `stop_reason="MAX_ROUNDS"` and `odr_valid=True` asserts `_odr_prebuild_accepted` returns `False`. Test with explicit override flag asserts `True`.

---

### P4-B: Make PR escalation threshold configurable and idempotent → **C21, B4**

**Files:** `orket/adapters/vcs/gitea_webhook_handlers.py`, `WebhookDatabase`

**Fix:**
1. Extract `3` to a named constant `MAX_PR_REVIEW_CYCLES = 3` at module level, or load from config.
2. Change `cycles == 3` to `cycles >= MAX_PR_REVIEW_CYCLES`.
3. Add an event deduplication check on webhook event ID before processing to make the handler idempotent (store `event_id` in `WebhookDatabase` and skip if already processed).
4. Ensure `WebhookDatabase` is initialized with an explicit path derived from the workspace root, injected at construction time.

**Acceptance:** Test simulates three `changes_requested` reviews and asserts escalation fires. Test simulates the same webhook event delivered twice and asserts escalation fires exactly once.

---

### P4-C: Enforce tool gate in all agent execution paths → **B6**

**Files:** Agent turn execution path (investigate `orket/runtime/execution/execution_pipeline.py` and related)

**Fix:** Audit all paths that dispatch tool calls. Identify any path that calls a tool without going through `tool_gate.check()`. Add the gate check as a decorator or pre-dispatch hook that runs on every tool call regardless of path. Add a test that installs a gate that blocks all tools and verifies no tool call succeeds.

**Acceptance:** Integration test verifies that with a deny-all `ToolGate`, zero tools execute successfully regardless of the dispatch path used.

---

### P4-D: Tighten default `forbidden_patterns` severity → **B9**

**File:** `orket/application/review/policy_resolver.py` (`DEFAULT_POLICY`)

**Fix:** Lower the `TODO|FIXME` pattern severity from `high` to `info` in the default policy. `password\s*=` can remain `high`. Document that operators can raise `TODO|FIXME` to `high` if they want it to block PRs. Alternatively, scope the `TODO|FIXME` pattern to only match outside of comments (which requires a language-aware parser rather than a regex — document this limitation).

**Acceptance:** Test that adds a line `# TODO: add more tests` to a diff asserts finding severity is `info`, not `high`.

---

### P4-E: Fix `odr_max_rounds: 0` silently overriding to 1 → **B10**

**File:** `orket/application/services/cards_odr_stage.py`

**Fix:** Remove `max(1, parsed)`. Allow `0` as a valid value meaning "skip ODR." Update the caller to skip the ODR stage if `_resolve_odr_max_rounds` returns `0`. Log at `info` level when ODR is explicitly skipped by operator config.

**Acceptance:** Test with `odr_max_rounds: 0` in issue params asserts ODR is not invoked and the log contains a skip entry.

---

### P4-F: Persist `WebhookDatabase` to workspace root → **B4 (compound)**

**File:** `orket/adapters/vcs/gitea_webhook_handler.py`

**Fix:** Pass `lifecycle_db_path` (or a webhook-specific path derived from `self.workspace`) to `WebhookDatabase()`. The database must survive process restarts. Add a migration in `WebhookDatabase` to create the schema if absent.

**Acceptance:** Test simulates two review cycles, restarts the handler (creates new instance with same path), delivers a third review cycle, and asserts escalation fires.

---

### P4-G: Address dual-write ledger duplicate-on-recovery → **C17, B13**

**File:** `orket/adapters/storage/async_dual_write_run_ledger.py`

**Fix:** Ensure `start_run` and `finalize_run` in both the SQLite and protocol repositories are idempotent (use `INSERT OR IGNORE` on the run ID, or check existence before insert). Remove the file-based intent log and rely on SQLite WAL atomicity. If parity between the two backends is required for recovery, use the run ID as an idempotency key: always check if the run exists in both backends before replaying.

**Acceptance:** Test simulates a crash mid-dual-write by raising an exception after the first backend write. Recovery (new instance, same path) is verified to produce exactly one record in each backend.

---

## Phase 5 — Documentation and Observability

### P5-A: Document provider timeout semantics (`local_model_provider.py`) → **C27**

**File:** `orket/adapters/llm/local_model_provider.py`

**Fix:** Add a docstring to `LocalModelProvider.__init__` that documents `timeout` as "total response generation timeout in seconds" and `connect_timeout_seconds` as "TCP connection establishment timeout in seconds." Add a validation check that raises `ValueError` if `timeout < connect_timeout_seconds` (a total timeout shorter than the connect timeout is almost certainly a misconfiguration).

**Acceptance:** Constructor raises `ValueError` for `timeout=10, connect_timeout_seconds=30`. Docstring is present and correctly describes both parameters.

---

### P5-B: Emit `STREAM_TRUNCATED` event when producer budget is exhausted → **B8, C28**

**File:** `orket/streaming/bus.py`

**Fix:** When `StreamBus.publish()` drops an event due to budget exhaustion, emit one `STREAM_TRUNCATED` advisory event (if not already emitted for this turn) before dropping. This event is exempt from the budget limit (bounded class, single emission per turn). Consumers can use it to display a "response truncated" indicator.

**Acceptance:** Test that publishes 300 best-effort events for a turn asserts exactly one `STREAM_TRUNCATED` event is in the subscriber queue after the 257th publish call.

---

### P5-C: Log null-journal activation at warn level → **B5 (complement to P1-E)**

Already covered in P1-E. Listed here for traceability.

---

*Total remediation items: 23 action groups covering all 46 issues.*
