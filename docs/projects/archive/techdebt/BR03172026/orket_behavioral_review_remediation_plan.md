# Orket Behavioral Review — Remediation Plan

Last updated: 2026-03-17  
Status: Archived  
Owner: Orket Core

**Source:** `orket_behavioral_review.md` (2026-03-17)  
**Scope:** 19 behavioral bugs across kernel, adapters, workflows, streaming, and tools.  
**Structure:** Three waves, sequenced to unblock each other. Each item lists exact files, the change to make, how to verify it, and what it unblocks.

---

## Guiding Constraints

- Wave 1 resolves the four Critical bugs. None of them require new capability; they are corrections to existing contracts.
- Wave 2 addresses High bugs that are safe to tackle in parallel once Wave 1 is merged, because none depend on each other.
- Wave 3 covers Medium and Low items, ordered cheapest-first.
- Every fix must include a test change or a new test that would have caught the original bug. If there was a false-green test, replace it.
- No fix should introduce new abbreviation or rename across the codebase unless the old name is provably unused.

---

## Wave 1 — Critical (Merge Before Any Other Work)

These four bugs are the ones where the code is actively lying to you. Merging them first prevents other wave-2 and wave-3 fixes from building on a corrupt foundation.

---

### W1-A: Eliminate the `stage_triplet` monkey-patch in `lsi.py`

**Issue #1 — 🔴 Critical**

**Problem recap:** The `stage_triplet` method defined in the `LocalSovereignIndex` class body calls `_update_refs_by_id` which unconditionally raises `RuntimeError`. At the bottom of the file, the method is replaced via `LocalSovereignIndex.stage_triplet = _stage_triplet_grouped_update`. The class definition is therefore wrong, and the real implementation is invisible to any reader of the class.

**Files to change:**

- `orket/kernel/v1/state/lsi.py`

**Exact changes:**

1. Delete the `stage_triplet` method body from inside the `LocalSovereignIndex` class (the broken one that calls `_update_refs_by_id`).
2. Delete the `_update_refs_by_id` method from the class body entirely. It has no callers other than the dead `stage_triplet`.
3. Move the body of `_stage_triplet_grouped_update` directly into the class as `def stage_triplet(self, *, ...)`. The body is already correct — this is a pure mechanical move.
4. Delete the module-level `_stage_triplet_grouped_update` function definition.
5. Delete the monkey-patch line: `LocalSovereignIndex.stage_triplet = _stage_triplet_grouped_update`.
6. Keep `_update_refs_by_id_grouped` exactly as-is; it is correct and used by the new `stage_triplet`.

**Verification:**

- `tests/kernel/v1/test_spec_002_lsi_v1.py` must pass without modification.
- Add one new test (or assert in the existing suite) that directly instantiates `LocalSovereignIndex` and calls `stage_triplet` without going through any import-time side effects. The test should verify that the method is present and correct on the class `__dict__`, not just on an instance. This catches any future monkey-patch regression:

```python
import inspect
assert "stage_triplet" in LocalSovereignIndex.__dict__, \
    "stage_triplet must be defined directly on the class, not patched in"
```

**What this unblocks:** W2-A (dual-write rename), W3-A (canon sort key), any future subclassing of `LocalSovereignIndex`.

---

### W1-B: Resolve the two-canonicalization-system conflict

**Issue #2 — 🔴 Critical**

**Problem recap:** `canon.py` and `canonical.py` are structurally incompatible. `canon.py` strips non-semantic keys, sorts unordered list keys, and uses `json.dumps(sort_keys=True)` (not RFC 8785). `canonical.py` uses proper RFC 8785 (JCS), rejects floats, enforces JS safe integer range, but does none of the key stripping. Digests from these two functions are not comparable across systems.

**Decision required before writing code:** You need to decide which system owns which surface. The review evidence suggests the following split, but you should confirm it:

