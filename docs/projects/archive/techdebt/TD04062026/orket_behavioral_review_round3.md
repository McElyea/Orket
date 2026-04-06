# Orket — Behavioral Truth Code Review (Round 3)

**Date:** 2026-04-05  
**Scope:** Current source tree (v0.4.34). Round 1 (2026-03-17) and Round 2 (2026-03-19) findings are confirmed closed per prior remediation records. This review covers new behavioral mismatches introduced since then.  
**Format:** Each finding states what the code *appears* to do, what it *actually* does, the exact location, and the severity.

---

## Severity Legend

| Level | Meaning |
|---|---|
| 🔴 **Critical** | Silent wrong behavior in the hot path; produces incorrect results or incorrect trust signals under normal use |
| 🟠 **High** | Observable wrong behavior in a realistic scenario; causes incorrect classification, silent data loss, or a broken invariant |
| 🟡 **Medium** | Fragile, misleading, or will produce wrong results in a specific but realistic scenario |
| 🔵 **Low** | Naming drift, minor spec deviation, or unreachable coverage gap that misleads a reader |

---

## 🔴 CRITICAL

---

### 1. `TURN_FINAL` Is Emitted as Non-Authoritative Immediately Before an Authoritative Commit — Both Workload Paths

**Files:** `orket/extensions/workload_executor.py` — `run_legacy_workload`, `run_sdk_workload`

**What it appears to do:** Emit the final turn event to signal completion, then commit the result authoritatively.

**What it actually does:** Both workload paths emit `TURN_FINAL` with `"authoritative": False`, then immediately call `request_commit(CommitIntent(type="turn_finalize", ...))`. The commit is the authoritative record. The `TURN_FINAL` event carries the actual output summary — and claims it's not authoritative.

```python
# run_legacy_workload
await interaction_context.emit_event(
    StreamEventType.TURN_FINAL, {"authoritative": False, "summary": summary}
)
await interaction_context.request_commit(
    CommitIntent(type="turn_finalize", ref=workload.workload_id)
)
```

Any subscriber observing `TURN_FINAL.authoritative` to decide whether to trust the summary — including any frontend that calls `packet1_context()` or displays result state — receives `False` as the authority signal on the actual output event. The commit that follows is authoritative but carries no summary payload. The two signals point in opposite directions: the summary says "not authoritative," the commit says "this is final."

**Concrete failure:** A client that waits for an authoritative `TURN_FINAL` will never see one from a workload execution path. A client that uses the summary from the first `TURN_FINAL` it receives is using a self-described non-authoritative value.

**Fix:** Either emit `TURN_FINAL` with `"authoritative": True` when the result is final, or separate the summary event from the authority signal and document clearly which event carries authoritative output.

---

### 2. `_try_protocol_write` Catches `AttributeError`, Silently Dropping Broken Protocol Repo Failures

**File:** `orket/adapters/storage/async_dual_write_run_ledger.py`

**What it appears to do:** Attempt the protocol write and surface any failure as a parity event so operators can observe it.

**What it actually does:**

```python
except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as exc:
    await self._emit({"kind": "run_ledger_dual_write_error", ...})
    return f"{type(exc).__name__}:{exc}"
```

`AttributeError` is in the catch list. An `AttributeError` in the protocol repo context most likely means the protocol repo object is misconfigured, partially constructed, or missing a method entirely — it is not a transient write failure. Catching it here silently masks a broken protocol repo as a "parity mismatch" log event and lets the run continue using SQLite-only data.

Additionally, the class docstring says "treats the protocol ledger as the primary event source" but `primary_mode` defaults to `"sqlite"`. In the default configuration, `get_run()` reads from SQLite, not the protocol repo. The "protocol primary" claim in the name and docstring is only true when `primary_mode="protocol"` is explicitly passed — which the factory does not do by default.

**Concrete failure:** A completely broken protocol repo (missing `append_event`, wrong type, etc.) produces an `AttributeError` that is caught, logged, and then execution continues. The run finishes with protocol data missing, and the only signal is a `run_ledger_dual_write_error` log event — not an exception, not a run failure.

**Fix:** Remove `AttributeError` from the catch list. `AttributeError` indicates a structural problem with the repo object and should propagate. Separately, rename the class or fix the docstring to match the actual default behavior.

---

### 3. `ToolGate._validate_file_write` Passes a Fabricated `ExecutionTurn` to iDesign Validation

