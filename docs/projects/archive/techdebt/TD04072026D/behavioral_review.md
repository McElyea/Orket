# Orket — Behavioral Review

> This review addresses runtime behavior, system contracts, architectural coherence, and observable correctness — distinct from code-level bugs.

---

## 🔴 Critical Behavioral Failures

### 1. The streaming budget silently starves real model runs

`StreamBus` is configured with `best_effort_max_events_per_turn = 256`. A model generating 512+ tokens fires one `TOKEN_DELTA` event per chunk. Any run exceeding 256 chunks hits the budget and starts dropping token deltas — silently, from the perspective of the generating workload. The `STREAM_TRUNCATED` advisory fires once, but the streaming continues emitting events that go to no subscriber. The user sees a truncated response with no clear error. There is no mechanism to tune this limit per workload type, per model, or per turn context. A 7B model generating a 1,000-token response will routinely exceed this budget.

---

### 2. Memory store is not a vector store — it is keyword frequency matching branded as RAG

`MemoryStore` is documented as "Vector DB Lite" and provides "RAG capabilities." In practice it:

- Splits content on whitespace to create a keyword bag
- Uses set intersection for scoring
- Returns results with the highest count of matching words

There are no embeddings, no semantic similarity, no BM25, no TF-IDF, no stemming, no stopword removal. A search for `"authentication"` returns zero results if stored content says `"auth"`. A query for `"fix the bug"` matches entries containing `"the"` with score 1. This system will give confidently wrong retrieval results for any non-trivial knowledge base. It is architecturally unfit for its stated purpose.

---

### 3. Dual-state system: `GlobalState` and `InteractionManager` track sessions independently with no reconciliation

`state.py` provides `runtime_state: GlobalState` which tracks `active_websockets` and `active_tasks` keyed by session ID. `streaming/manager.py` provides `InteractionManager` which tracks `_sessions` and `_turns` by session ID. These two systems are entirely independent.

A session created via `InteractionManager.start()` is invisible to `GlobalState` and vice versa. A websocket that subscribes to streaming events in one system cannot access session state from the other without external wiring. In production, if a request starts a turn via `InteractionManager` but the WebSocket cleanup path uses `GlobalState.get_tasks()`, no task will be found and no cleanup will occur. The session leaks.

---

### 4. The webhook HMAC validation will reject every legitimate Gitea webhook

As established in the code review, `validate_signature()` compares `hmac.new(secret, payload, hashlib.sha256).hexdigest()` against the raw `X-Gitea-Signature` header value. Gitea sends this header as `sha256=<hexdigest>`. Every legitimate webhook from Gitea will fail validation and be rejected with 401. The system has been silently broken since this was written — every webhook is hitting the rejection path.

---

### 5. Rate limiter provides no protection in multi-worker deployments

`SlidingWindowRateLimiter` is instantiated at module level and lives in process memory. Each uvicorn worker process maintains its own independent limiter state. With 4 workers, the effective rate limit is `4 × ORKET_RATE_LIMIT`. The configured `60 requests/min` becomes `240 requests/min`. The rate limiting provides no meaningful protection against any sustained webhook flood in a production deployment.

---

## 🟠 High — Contract Violations & Architectural Drift

### 6. Agent context injection breaks transcript ordering

`Agent.run()` appends the context dict as the final user message, after the transcript history:

```
system: compiled prompt
user: task description
user: Previous steps: [transcript]
user: Context: {context}
```

The model receives context as the most recent message — the anchor for its response. This means the model's last instruction is raw context data, not the task. A model that weight-anchors on recency will treat the context blob as its primary directive. The transcript history and task description are deprioritized. The intended ordering should be `system → context → task → history` to give the model proper working-memory framing.

---

### 7. Protocol ledger divergence is non-observable by default

`AsyncDualModeLedgerRepository` is configured with `primary_mode="sqlite"` by default. Protocol ledger write failures are caught, stored as parity telemetry, and returned to the caller as `None` (no error). Callers see success. SQLite remains authoritative. The protocol ledger silently accumulates divergence. Only an operator watching parity telemetry dashboards will notice the gap — and that's only if they are watching. There is no circuit breaker, no automatic fallback escalation, no alert trigger.

---

