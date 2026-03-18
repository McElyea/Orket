# Orket — Behavioral Truth Code Review

Last updated: 2026-03-17  
Status: Archived review snapshot  
Owner: Orket Core

**Date:** 2026-03-17  
**Scope:** Runtime semantics, control flow, async behavior, fallbacks, and test fidelity. Architectural/style issues excluded unless they directly cause incorrect behavior.  
**Format:** Each finding states what the code *appears* to do, what it *actually* does, the exact location, and the severity.

---

## Severity Legend

| Level | Meaning |
|---|---|
| 🔴 **Critical** | Silent data corruption, crash path, or guaranteed behavioral lie in the hot path |
| 🟠 **High** | Artifacts/tests/callers will observe wrong state; likely to cause real bugs |
| 🟡 **Medium** | Fragile, misleading, or will eventually bite you in a non-obvious way |
| 🔵 **Low / Cleanup** | Dead code, naming drift, minor spec deviation |

---

## 🔴 CRITICAL

---

### 1. `lsi.py` — `stage_triplet` in the class body is always broken; the real method is a module-level monkey-patch

**File:** `orket/kernel/v1/state/lsi.py`  
**Functions:** `LocalSovereignIndex.stage_triplet`, `_stage_triplet_grouped_update`

**What it appears to do:** `LocalSovereignIndex` is a class with a `stage_triplet` method that writes triplet artifacts to staging and updates `refs/by_id`.

**What it actually does:** The `stage_triplet` method defined inside the class body calls `self._update_refs_by_id(sources)`, which itself unconditionally raises `RuntimeError` on the very first iteration:

```python
def _update_refs_by_id(self, scope_root: Path, new_sources: list[RefSource]) -> None:
    for s in new_sources:
        raise RuntimeError(
            "Internal contract error: _update_refs_by_id requires ref_type/ref_id grouping. "
            "Call _update_refs_by_id_grouped()."
        )
```

At the very bottom of the module — after the full class definition — the class method is silently replaced:

```python
LocalSovereignIndex.stage_triplet = _stage_triplet_grouped_update  # type: ignore[attr-defined]
```

This means the class definition is a lie. The method you read in the `class` block is never what runs. It only works because the monkey-patch fires at import time.

**Failure modes:**
- Any subclass that calls `super().stage_triplet(...)` executes the broken body.
- Any code path that resolves `LocalSovereignIndex.stage_triplet` before the module bottom executes (e.g., early binding in tests or `getattr` tricks) gets the crashing version.
- The class is unreadable: every reader must mentally track a module-level patch to understand what `stage_triplet` does.

**Fix:** Delete the class-body `stage_triplet` and replace it with the correct grouped implementation directly in the class body. Delete `_update_refs_by_id` or make it a private helper that isn't called from anywhere.

---

### 2. Two incompatible canonicalization systems are both active and produce different output for the same input

**Files:** `orket/kernel/v1/canon.py`, `orket/kernel/v1/canonical.py`  
**Consumers:** `canon.py` → `repro_odr_gate.py`, `test_odr_determinism_gate.py`, LSI disk format. `canonical.py` → `lsi.py` object storage, `compute_turn_result_digest`, `digest_of`.

**What they appear to do:** Both compute a stable canonical representation of a JSON-like Python object for determinism and integrity checking.

**What they actually do:** They are fundamentally different algorithms:

| Property | `canon.py` | `canonical.py` |
|---|---|---|
| RFC 8785 compliant | ❌ No — uses `json.dumps(sort_keys=True)` | ✅ Yes — uses `rfc8785` or `jcs` library |
| Strips temporal/path keys | ✅ Yes (`timestamp`, `path`, `run_id`, etc.) | ❌ No |
| Sorts unordered list keys | ✅ Yes (`nodes`, `edges`, `links`, etc.) | ❌ No |
| Float handling | Silent pass-through | Raises `CanonicalizationError` |
| JS safe int check | No | Yes |

A digest from `canon.py` is structurally different from one from `canonical.py` for the same input object. The ODR determinism gate tests in `test_odr_determinism_gate.py` import from `canon.py` and pin expected SHA256 hashes. The LSI storage layer uses `canonical.py`. These systems cannot verify each other.

**Concrete risk:** `EXPECTED_TORTURE_SHA256` in the determinism gate test is valid against `canon.py` but means nothing against `canonical.py`. If you ever check the LSI's stored digests against the determinism gate's expected hashes, the comparison always fails.