**File:** `orket/core/policies/tool_gate.py` — `_validate_file_write`

**What it appears to do:** Validate the proposed file write against iDesign architectural rules using the turn's execution context.

**What it actually does:**

```python
temp_turn = ExecutionTurn(
    role="unknown",
    issue_id="unknown",
    tool_calls=[ToolCall(tool="write_file", args=args)],
)
if self._idesign_enabled(context):
    violations = iDesignValidator.validate_turn(temp_turn, self.workspace_root)
```

The `ExecutionTurn` is constructed with `role="unknown"` and `issue_id="unknown"`. If `iDesignValidator.validate_turn` uses `turn.role` to determine which architectural rules apply (e.g., a coder role may write to `src/`, an architect role may not), or uses `turn.issue_id` to scope the validation to the right card, the validator receives garbage identity data and its role-based or card-scoped decisions are meaningless.

**Concrete failure:** An agent with role `"operations_lead"` calling `write_file` to write to a protected path will have the iDesign validator run against `role="unknown"`, not `"operations_lead"`. Any rule conditioned on role is bypassed. The iDesign gate passes (or fails) for the wrong reason.

**Fix:** Pass the actual `role` and `issue_id` from `context` into the `ExecutionTurn`. The `context` dict is already available in `_validate_file_write`.

---

## 🟠 HIGH

---

### 4. `run_round` — `MAX_ROUNDS` Is Only Reachable When the Last Round Is Valid

**File:** `orket/kernel/v1/odr/core.py` — `run_round`

**What it appears to do:** Emit `stop_reason = "MAX_ROUNDS"` when the round budget is exhausted.

**What it actually does:**

```python
if semantic["validity_verdict"] == "valid":
    if circ_hit:
        stop_reason = "LOOP_DETECTED"
    elif diff_hit:
        stop_reason = "STABLE_DIFF_FLOOR"
    elif max_hit:
        stop_reason = "MAX_ROUNDS"
else:
    invalid_terminal = circ_hit or diff_hit or max_hit
    if semantic["pending_decision_count"] > 0 and invalid_terminal:
        stop_reason = "UNRESOLVED_DECISIONS"
    elif invalid_terminal:
        stop_reason = "INVALID_CONVERGENCE"
```

`MAX_ROUNDS` only fires when the last round is valid AND `max_hit`. When the model produces invalid output on the final round, exhausting the budget produces `INVALID_CONVERGENCE` (or `UNRESOLVED_DECISIONS`), not `MAX_ROUNDS`.

This means `MAX_ROUNDS` cannot be used to distinguish "ran out of budget" from "converged successfully within budget." Any downstream consumer reading `stop_reason == "MAX_ROUNDS"` to detect budget exhaustion will miss every case where exhaustion occurred on an invalid round — which is the most common failure mode. Budget exhaustion on invalid output is invisible via the stop reason.

**Concrete failure:** A monitoring dashboard that alerts on `MAX_ROUNDS` to detect "ODR is hitting the round ceiling" will miss all cases where the model consistently produces invalid output and exhausts the budget with `INVALID_CONVERGENCE`.

**Fix:** Introduce a separate `max_hit` flag in the record (it is already computed but not surfaced directly), or define `MAX_ROUNDS` as "budget exhausted regardless of validity" and fold it before the validity branch.

---

### 5. `run_round` — `UNRESOLVED_DECISIONS` Is Triggered by Budget Exhaustion, Not Just Actual Pending Decisions

**File:** `orket/kernel/v1/odr/core.py` — `run_round`

**What it appears to do:** Emit `UNRESOLVED_DECISIONS` when the requirement contains genuine open decisions that the model failed to resolve across rounds.

**What it actually does:**

```python
invalid_terminal = circ_hit or diff_hit or max_hit
if semantic["pending_decision_count"] > 0 and invalid_terminal:
    stop_reason = "UNRESOLVED_DECISIONS"
```

`invalid_terminal` is true whenever the round budget is exhausted (`max_hit`), regardless of why. If the semantic validator raises `pending_decision_count > 0` on the last round — even due to a false-positive match in `_UNRESOLVED_ALTERNATIVE_RE` — and the budget is exhausted at the same time, the result is `UNRESOLVED_DECISIONS`. The stop code conflates "budget ran out while the output contained something that looked like an open decision" with "the model genuinely failed to resolve a decision after N attempts."