### 8. The review policy's default `password\s*=` forbidden pattern is a false-positive machine

The default policy ships:

```json
{"pattern": "(?i)password\\s*=", "severity": "high"}
```

This fires on `password = get_secret_from_vault()`, `password = None`, `password = args.password`, `test_password = "mock"` — all completely legitimate patterns. Every codebase using standard credential-passing patterns will fail review with `high` severity findings. The policy is producing signal noise that will be trained away by engineers who learn to ignore it.

---

### 9. `ConfigPrecedenceResolver` section key enforcement uses global mutable class state that test suites will corrupt

Any test that calls `ConfigPrecedenceResolver.register_section("custom_section")` permanently adds that section to the class-level `SECTION_KEYS` set for the remainder of the test process lifetime. Test ordering determines whether validation passes or fails. This is a non-deterministic behavioral contract that makes the system unreliable in CI.

---

### 10. `GiteaWebhookHandler` caches a stale handler when environment changes

`_WebhookHandlerProxy` lazily constructs the handler once and caches it forever. If `GITEA_URL` or `GITEA_ADMIN_PASSWORD` change (e.g., via secret rotation in a 12-factor environment), the cached handler continues using the old values until the process restarts. There is a `reset()` method but no mechanism connects it to environment-change events.

---

### 11. `update_issue_status()` transition validation uses a hardcoded workflow profile

```python
transition_service = WorkItemTransitionService(
    workflow_profile=str(context.get("workflow_profile") or "legacy_cards_v1"),
)
```

The workflow profile defaults to `"legacy_cards_v1"` at the tool level. If a card belongs to an epic using a different workflow profile, the transition validation will apply the wrong rules. A transition that should be permitted under the correct profile will be rejected, and vice versa. The workflow profile should be derived from the card's epic or organization config, not defaulted at the tool boundary.

---

### 12. The forbidden pattern lane only records the first match per pattern, not all matches

`run_deterministic_lane()` iterates `added_lines` and breaks on the first match:

```python
for entry in added_lines:
    if regex.search(str(entry.get("text") or "")):
        location = entry
        break
```

A pattern that appears 50 times in a diff generates exactly one finding. A reviewer looking at the finding count cannot gauge the severity of the violation. Pattern matches should enumerate all occurrences up to a configurable maximum.

---

### 13. Token delta streaming behavior is undefined for Ollama tool-call responses

`OllamaModelStreamProvider.start_turn()` yields `TOKEN_DELTA` events for each streamed chunk. When the model outputs a tool call (structured JSON), those tool-call tokens are emitted as raw deltas mixed with any text tokens. The consumer (`model_stream_v1.py`) has no mechanism to distinguish tool-call token deltas from text token deltas. A consumer that naively concatenates deltas will receive partial JSON as display text.

---

## 🟡 Medium — Observable Misbehaviors

### 14. `MemoryStore.remember()` writes every `content` string as a keyword bag without deduplication

Every call to `remember()` adds a new row regardless of whether identical content already exists. A system that calls `remember()` on the same observation multiple times (e.g., on retries) silently inflates the store. Duplicate entries boost retrieval scores artificially — the same memory appearing 10 times will score 10× higher than a unique memory with the same word overlap.

---

### 15. Sprint labels from `get_eos_sprint()` drift incorrectly at DST boundaries

```python
base_tz = date_obj.tzinfo or UTC
base_date = datetime(2026, 2, 2, tzinfo=base_tz)
```

The base timezone is inherited from `date_obj`. If `date_obj` is in `America/Denver` (DST-aware), the base date may be in MST (-7) while a later date is in MDT (-6). The delta calculation uses `.days // 7` on a timedelta, which ignores sub-day clock drift from DST transitions. Sprint boundaries near DST change-over will compute incorrectly.

---

### 16. `InteractionContext.is_canceled()` and `await_cancel()` are not idempotent across turn boundaries

The `cancel_event` is an `asyncio.Event` that is set when a turn is canceled. Once set, it remains set for the lifetime of the `TurnState` object. If a second turn reuses a canceled event (or the cancel state is not cleared between turns), the new turn will immediately appear canceled. The code does not show explicit cancel event reset between turns.

---

