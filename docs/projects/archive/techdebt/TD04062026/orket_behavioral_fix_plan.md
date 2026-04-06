# Orket — Behavioral Truth Fix Plan (Round 3)

Last updated: 2026-04-06
Status: Completed
Owner: Orket Core

> Remediation plan for the 14 findings in `orket_behavioral_review_round3.md`. Organized by severity. Each fix includes the exact behavioral contract that must hold after the fix, and a suggested test to prove it.

---

## 🔴 Critical Fixes — Ship Before Any Release

---

### BT-1: Fix `TURN_FINAL` Authority Signal in Both Workload Paths

**Finding:** #1  
**Files:** `orket/extensions/workload_executor.py` — `run_legacy_workload`, `run_sdk_workload`

**Required behavioral contract after fix:** A `TURN_FINAL` event emitted with a non-empty summary must carry `"authoritative": True` when the workload has completed successfully and a commit has been or will be requested. A non-authoritative `TURN_FINAL` must only be emitted for intermediate progress updates, not final output.

**Steps:**
1. In both `run_legacy_workload` and `run_sdk_workload`, change the `TURN_FINAL` emit to `"authoritative": True`.
2. Audit all other `TURN_FINAL` emit sites across the codebase for consistency. A grep for `StreamEventType.TURN_FINAL` will find them.
3. If a workload must emit a non-authoritative final event (e.g., for progressive rendering), add a distinct `TURN_PROGRESS_FINAL` event type that carries partial output — do not overload `TURN_FINAL`.

**Test to prove it:**
```python
# After run_sdk_workload completes:
# Collect all TURN_FINAL events from the stream bus
# Assert every TURN_FINAL with a non-empty summary has authoritative=True
# Assert the commit was requested after the TURN_FINAL
```

---

### BT-2: Remove `AttributeError` from Protocol Write Catch; Fix Class Name

**Finding:** #2  
**File:** `orket/adapters/storage/async_dual_write_run_ledger.py`

**Required behavioral contract after fix:** A structurally broken protocol repo (wrong type, missing method, misconfigured object) must propagate as an exception, not be silently logged and swallowed. Transient write failures (`OSError`, application-level `ValueError`) may still be caught and logged.