**Concrete failure:** A requirement that legitimately uses `"either A or B"` as a constraint (e.g., "must support either REST or GraphQL") could produce `pending_decision_count > 0` on multiple rounds. When the budget runs out, the run terminates as `UNRESOLVED_DECISIONS` even though the requirement was semantically valid and the model was converging.

**Fix:** Track `UNRESOLVED_DECISIONS` separately from budget exhaustion. Reserve it for cases where the model actively produced `DECISION_REQUIRED` patches or the pending decision count was non-zero across all valid history rounds — not just the terminal one.

---

### 6. `_load_last_promoted_turn_id` Silently Treats Ledger Corruption as Fresh State

**File:** `orket/kernel/v1/state/promotion.py` — `_load_last_promoted_turn_id`

**What it appears to do:** Load the last promoted turn ID to enforce sequential promotion order.

**What it actually does:**

```python
def _load_last_promoted_turn_id(committed_root: Path) -> str:
    path = _ledger_path(committed_root)
    if not path.exists():
        return "turn-0000"
    try:
        data = _read_json(path)
    except (OSError, json.JSONDecodeError, TypeError):
        return "turn-0000"
```

On any read or parse failure — including a corrupted ledger file, partial write, or truncation — the function returns `"turn-0000"` and continues as if no promotions have ever occurred. A subsequent call to `promote_run` will then attempt to promote starting from turn-0001 again. If the staging directory for turn-0001 still exists (e.g., from a previous run), turn-0001 will be re-promoted, duplicating committed objects.

**Concrete failure:** If the `run_ledger.json` file in the committed index is corrupted by a crash mid-write (partially written JSON), every subsequent promotion resets to `"turn-0000"`, silently re-promoting turns that were already committed. The LSI committed store ends up with duplicate entries for the same stems.

**Fix:** `OSError` may be recoverable with a retry. `json.JSONDecodeError` is data corruption and should surface as `E_PROMOTION_FAILED`, not be silently masked. Distinguish transient I/O errors from data corruption.

---

### 7. `_load_turn_receipts` Uses Synchronous File I/O Inside an Async Function

**File:** `orket/runtime/protocol_receipt_materializer.py` — `_load_turn_receipts`

**What it appears to do:** Load all protocol receipt logs for a session as part of the async materialization pipeline.

**What it actually does:**

```python
for source_index, path in enumerate(_protocol_receipt_files(...), start=1):
    with path.open("r", encoding="utf-8") as handle:   # synchronous open
        for line_index, line in enumerate(handle, start=1):
            ...
```

`path.open()` is synchronous. `materialize_protocol_receipts` is `async def` and called from async context. Each receipt file opens a synchronous file handle and reads line-by-line in a blocking call. On a session with many receipt files (long run with many tool calls), this blocks the event loop for the full duration of the disk read.

**Fix:** Replace with `async with aiofiles.open(path, "r", encoding="utf-8") as handle:` or wrap in `asyncio.to_thread`.

---

## 🟡 MEDIUM

---

### 8. `LocalModelProvider` — A Single Timeout Covers Both Connection and Full Stream Duration

**File:** `orket/adapters/llm/local_model_provider.py` — `__init__`

**What it appears to do:** Apply a configurable timeout to model requests.

**What it actually does:** For the `openai_compat` backend, the httpx client is created as:

```python
self.client = httpx.AsyncClient(
    base_url=self.openai_base_url,
    timeout=httpx.Timeout(timeout=max(1.0, float(self.timeout))),
)
```

`httpx.Timeout(timeout=N)` sets ALL timeout phases (connect, read, write, pool) to `N`. For a streaming generation with `timeout=300`, the provider waits up to 300s for the initial connection AND up to 300s per read chunk. A slow connection that takes 280s to connect followed by a fast model will succeed, but a fast connection followed by a model that generates one token every 30s across 10 tokens will also hit the 300s deadline and fail mid-stream with what looks like a timeout error.

By contrast, the `ollama` backend uses the `ollama.AsyncClient()` which has its own separate timeout management via the ollama library.

**Concrete failure:** Long-running generations that exceed the configured `timeout` — even if actively producing tokens — are terminated with a timeout error indistinguishable from a connection failure.

**Fix:** Use `httpx.Timeout(connect=30.0, read=self.timeout, write=30.0, pool=10.0)` to separate connection establishment from stream read timeouts.

---

### 9. `check_link_integrity` Uses `refs/by_id` as an Orphan Authority, but the Index Can Lag Object Writes