**Fix:** Pick one canonicalization system for the whole kernel. Document which keys are non-semantic at the policy level, not inside the serializer.

---

### 3. `run_round` in `odr/core.py` mutates state in place while pretending to be functional

**File:** `orket/kernel/v1/odr/core.py`  
**Function:** `run_round(state: ReactorState, ...) -> ReactorState`

**What it appears to do:** A pure functional step — takes a `ReactorState`, runs a round, returns the new state.

**What it actually does:** `ReactorState` is a plain mutable dataclass (not frozen). `run_round` mutates the input state directly:

```python
state.history_v.append(current_requirement)
state.stable_count += 1
state.stop_reason = stop_reason
state.history_rounds.append(record)
```

Then it returns the same `state` object. Callers that do `state = run_round(state, ...)` work correctly by coincidence. Callers that snapshot the state before calling (e.g., `old_state = state; new_state = run_round(state, ...)`) will find `old_state` and `new_state` are identical mutable objects — the "old" snapshot has already been mutated.

`repro_odr_gate.py` does `state = run_round(state, ...)` in a loop which works, but any test or harness that tries to replay from a mid-run snapshot will produce garbage.

**Fix:** Either freeze `ReactorState` (use `dataclass(frozen=True)`) and build a new state each round, or rename the function `mutate_state_for_round` and remove the return value, making the mutation explicit.

---

### 4. `check_code_leak` in `odr/core.py` is a dead export with different semantics than the leak gate actually used

**File:** `orket/kernel/v1/odr/core.py`  
**Functions:** `check_code_leak`, `run_round`

**What it appears to do:** `check_code_leak(text, patterns)` is the code leak detection function. It appears to be the authoritative API for checking whether model output contains code.

**What it actually does:** `run_round` does NOT call `check_code_leak`. It calls `detect_code_leak(architect_raw=..., auditor_raw=..., mode=..., patterns=...)` from `leak_policy.py`. `check_code_leak` uses a simple loop over regex patterns against a single `text` string:

```python
def check_code_leak(text: str, patterns: List[str]) -> bool:
    normalized = normalize_newlines(text)
    for pattern in patterns:
        if re.search(pattern, normalized) is not None:
            return True
    return False
```

`detect_code_leak` operates on `architect_raw + auditor_raw` combined, distinguishes hard vs. soft signals, has a `balanced_v1` mode with Python/JS-specific structural pattern matching, a fallback heuristic, and tooling context detection. `check_code_leak` does none of this.

**Consequences:**
- Any test that calls `check_code_leak` directly is testing behavior that never runs in `run_round`.
- Any external caller that uses `check_code_leak` to gate something gets a dramatically weaker check than what the ODR reactor actually enforces.
- Because the function is exported, this is a false-green API surface: it passes for cases that `run_round` would reject.

**Fix:** Unexport `check_code_leak` or delete it. Add a thin delegation wrapper if callers need the public single-text API: `return detect_code_leak(architect_raw=text, auditor_raw="", mode=mode, patterns=patterns).hard_leak`.

---

## 🟠 HIGH

---

### 5. `TurnResult` has `violations: List[str] = None` — crashes with TypeError when iterated

**File:** `orket/application/workflows/turn_executor.py`  
**Class:** `TurnResult`

**What it appears to do:** A dataclass with a `violations` field typed as `List[str]`, defaulting to an empty state.

**What it actually does:**

```python
@dataclass
class TurnResult:
    violations: List[str] = None  # ← None, not []
```

`None` is the default, not an empty list. The type annotation says `List[str]`. Any caller that does `for v in result.violations` when `result.violations is None` (i.e., every non-governance-violation failure) raises `TypeError: 'NoneType' object is not iterable`. The `governance_violation` factory is the only path that sets a real list.

**Fix:**
```python
from dataclasses import field
violations: List[str] = field(default_factory=list)
```

---

### 6. Turn executor persists stale model response artifacts when a reprompt succeeds

**File:** `orket/application/workflows/turn_executor_ops.py`  
**Function:** `execute_turn`

**What it appears to do:** Artifacts written per turn (`model_response.txt`, `model_response_raw.json`, `parsed_tool_calls.json`) reflect the actual model response that was accepted and acted upon.

**What it actually does:** `model_response.txt` and `model_response_raw.json` are written from the **first** model call (lines ~138–158 in `execute_turn`), before contract violations are checked. If violations trigger a reprompt, the second model response overwrites `turn` and passes, but the raw response artifacts are never updated. Only `parsed_tool_calls.json` and the checkpoint (written post-reprompt) reflect the final response.