| System | Correct canonicalizer | Rationale |
|---|---|---|
| ODR reactor (`odr/core.py`, `repro_odr_gate.py`) | `canon.py` | The ODR uses graph-level key semantics (node/edge ordering, temporal key stripping). The existing SHA256 pinned values in tests are calibrated against `canon.py`. Changing this would require re-publishing all baseline hashes. |
| LSI object store (`state/lsi.py`) | `canonical.py` | Object storage needs RFC 8785 for cross-language/protocol stability. No pinned hash regression risk. |
| Turn result digests (`canonical.py` → `compute_turn_result_digest`) | `canonical.py` | Already correct. |

**Files to change (assuming the split above is confirmed):**

- `orket/kernel/v1/canon.py` — Add a module-level docstring that explicitly states this is the ODR-domain canonicalizer, is NOT RFC 8785, and must not be used outside the ODR subsystem.
- `orket/kernel/v1/canonical.py` — Add a module-level docstring that explicitly states this is the RFC 8785 / JCS canonicalizer, used for object storage and turn digests.
- `tests/kernel/v1/test_canonical_rfc8785_backend.py` (currently testing the capability decision record schema, misfiled) — Add a test that imports both `canon.canonical_bytes` and `canonical.canonical_json_bytes`, feeds the same object to both, and asserts they produce **different** bytes. This locks in the separation and prevents accidental convergence.
- `tests/kernel/v1/test_odr_determinism_gate.py` — Add an assertion that the test file only imports from `orket.kernel.v1.canon` and never from `orket.kernel.v1.canonical`. A simple string-scan assertion in a test is sufficient.

**If you decide to unify:** The larger work is to port `canon.py` semantics (key stripping, unordered list sorting) into `canonical.py` as an optional `profile` parameter, re-run the ODR determinism gate to regenerate all pinned hashes, and update the expected SHA256 constants in `test_odr_determinism_gate.py`. This is correct but requires a coordinated hash update across all ODR baseline fixtures. Plan for this as a separate sprint item.

**Verification:**

- All existing ODR determinism gate tests pass.
- New cross-system isolation test in `test_canonical_rfc8785_backend.py` passes.
- No file outside `orket/kernel/v1/odr/` imports from `canon.py` (enforce with `test_ring_import_boundary_policy.py` or a new lint rule).

**What this unblocks:** Any future integrity verification between ODR output and LSI storage.

---

### W1-C: Make `ReactorState` immutable or make `run_round` explicitly mutating

**Issue #3 — 🔴 Critical**

**Problem recap:** `run_round` is typed as `(ReactorState, ...) -> ReactorState` and all callers do `state = run_round(state, ...)`, implying a functional pipeline. In reality it mutates the input in place. Any caller that holds a reference to a "before" state snapshot will observe it changed.

**Recommended approach — Frozen dataclass (preferred):**

**Files to change:**

- `orket/kernel/v1/odr/core.py`

**Exact changes:**

1. Change `@dataclass` to `@dataclass(frozen=True)` on `ReactorState`.
2. Replace all mutating lines in `run_round` with construction of a new `ReactorState`:

```python
# Before (mutating):
state.history_v.append(current_requirement)
state.stable_count += 1
state.stop_reason = stop_reason
state.history_rounds.append(record)

# After (functional):
new_history_v = list(state.history_v) + [current_requirement]
new_stable_count = state.stable_count + 1  # or 0 depending on branch
new_history_rounds = list(state.history_rounds) + [record]
state = ReactorState(
    history_v=new_history_v,
    history_rounds=new_history_rounds,
    stable_count=new_stable_count,
    stop_reason=stop_reason,
)
```

3. All return sites already do `return state`, so the return type is correct once the binding is updated.

**Alternative approach — Make mutation explicit (if frozen is too disruptive):**

Rename `run_round` to `advance_reactor_state`. Change the return type to `None`. Update all callers (they already ignore the return value in the way that matters, since they rebind `state`). Add a docstring: "Mutates state in place. Do not hold references to state across calls."

This is less safe but has zero diff impact on callers.

**Verification:**

- Add a test that confirms snapshot isolation:

```python
def test_run_round_does_not_mutate_input():
    cfg = ReactorConfig()
    state_before = ReactorState()
    architect = "### REQUIREMENT\nX\n\n### CHANGELOG\n- c\n\n### ASSUMPTIONS\n- a\n\n### OPEN_QUESTIONS\n- q\n"
    auditor = "### CRITIQUE\n- c\n\n### PATCHES\n- p\n\n### EDGE_CASES\n- e\n\n### TEST_GAPS\n- t\n"
    state_after = run_round(state_before, architect, auditor, cfg)
    assert state_before is not state_after
    assert state_before.history_v == []  # must be unchanged
    assert state_before.stop_reason is None
```

- All existing `test_odr_core.py` and `test_odr_determinism_gate.py` tests pass.

**What this unblocks:** W2-D (`repro_odr_gate.py` fix), any ODR snapshot/replay tooling.

---

### W1-D: Remove or correctly delegate `check_code_leak`

**Issue #4 — 🔴 Critical**

**Problem recap:** `check_code_leak` in `odr/core.py` is a simpler, weaker function that is never called internally. `run_round` calls `detect_code_leak` from `leak_policy.py`. Any caller using `check_code_leak` gets different (weaker) behavior than the ODR reactor itself enforces.

**Files to change:**

- `orket/kernel/v1/odr/core.py`

**Option A — Replace with thin delegation (recommended if external callers exist):**

```python
def check_code_leak(text: str, patterns: list[str]) -> bool:
    """
    Thin delegation to the authoritative leak gate used by run_round.
    Uses default leak_gate_mode. For full control use detect_code_leak() directly.
    """
    from .leak_policy import detect_code_leak, DEFAULT_LEAK_GATE_MODE
    detection = detect_code_leak(
        architect_raw=text,
        auditor_raw="",
        mode=DEFAULT_LEAK_GATE_MODE,
        patterns=patterns or None,
    )
    return detection.hard_leak
```

**Option B — Delete (if no external callers exist):**

Run `grep -r "check_code_leak" .` across the codebase. If zero hits outside `odr/core.py` itself, delete the function and remove it from any `__all__` exports.

**Verification:**

- Add a test that calls both `check_code_leak` and `detect_code_leak` (with `auditor_raw=""`) on the same input and asserts they return the same hard-leak verdict.
- Search for any test that previously called `check_code_leak` directly and was not also covered by `run_round` tests — if found, migrate it to test `run_round` behavior instead.

**What this unblocks:** W2-E (false-green shape-violation test fix), confidence in any external tooling using the public ODR API.

---

## Wave 2 — High (Parallelizable After Wave 1)

These can be worked in any order or in parallel. None depend on each other, but all benefit from the Wave 1 foundation.

---

### W2-A: Fix `TurnResult.violations` default

**Issue #5 — 🟠 High**

**File:** `orket/application/workflows/turn_executor.py`

**Change:**

```python
# Before:
violations: List[str] = None

# After:
from dataclasses import field
violations: List[str] = field(default_factory=list)
```

**Verification:** Add a test that constructs `TurnResult.failed("some error")` and asserts `result.violations == []` and that iterating `result.violations` does not raise.

---

### W2-B: Fix stale model response artifacts on reprompt

**Issue #6 — 🟠 High**

**File:** `orket/application/workflows/turn_executor_ops.py`

**Change:** After the reprompt block succeeds (second model call passes contract validation), write updated response artifacts. The simplest approach is to move the `model_response.txt` and `model_response_raw.json` writes to a shared helper called after both the first and second model call paths converge. Alternatively, add a `reprompt_model_response.txt` artifact for the second call and add a `reprompt_occurred` boolean to the checkpoint. Either approach is acceptable; the important thing is that no artifact set contains a rejected response alongside accepted tool calls.

**Recommended implementation:** Extract the artifact-write block for `model_response.txt` and `model_response_raw.json` into a helper function `_write_response_artifacts(executor, session_id, issue_id, role_name, turn_index, response)`. Call it once after the first model call, and call it again (overwriting) after the reprompt call.

**Verification:** Add a test in `tests/application/test_turn_executor_middleware.py` that triggers a contract violation + reprompt and then reads the written `model_response.txt` from the artifact directory. Assert it contains content from the second model call, not the first.

---

### W2-C: Rename `AsyncDualWriteRunLedgerRepository` or implement full dual-write