**Steps:**
1. Remove `AttributeError` from the `_try_protocol_write` exception catch list. The catch should be `(RuntimeError, ValueError, OSError)` only.
2. Let `TypeError` propagate — a `TypeError` in an async write call also suggests structural misconfiguration (wrong argument type for the repo's interface).
3. Rename the class from `AsyncProtocolPrimaryRunLedgerRepository` to `AsyncDualModeLedgerRepository`. Update the docstring to accurately state that `primary_mode` defaults to `"sqlite"`.
4. Update all construction sites to use the new name.

**Test to prove it:**
```python
# Construct AsyncDualModeLedgerRepository with a mock protocol_repo that raises AttributeError
# Call start_run()
# Assert AttributeError propagates — it is NOT caught
```

---

### BT-3: Pass Real Role and Issue ID to iDesign Validator

**Finding:** #3  
**File:** `orket/core/policies/tool_gate.py` — `_validate_file_write`

**Required behavioral contract after fix:** The `ExecutionTurn` passed to `iDesignValidator.validate_turn()` must carry the actual role and issue_id from the execution context, not placeholder strings.

**Steps:**
1. Extract `role` and `issue_id` from the `context` dict before constructing `temp_turn`:
   ```python
   actual_role = str(context.get("role") or context.get("current_role") or "unknown")
   actual_issue_id = str(context.get("issue_id") or context.get("card_id") or "unknown")
   temp_turn = ExecutionTurn(
       role=actual_role,
       issue_id=actual_issue_id,
       tool_calls=[ToolCall(tool="write_file", args=args)],
   )
   ```
2. Audit `context` key names against the callers of `ToolGate.validate()` to confirm the right keys.
3. If `role` or `issue_id` are genuinely unavailable at the gate call site, document that explicitly and add a contract test that checks the gate still correctly rejects policy violations even without identity context.

**Test to prove it:**
```python
# Call _validate_file_write with context={"role": "coder", "issue_id": "iss-001", "idesign_enabled": True}
# Assert iDesignValidator.validate_turn receives a turn with role="coder", issue_id="iss-001"
# (use a mock or spy on validate_turn)
```

---

## 🟠 High Fixes — Ship in the Next Sprint

---

### BT-4: Surface Budget Exhaustion Separately From Validity in `run_round`

**Findings:** #4, #5 (and #13 for renaming)  
**File:** `orket/kernel/v1/odr/core.py`

**Required behavioral contract after fix:**
- `MAX_ROUNDS` must fire whenever `max_hit` is true, regardless of validity verdict on the terminal round.
- `UNRESOLVED_DECISIONS` must only fire when pending decisions persisted across multiple rounds, not just the terminal one.
- The round record must include `"max_hit": bool` as an explicit field.

**Steps:**
1. Lift `max_hit` out of the validity branch:
   ```python
   if max_hit:
       stop_reason = "MAX_ROUNDS"
   elif semantic["validity_verdict"] == "valid":
       if circ_hit:
           stop_reason = "LOOP_DETECTED"
       elif diff_hit:
           stop_reason = "STABLE_DIFF_FLOOR"
   else:
       if circ_hit or diff_hit:
           if semantic["pending_decision_count"] > 0:
               stop_reason = "UNRESOLVED_DECISIONS"
           else:
               stop_reason = "INVALID_CONVERGENCE"
   ```
2. Add `"max_hit": max_hit` to the round record dict.
3. For `UNRESOLVED_DECISIONS`: gate it on `semantic["pending_decision_count"] > 0` only when `circ_hit or diff_hit` — not when `max_hit` alone caused termination.
4. Rename `ReactorConfig.max_rounds` to `max_attempts` with a deprecation alias for `max_rounds`. Update all callers and docs.

**Tests to prove it:**
```python
# Scenario A: 8 consecutive invalid rounds → stop_reason == "MAX_ROUNDS", not "INVALID_CONVERGENCE"
# Scenario B: 7 invalid rounds, 1 valid round → stop_reason == "MAX_ROUNDS"
# Scenario C: 2 valid stable rounds before max_rounds → stop_reason == "STABLE_DIFF_FLOOR"
# Scenario D: invalid convergence on round 6 (before max) → stop_reason == "INVALID_CONVERGENCE"
```

---

### BT-5: Treat Ledger Corruption as a Hard Error in `promote_run`

**Finding:** #6  
**File:** `orket/kernel/v1/state/promotion.py` — `_load_last_promoted_turn_id`

**Required behavioral contract after fix:** A corrupted (unparseable) run ledger must surface as `E_PROMOTION_FAILED`, not silently reset to `"turn-0000"`. A missing ledger file (first promotion ever) must remain `"turn-0000"`.

**Steps:**
1. Split the exception handling:
   ```python
   if not path.exists():
       return "turn-0000"   # legitimate first-run case
   try:
       data = _read_json(path)
   except OSError as exc:
       raise PromotionError(E_PROMOTION_FAILED, f"ledger I/O error: {exc}") from exc
   except (json.JSONDecodeError, TypeError) as exc:
       raise PromotionError(E_PROMOTION_FAILED, f"ledger corrupt: {exc}") from exc
   ```
2. Verify `PromotionError` (or equivalent) is a defined exception in `promotion.py` or add it.
3. Add a `repair_run_ledger(root, force_turn_id)` function that allows operators to explicitly advance the ledger past a missing or corrupted turn, with a mandatory acknowledgment parameter.

**Test to prove it:**
```python
# Write a corrupted (truncated JSON) run_ledger.json to the committed index path
# Call promote_run() for any turn
# Assert PromotionError/E_PROMOTION_FAILED is raised, NOT a silent reset
```

---

### BT-6: Fix Sync File I/O in `_load_turn_receipts`

**Finding:** #7  
**File:** `orket/runtime/protocol_receipt_materializer.py`

**Required behavioral contract after fix:** No synchronous file I/O on the async thread in `materialize_protocol_receipts`. All file reads must use `aiofiles` or `asyncio.to_thread`.

**Steps:**
1. Convert `_load_turn_receipts` to `async def`:
   ```python
   async def _load_turn_receipts(*, workspace: Path, session_id: str) -> list[dict[str, Any]]:
       rows = []
       for source_index, path in enumerate(_protocol_receipt_files(...), start=1):
           async with aiofiles.open(path, "r", encoding="utf-8") as handle:
               content = await handle.read()
           for line_index, line in enumerate(content.splitlines(), start=1):
               ...
   ```
2. Propagate the `async` qualifier up through `materialize_protocol_receipts`.
3. Update all callers to `await` the call.

**Test to prove it:**
- Run the async ASYNC lint rules (`ruff --select ASYNC`) after the fix — they should catch any remaining sync I/O calls in async context.
- Add a test that calls `materialize_protocol_receipts` in a tight event loop with a mock file and asserts no blocking occurs (use `asyncio.get_event_loop().run_until_complete` with a 10ms timeout).

---

## 🟡 Medium Fixes — Schedule This Sprint or Next

---

### BT-7: Separate Connect and Stream Timeouts in `LocalModelProvider`

**Finding:** #8  
**File:** `orket/adapters/llm/local_model_provider.py`

**Required behavioral contract after fix:** Long-running token streams must not be terminated by a connection timeout. Connection establishment must fail fast. Read timeouts per chunk must be set to a generous but finite value.

**Steps:**
1. Replace:
   ```python
   timeout=httpx.Timeout(timeout=max(1.0, float(self.timeout)))
   ```
   With:
   ```python
   timeout=httpx.Timeout(
       connect=30.0,
       read=max(1.0, float(self.timeout)),
       write=30.0,
       pool=10.0,
   )
   ```
2. Expose `connect_timeout_seconds` as a separate `LocalModelProvider` parameter (default `30.0`).
3. Document the behavior difference between ollama and openai_compat timeout handling in the class docstring.

---

### BT-8: Add Fallback Object Scan to `check_link_integrity`

**Finding:** #9  
**File:** `orket/kernel/v1/state/lsi.py`

**Required behavioral contract after fix:** An object that exists in `objects/` or `triplets/` but is not yet indexed in `refs/by_id` must NOT be classified as an orphan.

**Steps:**
1. When `check_link_integrity` fails to find a ref target in `refs/by_id`, scan `triplets/` for the corresponding stem directly before emitting `E_LSI_ORPHAN_TARGET`.
2. If the triplet is found in `triplets/` but not in `refs/by_id`, emit `I_REF_INDEX_LAG` (a new informational code) rather than an orphan error.
3. Add a test: write a triplet without updating `refs/by_id`, run `check_link_integrity`, assert no orphan error is emitted.

---

### BT-9: Add Force-Skip Recovery to `promote_run`

**Finding:** #10  
**File:** `orket/kernel/v1/state/promotion.py`

**Required behavioral contract after fix:** An operator must be able to explicitly skip over a missing or unrecoverable turn and continue promoting subsequent turns.

**Steps:**
1. Add `repair_run_ledger(root: str, *, force_turn_id: str, acknowledge: str) -> None` where `acknowledge` must equal a specific sentinel string (e.g., `"I_ACKNOWLEDGE_DATA_GAP"`) to prevent accidental use.
2. The function writes `force_turn_id` as `last_promoted_turn_id` in the ledger, bypassing the missing turn.
3. Document the data integrity implications clearly in the function docstring.

---

### BT-10: Require Structured Removal Authorization in `_constraint_demotion_violations`

**Finding:** #11  
**File:** `orket/kernel/v1/odr/semantic_validity.py`

**Required behavioral contract after fix:** An `[REMOVE]` patch must only authorize the removal of a constraint if the patch text explicitly references the constraint token being removed, not just happens to contain it as a substring.

**Steps:**
1. Change `authorized_removals` matching from substring search to exact token intersection:
   ```python
   authorized_tokens = set()
   for patch_text in authorized_removals:
       authorized_tokens.update(tokenize(patch_text))  # existing normalize_text/tokenize
   ```
2. A constraint token is authorized for removal only if it appears in `authorized_tokens`.
3. Alternatively, define a structured `[REMOVE: <token>]` format and only match explicit `REMOVE:` annotations against constraint tokens.
4. Add a test: a patch saying "remove the encryption default" must NOT authorize removal of a "must encrypt all data" constraint — only a patch containing "encrypt" OR "all data" as the target token should.

---

## 🔵 Low Fixes — Batch Into Hygiene Sprint

---

### BT-11: Rename `max_rounds` to `max_attempts` in `ReactorConfig`

**Finding:** #13  
**File:** `orket/kernel/v1/odr/core.py`

1. Add `max_attempts: int = 8` to `ReactorConfig` with a deprecated `max_rounds` alias.
2. Update `run_round` to use `cfg.max_attempts`.
3. Add a `# Deprecated: use max_attempts` warning if `max_rounds` is accessed.
4. Update all benchmark config JSON files that use `max_rounds` over one sprint cycle.

---

### BT-12: Distinguish Parity Check Crash from Real Parity Mismatch

**Finding:** #14  
**File:** `orket/adapters/storage/async_dual_write_run_ledger.py`

1. In the `_emit_parity` error catch block, add `"parity_check_error": True` to the emitted event payload.
2. In the normal mismatch path, add `"parity_check_error": False`.
3. Update any monitoring or dashboard queries that read `parity_ok: False` to also check `parity_check_error`.

---

## Verification Checklist

Closeout status:
1. All BT-1 through BT-12 remediation items are complete in code.
2. Structural proof for the behavior packet was refreshed on 2026-04-06 before archive closeout.
3. Archive authority for this cycle is `docs/projects/archive/techdebt/TD04062026/`.

Before closing this plan, the following must be demonstrable:

| ID | Verification |
|----|-------------|
| BT-1 | `TURN_FINAL` with summary always has `authoritative: True` in workload paths (contract test) |
| BT-2 | `AttributeError` in protocol repo propagates; class renamed (unit test + grep for old name) |
| BT-3 | iDesign validator receives actual role/issue_id from context (spy test) |
| BT-4 | 8 invalid rounds produces `MAX_ROUNDS`, not `INVALID_CONVERGENCE` (unit test) |
| BT-5 | Corrupted ledger raises hard error, not silent reset (unit test with bad JSON ledger) |
| BT-6 | No synchronous `open()` calls in `materialize_protocol_receipts` (ruff ASYNC check + asyncio timeout test) |
| BT-7 | Long stream survives 300s read; connect fails fast at 30s (integration test with mock server) |
| BT-8 | Non-indexed object does not produce orphan error (unit test with partial staging state) |
| BT-9 | `repair_run_ledger` advances past missing turn without re-promoting earlier turns (unit test) |
| BT-10 | Short removal patch does not authorize unrelated constraint removal (unit test) |
| BT-11 | `max_rounds` in existing benchmark configs still works via alias; `max_attempts` works (regression suite) |
| BT-12 | Parity crash and parity mismatch produce distinct log fields (unit test on `_emit_parity`) |