**Effect:** A developer replaying from artifacts sees a `model_response.txt` that the system rejected, alongside a `parsed_tool_calls.json` from the response that was accepted. These are mismatched. Any determinism or replay analysis that compares raw responses to tool calls will produce incorrect conclusions.

**Fix:** Move the `model_response.txt` / `model_response_raw.json` writes to after the contract validation block, or write a `_reprompt/` variant when a reprompt occurs. At a minimum, write a `reprompt_occurred: true` flag in the checkpoint.

---

### 7. `AsyncDualWriteRunLedgerRepository` does not dual-write for `append_event`, `append_receipt`, or `list_events`

**File:** `orket/adapters/storage/async_dual_write_run_ledger.py`  
**Class:** `AsyncDualWriteRunLedgerRepository`

**What it appears to do:** A compatibility adapter that writes to both SQLite and protocol ledgers for all operations.

**What it actually does:** Only `start_run` and `finalize_run` perform dual writes (SQLite primary + protocol shadow). The event stream operations delegate entirely to `protocol_repo` with no SQLite involvement:

```python
async def append_event(self, ...) -> dict[str, Any]:
    return await self.protocol_repo.append_event(...)  # SQLite never sees this

async def append_receipt(self, ...) -> dict[str, Any]:
    return await self.protocol_repo.append_receipt(...)  # SQLite never sees this

async def list_events(self, session_id: str) -> list[dict[str, Any]]:
    return await self.protocol_repo.list_events(session_id)  # protocol only
```

Any caller relying on SQLite as a fallback source of truth for the event stream will find it empty. The class name promises "dual write" but only delivers it for run lifecycle transitions.

**Fix:** Either rename the class to `ProtocolPrimaryRunLedgerRepository` (with SQLite used only for lifecycle boundaries), or implement actual dual-write for all event operations. Document the asymmetry explicitly in the docstring.

---

### 8. `repro_odr_gate.py` `--expected-hash` diff path is meaningless

**File:** `tools/repro_odr_gate.py`  
**Function:** `main`, specifically the `CANON_MISMATCH` branch

**What it appears to do:** When the canonical hash of an output doesn't match the expected hash, it reports the first structural difference path between the actual output and the expected output.

**What it actually does:**

```python
if args.expected_hash and canon_hash != args.expected_hash:
    expected_payload = {"expected_hash": args.expected_hash}
    expected_bytes = canonical_bytes(expected_payload)          # ← dict with one key
    diff_path = first_diff_path(canon, expected_bytes)          # ← compares apple to orange
```

`expected_bytes` is the canonical encoding of the dict `{"expected_hash": "<some_sha256>"}` — a completely different structure from the actual output. `first_diff_path` comparing the full run output against a one-key dict will always return `$` (root differs), telling you nothing.

To get the real diff, you need to deserialize the *expected output object* and compare that, not a dict containing only its hash.

**Fix:** Either remove `first_diff_path` from the `CANON_MISMATCH` branch (just report the hash mismatch), or store expected canonical bytes alongside the expected hash so a real structural comparison is possible.

---

### 9. `_shape_violation_output` fixture in `test_odr_determinism_gate.py` expects `FORMAT_VIOLATION` but sends headers in wrong order — tests nothing about shape detection

**File:** `tests/kernel/v1/test_odr_determinism_gate.py`  
**Function:** `_shape_violation_output`

**What it appears to do:** A helper that exercises the shape violation path by sending a malformed architect message.

**What it actually does:** The fixture sends headers in the order `REQUIREMENT → ASSUMPTIONS → CHANGELOG → OPEN_QUESTIONS`, but the required order per `parsers.py` is `REQUIREMENT → CHANGELOG → ASSUMPTIONS → OPEN_QUESTIONS`. The parser catches `HEADER_OUT_OF_ORDER`, which correctly produces `stop_reason="FORMAT_VIOLATION"`. So the test does pass — but it's testing the wrong failure mode. The fixture name suggests it's testing "shape violations" (structural code leak), but it's actually testing header ordering. There are no tests in this file for the actual code-leak-based shape detection in `detect_code_leak`.

This is a false-green: the shape violation detector in `leak_policy.py` has no coverage from this helper.

---

## 🟡 MEDIUM

---

### 10. Timestamp monotonicity guard in `async_protocol_run_ledger.py` is lexicographic string comparison

**File:** `orket/adapters/storage/async_protocol_run_ledger.py`  
**Function:** `_append_event_locked`