**File:** `orket/kernel/v1/state/lsi.py` — `check_link_integrity`

**What it appears to do:** Detect orphaned refs — links that point to IDs that don't exist in the index.

**What it actually does:** The orphan check resolves ref targets by looking them up in `refs/by_id`, which is a non-owning, best-effort index maintained by `stage_triplet`. The path for writing a triplet is:
1. Write canonical bytes to `objects/<digest>`
2. Write triplet record to `triplets/<stem>.json`
3. Update `refs/by_id/<type>/<id>.json`

If a crash or async interruption occurs between step 2 and step 3, the object and triplet exist on disk but the `refs/by_id` entry was not written. `check_link_integrity` will then classify any links that point to that ID as orphans — even though the data is fully present in the object store.

**Concrete failure:** A run that was interrupted mid-staging will cause every subsequent integrity check to report false orphan errors for the incompletely indexed IDs, blocking promotions unnecessarily.

**Fix:** The integrity check should fall back to scanning the `triplets/` directory directly when a ref target is not found in `refs/by_id`, before declaring an orphan.

---

### 10. `promote_run` Has No Recovery Path for an Out-of-Order Turn — Any Skip Permanently Deadlocks Promotion

**File:** `orket/kernel/v1/state/promotion.py` — `promote_run`

**What it appears to do:** Enforce strict sequential promotion of turns.

**What it actually does:** If turn-0001 staging data is missing or was never written (partial run, failed tool execution, disk error), the promotion returns `E_PROMOTION_OUT_OF_ORDER` for turn-0002 and all subsequent turns. There is no skip, force-promote, or recovery operation exposed. The committed store is permanently stuck.

The only escape hatch is manually deleting the committed run ledger file (resetting to `"turn-0000"`) — which per finding #6 above silently re-promotes everything, risking duplication.

**Concrete failure:** A run where one turn's staging artifacts were never written (e.g., agent was killed mid-turn) cannot have any subsequent turns promoted. The entire run's output is inaccessible from the committed index.

**Fix:** Add a `force_skip_to_turn_id` parameter or a `repair_run_ledger` function that allows an operator to acknowledge the gap and advance the ledger past the missing turn.

---

### 11. `_constraint_demotion_violations` Authorizes Removals via Substring Match Against Full Patch Text

**File:** `orket/kernel/v1/odr/semantic_validity.py` — `_constraint_demotion_violations`

**What it appears to do:** Allow auditor patches marked `[REMOVE]` to authorize the removal of specific constraints from the requirement.

**What it actually does:** The `authorized_removals` list contains full patch text strings (e.g., `"[REMOVE] The encryption requirement is too strict for low-risk data"`). The demotion check compares constraint tokens from the *previous* requirement against these patch texts using substring matching. A patch text string containing the word "encrypt" will authorize the removal of **any** constraint token that contains "encrypt" — regardless of whether the patch actually refers to the same constraint. A patch like `"[REMOVE] The encryption default is redundant"` would authorize the removal of `"must encrypt all user data at rest AND in transit"`.

**Concrete failure:** An auditor patch that says "remove the encryption mention in the assumptions" could inadvertently authorize the removal of a hard security requirement from the requirement field.

**Fix:** Use exact token matching or require patch texts to include the verbatim constraint text being authorized for removal. A structural `[REMOVE: constraint_id]` format would be unambiguous.

---

## 🔵 LOW

---

### 12. `AsyncProtocolPrimaryRunLedgerRepository` Class Name Does Not Match Default Behavior

**File:** `orket/adapters/storage/async_dual_write_run_ledger.py`

**What it appears to do:** Name and docstring both say "treats the protocol ledger as the primary event source."

**What it actually does:** The constructor default is `primary_mode="sqlite"`. In sqlite mode, `get_run()` reads from SQLite. The protocol repo is secondary and fire-and-forget. Protocol-primary behavior requires explicit opt-in that no default factory path exercises.

**Fix:** Rename to `AsyncDualModeLedgerRepository` or `AsyncSQLitePrimaryRunLedgerRepository` to match the actual default. Update the docstring.

---

### 13. `run_round` — `history_v` Grows Unboundedly Including Invalid Rounds, But `max_rounds` Counts Against It

**File:** `orket/kernel/v1/odr/core.py`

**What it appears to do:** `max_rounds` controls the maximum number of convergence attempts.