### 17. Model-assisted review lane returns empty critique on any provider exception without distinguishing severity

```python
except (RuntimeError, ValueError, OSError) as exc:
    advisory_errors.append(f"model_provider_error:{exc}")
    return ModelAssistedCritiquePayload(summary=[], ...)
```

A transient network error, a permanent misconfiguration, and a Python logic error are all handled identically — an empty critique with an advisory error string. The operator cannot tell whether the lane failed due to a transient issue (retry) or a permanent configuration problem (requires human intervention). Retry logic, error classification, and escalation paths are absent.

---

### 18. `build_team_agents()` silently ignores agents for seats with no role config

If a seat's role name doesn't match any entry in `role_configs`, `_allowed_tools_for_seat()` logs an error and returns an empty set, which then triggers `AgentConfigurationError`. But `_role_names_for_seat()` silently drops blank role names. A misconfigured seat with a whitespace-only role name produces an empty tool set with no visible diagnostic.

---

### 19. Gitea state snapshot uses Gitea issue `body` field as state storage — no size limit enforcement

`GiteaLeaseManager` and `GiteaStateTransitioner` both PATCH the issue `body` field with JSON-encoded snapshots. Gitea imposes a maximum body size. As metadata accumulates (`transition_reason`, `terminal_error`, per-epoch lease history), snapshot size grows. At some threshold, Gitea will reject PATCH requests silently or with a 422 error, breaking state transitions.

---

### 20. `async_card_repository.py` `list_cards()` has no SQL injection guard on dynamically assembled WHERE clause structure

```python
where_clauses.append("build_id = ?")
params.append(build_id)
...
query = f"SELECT * FROM issues {where_sql} ORDER BY ..."
```

The values are safely parameterized. However, the structure of the WHERE clause (`where_sql = f"WHERE {' AND '.join(where_clauses)}"`) is assembled from string literals controlled entirely by the function — not user input. This is safe today but the pattern is dangerous if future developers add `where_clauses.append(user_provided_field)` without noticing that `where_sql` is unparameterized structure, not just values.

---

### 21. `SandboxOrchestrator._allowed_log_services` is a hardcoded set with no extension point

```python
self._allowed_log_services = {"api", "frontend", "db", "database", "pgadmin", "mongo", "mongo-express"}
```

Any sandbox that uses a service name outside this hardcoded set (e.g., `redis`, `worker`, `celery`) cannot have its logs retrieved via the log service. Extension requires source code changes. This should be configuration-driven.

---

### 22. `_generate_ulid()` can overflow silently and raise `OverflowError` in production at year 10889

The overflow check `if timestamp_ms >= _ULID_TIMESTAMP_LIMIT` guards against impossibly large timestamps. This is correct but produces an unhandled `OverflowError` with no fallback, no retry, and no user-visible diagnostic. Callers should be prepared for this exception or ULID generation should degrade gracefully.

---

### 23. `AsyncDualModeLedgerRepository._recover_pending_intents()` is called on every `start_run()` and `finalize_run()` — potentially expensive startup overhead

Intent recovery involves reading a JSON file and replaying any pending operations. Calling it at the top of every ledger write means every `start_run` incurs disk I/O even when there are no pending intents. This should be called once at initialization, not on every write.

---

### 24. The review bundle validation uses string error codes (e.g., `"review_run_manifest_run_id_missing"`) for all control flow

Error handling throughout `bundle_validation.py` uses `raise ValueError("error_code_string")` for control flow. Callers must parse the string to determine the error type. This is a stringly-typed error system that prevents structured error handling, makes error codes invisible to type checkers, and creates implicit coupling between thrower and catcher.

---

### 25. `CommitOrchestrator` writes commit artifacts to disk with no atomic write guarantee

```python
async with aiofiles.open(path, "w", encoding="utf-8") as handle:
    await handle.write(json.dumps(payload, ...))
```

The artifact is written directly to the target path. If the process crashes mid-write, the artifact at `authority_commit.json` will be a partial JSON file. Readers that load this file will get a parse error or corrupted commit record. Commits should use write-to-temp-then-atomic-rename to guarantee either the old or the new file is present, never a partial.

---

*25 behavioral issues identified. Many represent gaps between what the system claims to do and what it actually does at runtime.*