**Issue #7 — 🟠 High**

**File:** `orket/adapters/storage/async_dual_write_run_ledger.py`

**Decision required:** Pick one:

**Option A — Rename (cheaper, honest):** Rename to `ProtocolRunLedgerWithSqliteLifecycleMirrorRepository` or a shorter but accurate name like `ProtocolPrimaryRunLedgerRepository`. Update all instantiation sites. Update docstring to state explicitly that SQLite receives only lifecycle events (`start_run`, `finalize_run`) and is not a full mirror of the event stream.

**Option B — Implement full dual-write (correct, more work):** For `append_event` and `append_receipt`, add shadow writes to `sqlite_repo` using `_try_protocol_write` / `_emit_parity` pattern already established for `start_run`. This requires the SQLite repo to expose `append_event` and `append_receipt`, which it currently does not — that's the actual reason the methods delegate to protocol-only today. Scope this as a separate ticket if Option A is chosen first.

**Verification for Option A:** Add a test that instantiates the class and checks `__class__.__name__` or the class docstring for the word "dual" — if found, fail. This prevents the name from drifting back.

---

### W2-D: Fix `repro_odr_gate.py` — `CANON_MISMATCH` diff path

**Issue #8 — 🟠 High**

**File:** `tools/repro_odr_gate.py`

**Change:** Remove the `first_diff_path` call from the `CANON_MISMATCH` branch. The hash is the evidence of mismatch; the structural diff requires the expected output object, not its hash. The current code builds a one-key dict from the hash string and diffs that — which always returns `$`.

```python
# Before:
if args.expected_hash and canon_hash != args.expected_hash:
    expected_payload = {"expected_hash": args.expected_hash}
    expected_bytes = canonical_bytes(expected_payload)
    diff_path = first_diff_path(canon, expected_bytes)
    return _print_failure(..., diff_path=diff_path, ...)

# After:
if args.expected_hash and canon_hash != args.expected_hash:
    return _print_failure(..., diff_path="$", reason="CANON_MISMATCH")
```

If you want a real structural diff in the future, add an `--expected-canon-bytes-file` argument that accepts a path to the previously serialized canonical bytes, and use `first_diff_path(canon, Path(args.expected_canon_bytes_file).read_bytes())`.

**Verification:** Add a test in `tests/scripts/` that runs `repro_odr_gate.py` with a known-bad `--expected-hash` and asserts that `first_diff_path` is not called (or that the output does not claim a specific diff path when only hash is known).

---

### W2-E: Fix the `_shape_violation_output` test helper

**Issue #9 — 🟠 High**

**File:** `tests/kernel/v1/test_odr_determinism_gate.py`

**Change:** `_shape_violation_output` happens to produce `FORMAT_VIOLATION` (via `HEADER_OUT_OF_ORDER`) but is named and commented as if it tests code-leak shape detection. Fix in two steps:

1. Rename `_shape_violation_output` to `_header_order_violation_output` and update all call sites. Its existing behavior is actually a valid test of the header ordering contract — keep it, just name it correctly.

2. Add a new test function `test_code_leak_shape_detection_fires` that constructs architect/auditor content containing a fence block or Python struct pattern and asserts `run_round` returns `stop_reason == "CODE_LEAK"`. This is the test that was never written.

**Verification:** The new test must fail if `detect_code_leak` is replaced with `check_code_leak` (cross-checking W1-D).

---

## Wave 3 — Medium and Low (Ordered Cheapest First)

---

### W3-A: Fix dead list comprehension in `parsers.py`

**Issue #12 — 🟡 Medium** (trivial, do this first in Wave 3)

**File:** `orket/kernel/v1/odr/parsers.py`  
**Function:** `_extract_sections`

Delete the line:
```python
[header for header in required_headers if positions[header]]
```

It has no assignment target and no side effects. One-line delete, one-line test confirmation that `_extract_sections` behavior is unchanged.

---

### W3-B: Fix dead `isinstance(v, bool)` branch in `canonical.py`

**Issue #13 — 🟡 Medium** (trivial)

