# Orket Behavioral Review

**Scope:** Runtime behavior, failure modes, invariant enforcement, and observable system properties. Distinct from the code review — this is about what the system *does*, not just how the code *looks*.

---

## 1. Tool Recovery Is Not Fail-Closed — Silent Partial Execution

**Severity: Critical**

When a model response is truncated or malformed, `ToolParser._recover_truncated_tool_calls` attempts to extract as many tool calls as it can from the wreckage. The design intent is robustness. The actual behavior is a silent partial-execution mode that no caller surface currently distinguishes from a clean run.

**Concrete scenario:** A model is asked to `write_file` and then `update_issue_status`. The response is truncated after the write. Recovery extracts the write call, executes it, and the status update is silently dropped. The card stays `in_progress` indefinitely. No error is surfaced. No retry is triggered. The file on disk and the card state are now diverged.

The system's stated priority #1 is **truthful behavior**. Silent partial execution is incompatible with that priority. The recovery path must either execute all extracted calls or none — and must write an explicit event record either way.

---

## 2. No Per-Tool-Call Timeout — Hung Tool Blocks the Pipeline

**Severity: Critical**

`ToolRuntimeExecutor.invoke` calls the tool function with no timeout:

```python
result = await tool_fn(args, context=resolved_context)
```

A filesystem tool that blocks on a slow network mount, a card repository call that hangs on a locked SQLite connection, or a governance tool waiting on an unresponsive HTTP endpoint will hold the `asyncio` task open indefinitely. Since the pipeline runs turns in sequence, one hung tool call prevents every subsequent card from being processed. There is no circuit breaker, no watchdog, no watchdog-triggered abort. The system silently degrades to zero throughput with no log entry after the hang begins.

---

## 3. Middleware Interceptor Failure Kills the Turn Without Isolation

**Severity: High**

`TurnLifecycleInterceptors` iterates its list and calls each interceptor in sequence. There is no `try/except` around individual interceptor calls. If any interceptor's `before_prompt`, `after_model`, `before_tool`, or `after_tool` raises an unhandled exception, the entire turn aborts and subsequent interceptors are never called. The `on_turn_failure` hook is also not guaranteed to fire in this case — it depends on the outer caller catching the exception and dispatching it.

This means a single badly-behaved middleware can make the entire agent loop unresponsive. Because interceptors are user-extensible, this is a reliability-class bug in the extension surface.

---

## 4. Card State Can Diverge Between SQLite and Gitea Without Detection

**Severity: High**

`AsyncDualModeLedgerRepository` writes to both SQLite and the protocol ledger on every lifecycle event. When one leg fails, `sink_failure_count` is incremented — but there is no alarm threshold, no alert, and no automatic remediation. The primary leg (SQLite) succeeds and the system continues.

More critically: `GiteaStateAdapter` maintains card state independently in Gitea issue bodies. The SQLite repo and Gitea adapter can be mutated by independent code paths (CLI vs. webhook vs. API). There is no sync mechanism, no reconciliation job, and no constraint that prevents SQLite saying a card is `done` while the Gitea issue body still says `in_progress`. The system operates as if these are separate sources of truth with no authority resolution.

---

## 5. Lease Acquisition Returns `None` Silently — Not Uniformly Checked

**Severity: High**

`GiteaStateAdapter.acquire_lease` returns `None` if the card cannot be leased. The contract is defined in `StateBackendContract` which also specifies `None` as the "unavailable" return. Any caller that destructures the result without a `None` check will proceed as if it holds a lease it does not actually hold, execute the card, and write state without the concurrency protection the lease was supposed to provide.

There is no evidence in the reviewed code that all callers uniformly check the `None` case.

---

## 6. `StateMachine` Is Enforced Only on the Governed Path

**Severity: High**

`README.md` acknowledges this directly:

> "Namespace and safe-tooling enforcement are stronger on the governed turn-tool path than on the rest of the runtime."

The practical consequence: cards transitioning through the non-governed path (CLI runner, some agent turns, webhook-triggered flows) can reach `done` from `in_progress` without passing through `code_review` or `awaiting_guard_review`. The state machine exists in code but is only mechanically enforced on a subset of execution paths. The behavioral guarantee of the state machine is therefore weaker than its definition implies.

---

## 7. Tool Gate Validation Runs Synchronous AST Analysis in the Async Hot Path

**Severity: High**

`ToolGate._validate_file_write` calls `ASTValidator.validate_code(content, filename)` which calls `ast.parse(content)` — a synchronous, potentially CPU-heavy operation — inside an async function on the event loop. For large agent-generated files (common in coding tasks), this blocks the event loop for a measurable duration. Under concurrency, this stalls every other coroutine for the duration of the parse. The correct mitigation is `await asyncio.to_thread(ASTValidator.validate_code, content, filename)`.

---

## 8. Agent Turn Has No Turn-Level Retry Logic

**Severity: High**

The agent orchestration loop does not have a retry policy at the turn level. If a model call fails with a transient network error, a timeout, or a malformed response that the parser cannot recover from, the failure propagates up and the card typically transitions to `blocked` or the run is marked failed. There is no exponential backoff, no model-side retry, and no "try a simplified prompt" degradation path. The system is brittle to transient LLM provider failures.

---

## 9. Protocol Ledger Has No Crash-Recovery Guarantee