**What it appears to do:** Guards against non-monotonic timestamps.

**What it actually does:**

```python
if previous_ts and current_ts and current_ts < previous_ts:
    raise ValueError("E_LEDGER_TIMESTAMP_NON_MONOTONIC")
```

This is a string comparison of ISO 8601 timestamps. It works correctly as long as both timestamps use the exact same format from `datetime.now(UTC).isoformat()` (which currently emits `+00:00`). It silently breaks if:
- Any timestamp uses `Z` suffix instead of `+00:00`
- Any timestamp comes from an external source (e.g., replay) with different precision
- Microseconds are stripped in one path but not another

The comparison would pass `"2025-01-01T00:00:01+00:00" < "2025-01-01T00:00:00Z"` incorrectly because `"Z"` sorts before `"+"` in ASCII.

**Fix:** Parse both timestamps before comparing: `datetime.fromisoformat(ts)`.

---

### 11. `get_run()` in `async_protocol_run_ledger.py` returns a fabricated dict (not `None`) when a session has events but no `run_started`

**File:** `orket/adapters/storage/async_protocol_run_ledger.py`  
**Function:** `get_run`

**What it appears to do:** Returns `None` if the session doesn't exist, or the run record if it does.

**What it actually does:** Returns `None` only if there are **zero** events. If events exist but no `run_started` event is among them, it returns a synthesized dict with empty strings, `status="running"`, and zeroed event sequences. Callers expecting `None` as a "not found" sentinel will instead get garbage data that looks valid.

This is a latent bug whenever a run is partially written (e.g., a crash between event writes).

**Fix:** Add a guard: if `run_type == ""` after processing all events, return `None`. Or track a `started_seen` flag and return `None` if not set.

---

### 12. Dead list comprehension in `parsers.py`

**File:** `orket/kernel/v1/odr/parsers.py`  
**Function:** `_extract_sections`

```python
[header for header in required_headers if positions[header]]  # ← result discarded
missing = [header for header in required_headers if not positions[header]]
```

The first list comprehension is computed, evaluated, and immediately discarded. It was likely a debugging artifact or a refactor leftover. It has no side effects but wastes CPU and is confusing — a reader might think the missing-check logic depends on it.

**Fix:** Delete the dead comprehension.

---

### 13. `_validate_orket_number_domain` in `canonical.py` has an unreachable dead branch

**File:** `orket/kernel/v1/canonical.py`  
**Function:** `_validate_orket_number_domain`

```python
for v in _iter_json_values(obj):
    if v is None or isinstance(v, (str, bool)):  # ← catches bool here
        continue
    # bool is subclass of int in Python; ensure we don't treat True/False as numbers.
    if isinstance(v, bool):   # ← DEAD: already continued above
        continue
    if isinstance(v, float):
        raise CanonicalizationError(...)
```

The second `isinstance(v, bool)` check can never execute because any bool was already caught by the first `isinstance(v, (str, bool))` and `continue`d. The comment above the dead check is correct in its intent but the code doesn't need to be there. This is harmless but is a code-reading hazard: reviewers seeing the double-check might think there's a subtle Python subtype reason for it, spending time on a false lead.

**Fix:** Remove the second `isinstance(v, bool)` block.

---

### 14. `OllamaModelStreamProvider.start_turn` applies a double timeout that can fire prematurely

**File:** `orket/streaming/model_provider.py`  
**Function:** `OllamaModelStreamProvider.start_turn`

```python
stream = await asyncio.wait_for(
    self._client.chat(..., stream=True),
    timeout=self._timeout_s,         # ← timeout for connection
)
index = 0
async with asyncio.timeout(self._timeout_s):  # ← second timeout for the full stream
    async for chunk in stream:
        ...
```

`self._timeout_s` is applied twice: once for the initial connection/handshake, and once as a wall-clock budget for consuming the entire stream. If the connection takes 5 seconds and the stream budget is also `timeout_s`, the stream budget started counting before the connection was established, effectively giving streaming less time than intended. On a slow cold-start model, this causes spurious timeouts.

More critically, `asyncio.wait_for` on `self._client.chat(...)` only times out the coroutine up to the point it returns the `stream` object. The actual per-token streaming happens in the `async for` loop, guarded by the second `asyncio.timeout`. These two timeouts are not additive — they measure different phases with the same value.

**Fix:** Use a single overall budget, or document that `timeout_s` is applied independently to connection and streaming phases so operators can set it accordingly.

---

### 15. `StubModelStreamProvider` cancel before `start_turn` registration is silently lost