**File:** `orket/kernel/v1/canonical.py`  
**Function:** `_validate_orket_number_domain`

Delete the second `isinstance(v, bool)` block. The first check already handles bools via `isinstance(v, (str, bool))`. Add a comment explaining why bool is caught with `str` (Python's `bool` is a subclass of `int`; catching it early prevents false float/int rejections):

```python
# bool is a subclass of int in Python. Catch it here alongside str/None
# before the int path, to prevent True/False from being validated as integers.
if v is None or isinstance(v, (str, bool)):
    continue

if isinstance(v, float):
    raise CanonicalizationError(...)

if isinstance(v, int):
    ...
```

---

### W3-C: Fix timestamp comparison to use datetime objects

**Issue #10 — 🟡 Medium**

**File:** `orket/adapters/storage/async_protocol_run_ledger.py`  
**Function:** `_append_event_locked`

```python
# Before:
if previous_ts and current_ts and current_ts < previous_ts:
    raise ValueError("E_LEDGER_TIMESTAMP_NON_MONOTONIC")

# After:
from datetime import datetime
def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None

prev_dt = _parse_ts(previous_ts)
curr_dt = _parse_ts(current_ts)
if prev_dt is not None and curr_dt is not None and curr_dt < prev_dt:
    raise ValueError("E_LEDGER_TIMESTAMP_NON_MONOTONIC")
```

**Verification:** Add a test that writes two events where the second has a `Z`-suffixed timestamp that is chronologically later, and asserts no `ValueError` is raised. Also test that a chronologically earlier second timestamp does raise.

---

### W3-D: Fix `get_run` fabricated-dict false positive

**Issue #11 — 🟡 Medium**

**File:** `orket/adapters/storage/async_protocol_run_ledger.py`  
**Function:** `get_run`

Add a `started_seen` flag. Return `None` if no `run_started` event was found:

```python
started_seen = False
for event in events:
    kind = str(event.get("kind") or "")
    if kind == "run_started":
        started_seen = True
        ...
    ...

if not started_seen:
    return None
```

**Verification:** Add a test that appends a `tool_call` event without a prior `run_started` and asserts `get_run()` returns `None`.

---

### W3-E: Fix `_emit_parity` — skip parity on protocol write failure

**Issue #16 — 🟡 Medium**

**File:** `orket/adapters/storage/async_dual_write_run_ledger.py`  
**Function:** `_emit_parity`

Add an early-exit when `protocol_error` is set:

```python
async def _emit_parity(self, *, phase, session_id, protocol_error):
    if protocol_error is not None:
        await self._emit({
            "kind": "run_ledger_dual_write_parity",
            "phase": str(phase),
            "session_id": str(session_id),
            "parity_ok": False,
            "parity_skip_reason": "protocol_write_failed",
            "protocol_error": protocol_error,
        })
        return
    # ... existing comparison logic
```

**Verification:** Add a test that injects a protocol write failure and asserts the parity event contains `parity_skip_reason == "protocol_write_failed"` rather than `difference_count > 0`.

---

### W3-F: Fix double timeout in `OllamaModelStreamProvider`

**Issue #14 — 🟡 Medium**

**File:** `orket/streaming/model_provider.py`  
**Function:** `OllamaModelStreamProvider.start_turn`

Add a distinct `stream_timeout_s` parameter (or derive it: `stream_timeout_s = timeout_s * 3`). Apply the smaller value to the connection handshake and the larger value to the stream consumption:

```python
# __init__:
self._connect_timeout_s = max(1.0, float(timeout_s))
self._stream_timeout_s = max(1.0, float(stream_timeout_s or timeout_s * 3))

# start_turn:
stream = await asyncio.wait_for(
    self._client.chat(..., stream=True),
    timeout=self._connect_timeout_s,
)
async with asyncio.timeout(self._stream_timeout_s):
    async for chunk in stream:
        ...
```

If adding a parameter is too disruptive, at minimum add a comment documenting that `timeout_s` is used independently for both phases and operators should set it conservatively relative to stream length.

---

### W3-G: Fix `_select_case_id` `IndexError` on empty corpus

**Issue #18 — 🔵 Low**

**File:** `tools/fake_openclaw_adapter_torture.py`  
**Function:** `_select_case_id` (and `main`)

The original review referenced `fake_openclaw_adapter_strict.py`, but the live `_select_case_id` path now resides in `fake_openclaw_adapter_torture.py`.

```python
def _select_case_id(request, known_case_ids):
    requested = str(request.get("case_id") or request.get("scenario_kind") or "").strip()
    if requested:
        return requested
    if not known_case_ids:
        return ""   # Caller must handle empty string
    return known_case_ids[0]
```

In `main`, after `_select_case_id` returns `""`, add:
```python
if not case_id:
    _write_line({"type": "error", "code": "NO_CASES_LOADED", "message": "Corpus is empty."})
    continue
```

---

### W3-H: Fix process_rules type guard in `execution_pipeline.py`

**Issue #19 — 🔵 Low**

**File:** `orket/runtime/execution_pipeline.py`  
**Functions:** `_resolve_state_backend_mode`, `_resolve_run_ledger_mode`, `_resolve_gitea_state_pilot_enabled`

For all three functions, change the type guard from `isinstance(..., dict)` to a method-existence check, or use `getattr` with a default:

```python
# Before:
if self.org and isinstance(getattr(self.org, "process_rules", None), dict):
    process_raw = str(self.org.process_rules.get("state_backend_mode", "")).strip()

# After:
process_rules = getattr(self.org, "process_rules", None) or {}
if hasattr(process_rules, "get"):
    process_raw = str(process_rules.get("state_backend_mode", "")).strip()
```

This works for both `dict` and Pydantic models that expose `.get()`.

---

### W3-I: Precompute sort key in `canon.py` canonicalize

**Issue #17 — 🔵 Low** (performance, not correctness)

**File:** `orket/kernel/v1/canon.py`  
**Function:** `canonicalize`

```python
# Before:
canonical_items.sort(key=lambda item: canonical_bytes(item))

# After:
keyed = [(canonical_bytes(item), item) for item in canonical_items]
keyed.sort(key=lambda pair: pair[0])
canonical_items = [item for _, item in keyed]
```

This converts O(N log N) redundant re-canonicalization to one pass of precomputation plus a sort on already-computed bytes. Add a benchmark assertion or comment with expected improvement for large graphs.

---

## Wave 3-J: Address the stub cancel-before-start race

**Issue #15 — 🟡 Medium** (defensive, low urgency for Stub)

**File:** `orket/streaming/model_provider.py`  
**Function:** `StubModelStreamProvider.start_turn`

Change the cancel event registration to check if an event already exists and preserve it:

```python
# Before:
async with self._lock:
    self._canceled[provider_turn_id] = asyncio.Event()

# After:
async with self._lock:
    if provider_turn_id not in self._canceled:
        self._canceled[provider_turn_id] = asyncio.Event()
    # else: keep the already-set (pre-cancel) event
```

Since `provider_turn_id` is generated with `uuid4()` inside `start_turn`, a true pre-cancel is currently impossible for the Stub. But this hardens the design against future refactors that accept a caller-supplied turn ID.

---

## Completion Checklist

Closeout status: completed 2026-03-17. All W1, W2, and W3 items were implemented and verified by the targeted regression proof recorded in the archive closeout for this cycle.

Authoritative closeout table:

| # | Item | Wave | Owner | Done |
|---|---|---|---|---|
| W1-A | Remove `lsi.py` monkey-patch | 1 | Orket Core | yes |
| W1-B | Resolve canonicalization split | 1 | Orket Core | yes |
| W1-C | Make `run_round` functionally pure or explicitly mutating | 1 | Orket Core | yes |
| W1-D | Fix or delete `check_code_leak` | 1 | Orket Core | yes |
| W2-A | Fix `TurnResult.violations = None` | 2 | Orket Core | yes |
| W2-B | Fix stale model response artifacts on reprompt | 2 | Orket Core | yes |
| W2-C | Rename dual-write ledger or implement full dual-write | 2 | Orket Core | yes |
| W2-D | Fix `repro_odr_gate.py` CANON_MISMATCH diff path | 2 | Orket Core | yes |
| W2-E | Fix false shape-violation test; add real code-leak test | 2 | Orket Core | yes |
| W3-A | Delete dead list comprehension in `parsers.py` | 3 | Orket Core | yes |
| W3-B | Delete dead `isinstance(v, bool)` in `canonical.py` | 3 | Orket Core | yes |
| W3-C | Fix timestamp comparison to use `datetime.fromisoformat` | 3 | Orket Core | yes |
| W3-D | Fix `get_run` fabricated-dict on no `run_started` | 3 | Orket Core | yes |
| W3-E | Skip parity check on protocol write failure | 3 | Orket Core | yes |
| W3-F | Fix double timeout in `OllamaModelStreamProvider` | 3 | Orket Core | yes |
| W3-G | Fix `IndexError` on empty corpus in `fake_openclaw_adapter_torture.py` | 3 | Orket Core | yes |
| W3-H | Fix `process_rules` type guard in `execution_pipeline.py` | 3 | Orket Core | yes |
| W3-I | Precompute sort key in `canon.py` | 3 | Orket Core | yes |
| W3-J | Harden Stub provider cancel-before-start | 3 | Orket Core | yes |

Historical working table retained below:

| # | Item | Wave | Owner | Done |
|---|---|---|---|---|
| W1-A | Remove `lsi.py` monkey-patch | 1 | — | ☐ |
| W1-B | Resolve canonicalization split | 1 | — | ☐ |
| W1-C | Make `run_round` functionally pure or explicitly mutating | 1 | — | ☐ |
| W1-D | Fix or delete `check_code_leak` | 1 | — | ☐ |
| W2-A | Fix `TurnResult.violations = None` | 2 | — | ☐ |
| W2-B | Fix stale model response artifacts on reprompt | 2 | — | ☐ |
| W2-C | Rename dual-write ledger or implement full dual-write | 2 | — | ☐ |
| W2-D | Fix `repro_odr_gate.py` CANON_MISMATCH diff path | 2 | — | ☐ |
| W2-E | Fix false shape-violation test; add real code-leak test | 2 | — | ☐ |
| W3-A | Delete dead list comprehension in `parsers.py` | 3 | — | ☐ |
| W3-B | Delete dead `isinstance(v, bool)` in `canonical.py` | 3 | — | ☐ |
| W3-C | Fix timestamp comparison to use `datetime.fromisoformat` | 3 | — | ☐ |
| W3-D | Fix `get_run` fabricated-dict on no `run_started` | 3 | — | ☐ |
| W3-E | Skip parity check on protocol write failure | 3 | — | ☐ |
| W3-F | Fix double timeout in `OllamaModelStreamProvider` | 3 | — | ☐ |
| W3-G | Fix `IndexError` on empty corpus in `fake_openclaw_adapter_strict.py` | 3 | — | ☐ |
| W3-H | Fix `process_rules` type guard in `execution_pipeline.py` | 3 | — | ☐ |
| W3-I | Precompute sort key in `canon.py` | 3 | — | ☐ |
| W3-J | Harden Stub provider cancel-before-start | 3 | — | ☐ |

---

## Notes on Test Coverage Policy

Each wave item that involves deleting or changing a code path must include at least one test that would have caught the original bug at the time it was introduced. In specific terms:

- **W1-A:** Test that `stage_triplet` is in `LocalSovereignIndex.__dict__` (not patched).
- **W1-C:** Test that input `ReactorState` is unchanged after `run_round`.
- **W1-D:** Test that `check_code_leak` and `detect_code_leak` agree on verdict.
- **W2-A:** Test that `TurnResult.failed(...)` has an iterable `violations`.
- **W2-B:** Test that `model_response.txt` reflects the accepted response, not the rejected one.
- **W2-E:** Test that `run_round` fires `CODE_LEAK` on fenced code blocks.
- **W3-C:** Test timestamp comparison with `Z` vs `+00:00` format.
- **W3-D:** Test `get_run` returns `None` when no `run_started` event exists.

For all other items, existing test coverage is sufficient once the fix is applied.