**Severity: Medium**

The binary append-only ledger (`protocol_append_only_ledger.py`) handles partial tail records gracefully:

```python
if record_end > total_len:
    # Partial tail: end-of-log by contract.
    break
```

But this means a crash mid-write produces a silently truncated log — the partial record is ignored and the next write appends at the point where the partial record began (if the writer resumes correctly). There is no explicit sequence-number gap detection or recovery marker written before the record. The dual-write ledger's recovery code is in `_recover_pending_intents` but this mechanism is only triggered on the next `start_run` call — if the process crashes before then, the recovery is never triggered.

---

## 10. `ConfigLoader` Blocks the Event Loop on Sync Config Loads

**Severity: Medium**

The sync-to-async bridge in `ConfigLoader._run_async` spawns a thread and joins it — which blocks the calling thread. If the calling thread is an async worker (e.g., a FastAPI request handler calling config-dependent code), and the async work is dispatched through `asyncio.to_thread`, the outer event loop remains unblocked — but only if the caller correctly uses `to_thread`. Any direct sync call from an async context will block.

The `_run_async` guard (`raise AssertionError` if on event loop) is the only protection. But this only fires if called *directly* from an async context — not if called through `asyncio.to_thread`, where it incorrectly tries to run `asyncio.run()` inside a new event loop in a thread that already has one running in another thread. The behavior is environment-dependent and fragile.

---

## 11. Sandbox Registry Has No Persistence — Multi-Request Lifecycle Is Broken

**Severity: Medium**

`SandboxRegistry` is instantiated inside `GiteaWebhookHandler.__init__`. In any deployment where the webhook handler is created per request (or the process restarts between webhook events), the registry is empty and has no memory of prior sandbox state. The `_handle_pr_opened` → `_trigger_sandbox_deployment` → (wait) → `_handle_pr_merged` flow assumes the sandbox created in the first event is findable in the second. Without persistence, it is not.

---

## 12. `update_issue_status` Tool Accepts Any String Status — Validated Too Late

**Severity: Medium**

In `CardManagementTools.update_issue_status`:

```python
try:
    new_status = CardStatus(new_status_str)
except ValueError:
    return {"ok": False, "error": f"Invalid status: {new_status_str}"}
```

The validation is correct, but it happens after the card is already fetched from the database. In a busy system, fetching a card by ID when the status string is invalid is a wasted round-trip. More importantly, the agent that produced the invalid status string receives only `{"ok": False, "error": "Invalid status: ..."}` — there is no structured error code that tells the agent *which* statuses are valid. The error is likely to cause the agent to guess again.

---

## 13. Model Family Detection Affects Prompt Dialect — Silent Mis-Dispatch

**Severity: Medium**

As noted in the code review, model family detection in `agent.py` uses substring matching. The behavioral consequence is that a wrong dialect is silently selected, producing a system prompt that uses the wrong DSL format, wrong hallucination guard, wrong tool-call syntax hints. The model will produce output shaped by the wrong dialect contract, leading to higher parse failure rates and more recovery attempts — without any log event indicating the mis-dispatch.

---

## 14. Webhook Payload Validation Has No Schema Enforcement

**Severity: Medium**

`GiteaWebhookHandler` routes events based on keys in the raw payload dict (`payload.get("action")`, `payload.get("pull_request")`, etc.) without validating the overall payload shape against a schema. A malformed or adversarially crafted webhook payload that is missing expected keys will propagate `None` or raise `KeyError` inside handler methods. There is no top-level validation guard.

---

## 15. No Backpressure on the Log Write Queue

**Severity: Low**

`_log_write_queue` is a `queue.SimpleQueue` — unbounded. Under a log storm (e.g., a tight agent loop logging every tool call at high volume), the queue grows without limit until memory is exhausted. The daemon thread writes as fast as disk allows, but if disk I/O is the bottleneck, RAM fills up first.

---

## Summary Table

| # | Area | Behavioral Risk | Severity |
|---|------|-----------------|----------|
| 1 | Tool Parser Recovery | Silent partial execution, card state diverges from disk | Critical |
| 2 | Tool Invocation | No timeout, hung tool halts pipeline | Critical |
| 3 | Middleware Interceptors | Unhandled exception kills turn, no isolation | High |
| 4 | Dual Ledger / Gitea Adapter | State divergence between SQLite and Gitea, no reconciliation | High |
| 5 | Lease Acquisition | `None` return not uniformly checked | High |
| 6 | State Machine Enforcement | Governed path only, non-governed path bypasses machine | High |
| 7 | ToolGate / AST Validation | Sync AST parse blocks event loop | High |
| 8 | Agent Turn Loop | No retry on transient model failures | High |
| 9 | Protocol Ledger | No crash-recovery guarantee for partial writes | Medium |
| 10 | ConfigLoader Sync Bridge | Event-loop blocking in some call patterns | Medium |
| 11 | Sandbox Registry | No persistence, multi-request lifecycle broken | Medium |
| 12 | Status Tool Validation | Error response not machine-actionable by agent | Medium |
| 13 | Agent Dialect Selection | Silent mis-dispatch, elevated parse failure rate | Medium |
| 14 | Webhook Handler | No schema validation on incoming payloads | Medium |
| 15 | Log Queue | Unbounded, memory risk under log storms | Low |