**File:** `orket/streaming/model_provider.py`  
**Function:** `StubModelStreamProvider.start_turn`, `cancel`

**What it appears to do:** A cancel-before-start call is handled gracefully.

**What it actually does:** `cancel(provider_turn_id)` calls `_is_canceled(id)` → `setdefault(id, new Event)` → `.set()`. The event is created and set. But when `start_turn` later runs, it does:

```python
async with self._lock:
    self._canceled[provider_turn_id] = asyncio.Event()  # ← overwrites the already-set event
```

This is only possible in the Stub because `provider_turn_id` is generated inside `start_turn` using `uuid4()`, so a pre-cancel requires the caller to know the turn ID in advance — which they can't. In practice this race is impossible with the Stub. But if the real providers were ever refactored to accept a caller-supplied `provider_turn_id`, this bug would silently swallow pre-cancels.

---

### 16. `AsyncDualWriteRunLedgerRepository._emit_parity` always reads from both repos after the sqlite write, before the protocol write completes

**File:** `orket/adapters/storage/async_dual_write_run_ledger.py`  
**Function:** `start_run`, `_emit_parity`

In `start_run`, the flow is:
1. `await self.sqlite_repo.start_run(...)` — SQLite write completes
2. `protocol_error = await self._try_protocol_write(...)` — protocol write completes (or errors)
3. `await self._emit_parity(...)` — reads from BOTH repos and compares

But inside `_emit_parity`:
```python
parity = await compare_run_ledger_rows(
    sqlite_repo=self.sqlite_repo,
    protocol_repo=self.protocol_repo,
    session_id=session_id,
)
```

If `protocol_error` is not None (protocol write failed), parity will fail for the wrong reason: not because the data doesn't match but because the protocol record doesn't exist. The parity check is performed regardless of whether the protocol write succeeded. The `protocol_error` field in the emitted telemetry records this, but `parity_ok=False` conflates "write failed" with "parity failed." Any dashboards keying on `parity_ok` will see false parity failures whenever there's a transient protocol write error.

**Fix:** Skip `compare_run_ledger_rows` when `protocol_error is not None`. Record `parity_skip_reason="protocol_write_failed"` instead.

---

## 🔵 LOW / CLEANUP

---

### 17. `canon.py` — `canonical_bytes` double-calls `canonicalize()` when sorting lists

**File:** `orket/kernel/v1/canon.py`  
**Function:** `canonicalize` (list branch)

```python
if isinstance(obj, list):
    canonical_items = [canonicalize(item, _parent_key=_parent_key) for item in obj]
    if _parent_key in UNORDERED_LIST_KEYS:
        canonical_items.sort(key=lambda item: canonical_bytes(item))  # ← calls canonicalize again
    return canonical_items
```

`canonical_bytes` calls `canonicalize` again for the sort key. For a list of N items being sorted, this runs `canonicalize` O(N log N) extra times. For deep graphs this is quadratic. This is a hot path in the ODR determinism gate. The sort key should be precomputed.

---

### 18. `_select_case_id` in `fake_openclaw_adapter_torture.py` silently falls back to index 0 for unknown case IDs

**File:** `tools/fake_openclaw_adapter_torture.py`  
**Function:** `_select_case_id`

```python
def _select_case_id(request: dict[str, Any], known_case_ids: list[str]) -> str:
    requested = str(request.get("case_id") or request.get("scenario_kind") or "").strip()
    if requested:
        return requested
    return known_case_ids[0]
```

If a caller sends a `case_id` that doesn't exist in `cases_by_id`, `_select_case_id` returns the unknown ID, `cases_by_id.get(case_id)` returns `None`, and the loop sends back `UNKNOWN_CASE_ID`. That part is fine. But the fallback `known_case_ids[0]` is a silent default when no `case_id` is sent. If `known_case_ids` is empty (e.g., the corpus failed to load cases but didn't error out), this raises `IndexError` rather than returning a clean error response.

---

### 19. `_resolve_gitea_state_pilot_enabled` in `execution_pipeline.py` ignores the `process_raw` path if `org.process_rules` is not a plain dict

**File:** `orket/runtime/execution_pipeline.py`  
**Function:** `_resolve_gitea_state_pilot_enabled`

```python
if self.org and isinstance(getattr(self.org, "process_rules", None), dict):
    process_raw = str(self.org.process_rules.get("gitea_state_pilot_enabled", "")).strip()
```