**What it actually does:** `n = len(history_v)` where `history_v` includes ALL rounds — valid and invalid. `max_rounds` is checked against `n`. The convergence history (`valid_history_v`) has a separate, smaller count. A config of `max_rounds=8, stable_rounds=2` does NOT guarantee the model gets 8 chances at valid output — it gets 8 total attempts including format violations, code leak rejections, and invalid semantic rounds. A model that produces 6 invalid outputs then 2 valid ones hits `stable_count=2` on the 8th round, but the stop reason will be `STABLE_DIFF_FLOOR` (correct) only if the budget isn't exhausted first. If the model produces 7 invalid outputs then 1 valid one, it gets `MAX_ROUNDS` on the 8th round — even though it only had 1 valid attempt.

The comment in the code says `# max_rounds is an attempt budget for the live loop, so invalid rounds count too.` — so this is intentional. But it is not documented in `ReactorConfig` or any public API surface, making `max_rounds` a deceptive parameter name. It should be `max_attempts`.

---

### 14. `_emit_parity` Catches Parity Check Failures and Emits `parity_ok: False` — Indistinguishable from Real Parity Mismatch

**File:** `orket/adapters/storage/async_dual_write_run_ledger.py` — `_emit_parity`

**What it appears to do:** Report whether the SQLite and protocol ledger contents match.

**What it actually does:** If `compare_run_ledger_rows` itself raises an exception, the catch block emits a parity event with `parity_ok: False` and `parity_error` set. This looks identical to a real data mismatch in the log format. An operator reading the log cannot distinguish "parity check found a difference" from "parity check crashed." Both emit `parity_ok: False`.

**Fix:** Add a distinct `parity_check_error: true` field in the error case so operators can tell the difference.

---

## Prior Review Status

All 19 findings from Round 1 (2026-03-17) and all findings from Round 2 (2026-03-19) are confirmed closed:
- `lsi.py` monkey-patch removed; `stage_triplet` is now a clean class method.
- `ReactorState` is `frozen=True`; `run_round` is properly functional.
- `diff_ratio` now uses Jaccard similarity over trigrams, not character length.
- `_unresolved_alternative_RE` no longer matches bare `\bor\b` or `\bmay\b`.
- `check_code_leak` correctly delegates to `detect_code_leak`.
- `AsyncDualWriteRunLedgerRepository` has been renamed to `AsyncProtocolPrimaryRunLedgerRepository` (though per finding #12 above, the name remains misleading).
- `TurnResult.violations` uses `field(default_factory=list)`.

---

## Summary Table

| # | Severity | File(s) | Behavioral Lie |
|---|----------|---------|---------------|
| 1 | 🔴 Critical | `workload_executor.py` | `TURN_FINAL` emitted as non-authoritative before authoritative commit |
| 2 | 🔴 Critical | `async_dual_write_run_ledger.py` | `AttributeError` caught silently; "protocol primary" claim vs sqlite default |
| 3 | 🔴 Critical | `tool_gate.py` | iDesign validation runs against fabricated `role="unknown"` turn |
| 4 | 🟠 High | `odr/core.py` | `MAX_ROUNDS` only reachable on valid last round; budget exhaustion invisible |
| 5 | 🟠 High | `odr/core.py` | `UNRESOLVED_DECISIONS` triggered by budget exhaustion, not genuine decisions |
| 6 | 🟠 High | `promotion.py` | Ledger corruption silently resets to fresh state, enabling re-promotion |
| 7 | 🟠 High | `protocol_receipt_materializer.py` | Synchronous file I/O in async receipt loader |
| 8 | 🟡 Medium | `local_model_provider.py` | Single timeout covers connect and stream; kills long generations |
| 9 | 🟡 Medium | `lsi.py` | Orphan detection trusts stale `refs/by_id` index; false orphans on crash |
| 10 | 🟡 Medium | `promotion.py` | Missing turn permanently deadlocks promotion with no recovery |
| 11 | 🟡 Medium | `semantic_validity.py` | Authorized removal uses substring match; can authorize wrong constraint removal |
| 12 | 🔵 Low | `async_dual_write_run_ledger.py` | Class name "Protocol Primary" contradicts sqlite default |
| 13 | 🔵 Low | `odr/core.py` | `max_rounds` counts all attempts including invalid; misleading parameter name |
| 14 | 🔵 Low | `async_dual_write_run_ledger.py` | Parity check crash emits `parity_ok: False`, indistinguishable from real mismatch |