If `org.process_rules` is a Pydantic model or a config object (not a plain `dict`), `isinstance(..., dict)` is False, `process_raw` stays `""`, and the org-level setting is silently ignored. The user setting then wins by default. The same pattern repeats for `_resolve_state_backend_mode` and `_resolve_run_ledger_mode`. If `process_rules` was ever migrated to a typed model, all three resolution functions would silently stop reading org config.

---

## Summary Table

| # | Severity | File | Function / Class | Issue |
|---|---|---|---|---|
| 1 | 🔴 Critical | `kernel/v1/state/lsi.py` | `LocalSovereignIndex.stage_triplet` | Class method always raises; replaced by module-level monkey-patch |
| 2 | 🔴 Critical | `kernel/v1/canon.py` vs `canonical.py` | Multiple | Two incompatible canon systems both active; digests not cross-comparable |
| 3 | 🔴 Critical | `kernel/v1/odr/core.py` | `run_round` | Mutates state in place; functional signature is a lie |
| 4 | 🔴 Critical | `kernel/v1/odr/core.py` | `check_code_leak` | Dead export with weaker semantics than the actual leak gate |
| 5 | 🟠 High | `workflows/turn_executor.py` | `TurnResult` | `violations: List[str] = None` crashes on iteration |
| 6 | 🟠 High | `workflows/turn_executor_ops.py` | `execute_turn` | Stale model_response.txt after reprompt; artifact set internally inconsistent |
| 7 | 🟠 High | `adapters/storage/async_dual_write_run_ledger.py` | `AsyncDualWriteRunLedgerRepository` | Name promises dual-write; event stream is protocol-only |
| 8 | 🟠 High | `tools/repro_odr_gate.py` | `main` | `--expected-hash` diff path always returns `$`; comparison is structurally wrong |
| 9 | 🟠 High | `tests/kernel/v1/test_odr_determinism_gate.py` | `_shape_violation_output` | Tests wrong failure mode; actual code-leak shape detector has no coverage |
| 10 | 🟡 Medium | `adapters/storage/async_protocol_run_ledger.py` | `_append_event_locked` | Lexicographic timestamp comparison; breaks on `Z` vs `+00:00` format |
| 11 | 🟡 Medium | `adapters/storage/async_protocol_run_ledger.py` | `get_run` | Returns fabricated dict instead of `None` when `run_started` is missing |
| 12 | 🟡 Medium | `kernel/v1/odr/parsers.py` | `_extract_sections` | Dead list comprehension with no assignment |
| 13 | 🟡 Medium | `kernel/v1/canonical.py` | `_validate_orket_number_domain` | Unreachable second `isinstance(v, bool)` check |
| 14 | 🟡 Medium | `streaming/model_provider.py` | `OllamaModelStreamProvider.start_turn` | Double timeout uses same value for connection and streaming phases |
| 15 | 🟡 Medium | `streaming/model_provider.py` | `StubModelStreamProvider` | Pre-cancel event overwritten when `start_turn` registers new Event |
| 16 | 🟡 Medium | `adapters/storage/async_dual_write_run_ledger.py` | `_emit_parity` | Parity check runs even on protocol write failure; conflates error with divergence |
| 17 | 🔵 Low | `kernel/v1/canon.py` | `canonicalize` | O(N log N) redundant re-canonicalization in sort key |
| 18 | 🔵 Low | `tools/fake_openclaw_adapter_torture.py` | `_select_case_id` | `IndexError` if corpus is empty; no graceful error |
| 19 | 🔵 Low | `runtime/execution_pipeline.py` | `_resolve_gitea_state_pilot_enabled` | Org process_rules silently ignored if not a plain `dict` |

---

## Priority Recommendations

1. **Fix #1 immediately.** The `lsi.py` monkey-patch is a maintenance landmine. The class definition is actively misleading. This should be a clean refactor in one PR.

2. **Resolve the canonicalization split (#2) before shipping any cross-system integrity claims.** Decide: is `canon.py` a separate legacy system for ODR only, or should it be replaced? The answer determines whether your determinism gate hashes and your LSI object digests mean anything to each other.

3. **Fix `run_round` mutation (#3) before writing any ODR snapshot or replay tooling.** The immutability assumption is baked into several replay tools. A frozen dataclass with a builder is the right model.

4. **Fix `TurnResult.violations` (#5) before any error path that reaches governance violations is hit in production.** It's a one-line fix.

5. **Fix the artifact inconsistency (#6) or document the "first-response-wins" artifact policy explicitly** in the artifact schema. Any replay tool built on raw response artifacts will be misled.
