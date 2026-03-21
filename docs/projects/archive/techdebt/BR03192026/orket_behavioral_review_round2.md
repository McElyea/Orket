# Orket — Behavioral Truth Code Review (Round 2)

**Date:** 2026-03-19  
**Scope:** Updated codebase after Round 1 remediation. Covers new ODR semantic layer, updated convergence logic, and any regressions or newly introduced behavioral lies.  
**Prior review:** `orket_behavioral_review.md` (2026-03-17)

---

## Prior Review Status

All 19 issues from the Round 1 review are confirmed fixed in this build. Notable fixes include: the `lsi.py` monkey-patch has been removed and `stage_triplet` lives cleanly in the class body; `ReactorState` is now `frozen=True` and `run_round` is properly functional; the two canonicalization systems are now documented with clear docstrings; `check_code_leak` delegates to `detect_code_leak`; `TurnResult.violations` uses `field(default_factory=list)`; `OllamaModelStreamProvider` has separate connection and stream timeouts; and `AsyncDualWriteRunLedgerRepository` is correctly renamed `AsyncProtocolPrimaryRunLedgerRepository`.

The new work — the semantic validity layer in `semantic_validity.py`, the revised ODR convergence logic in `core.py`, and the new `live_runner.py` / `prompt_contract.py` modules — introduces a fresh set of behavioral mismatches documented below.

---

## Severity Legend

| Level | Meaning |
|---|---|
| 🔴 **Critical** | Silent wrong behavior in the hot path; will produce incorrect results under normal use |
| 🟠 **High** | Causes incorrect classification or prevents convergence; observable in real runs |
| 🟡 **Medium** | Fragile, misleading, or will produce wrong results in a specific but realistic scenario |
| 🔵 **Low** | Naming drift, minor spec deviation, or unreachable coverage gap |

---

## 🔴 CRITICAL

---

### 1. `_unresolved_alternative_hits` classifies ordinary requirement English as unresolved decisions

**File:** `orket/kernel/v1/odr/semantic_validity.py`  
**Function:** `_unresolved_alternative_hits`

**What it appears to do:** Detect genuinely ambiguous alternative constructions in requirement text — phrases that indicate a decision has not been made yet.

**What it actually does:** The regex `_UNRESOLVED_ALTERNATIVE_RE` contains two patterns that match common, non-ambiguous English vocabulary:

```python
_UNRESOLVED_ALTERNATIVE_RE = re.compile(
    r"\b(either\b.*\bor\b|\bor\b|\bmay\b|\bdepending on\b)", re.IGNORECASE
)
```

The bare `\bor\b` matches any standalone "or" in any clause. The `\bmay\b` matches any occurrence of "may" regardless of context. This means:

- `"The system must encrypt or hash all passwords."` → fires: `\bor\b` matches → classified INVALID
- `"The system may cache results for up to 10 seconds."` → fires: `\bmay\b` matches → classified INVALID
- `"Users must authenticate via password or hardware token."` → fires → INVALID
- `"The tool must read or write to the workspace path."` → fires → INVALID

In RFC 2119 usage, "may" means "is permitted to" — it is a valid constraint verb, not an ambiguity marker. And "or" in requirements frequently describes valid binary choices that are not ambiguous (encrypt-or-hash is a concrete choice the implementer makes, not an open decision).

**Effect:** Any requirement containing "or" or "may" is classified `validity_verdict = "invalid"`, which means `pending_decisions` is non-empty, and the ODR will never reach `STABLE_DIFF_FLOOR` via the valid path. Instead, it will either loop until `MAX_ROUNDS` → `UNRESOLVED_DECISIONS`, or loop indefinitely if the model keeps using "or" or "may" in requirements. This effectively makes the semantic validity gate a false blocker for the majority of real-world requirement text.

**Concrete fix:** The `\bor\b` arm of the regex is too broad. It should only match `\bor\b` when preceded or followed by an explicit ambiguity marker, or the pattern should be rewritten to require a sentence-level pattern (e.g., `either...or`, `X or Y` where neither X nor Y is followed by a verb). The `\bmay\b` arm should only match when "may" is in a list-of-options context, not as RFC 2119 "permitted". The simplest safe fix is to remove `\bor\b` and `\bmay\b` from the regex entirely and rely on `\either\b.*\bor\b` and `\bdepending on\b` only.

---

### 2. `diff_ratio` in `metrics.py` measures character length change, not textual similarity

**File:** `orket/kernel/v1/odr/metrics.py`  
**Function:** `diff_ratio`

**What it appears to do:** Measure how much a requirement changed between rounds to detect convergence (stable output).

**What it actually does:**

```python
def diff_ratio(curr: str, prev: str) -> float:
    return abs(len(str(curr)) - len(str(prev))) / max(1, len(str(prev)))
```

This is purely a character count delta. Two completely different strings of the same length return `diff_ratio = 0.0`. This means the ODR will declare `STABLE_DIFF_FLOOR` on semantically divergent requirements if they happen to be the same length.

**Concrete example:** If round N produces `"must store data locally on device"` (34 chars) and round N+1 produces `"must upload data remotely to cloud"` (34 chars), `diff_ratio = 0.0 < 0.05` → `stable_count += 1`. The ODR believes these are converging. They are opposite requirements.

This is the metric used to drive ALL convergence detection — `diff_hit` which triggers `STABLE_DIFF_FLOOR` — and `jaccard_sim` is only used for the less-common `circ_hit` loop detection. In practice, most convergence will happen via `STABLE_DIFF_FLOOR`, and all of it is gated on a length-difference metric.

**Fix:** `diff_ratio` should be `1.0 - jaccard_sim(curr, prev, k=3)` (or similar normalized edit distance). Using `jaccard_sim` from the same module makes the convergence definition consistent with the loop-detection definition.

---

## 🟠 HIGH

---

### 3. `stable_count` is not reset when transitioning from valid to invalid rounds

**File:** `orket/kernel/v1/odr/core.py`  
**Function:** `run_round`

**What it appears to do:** Track consecutive stable valid rounds. `STABLE_DIFF_FLOOR` fires when `stable_count >= stable_rounds` consecutive valid rounds have `diff_ratio < diff_floor_pct`.

**What it actually does:** When a round is valid, `next_invalid_stable_count = 0` (correctly resets). But when a round is invalid, `next_stable_count` is never reset — it simply carries forward from `state.stable_count`:

```python
next_stable_count = state.stable_count   # initialized here
...
if semantic["validity_verdict"] == "valid":
    ...
    next_invalid_stable_count = 0        # valid path resets invalid count
    # ← valid path may increment OR reset next_stable_count via _advance_history_metrics
else:
    ...
    # ← invalid path NEVER touches next_stable_count
    # next_stable_count stays as state.stable_count (whatever it was)
```

**Consequence:** Suppose rounds go `[valid(diff=0.03, stable→1), invalid, invalid, valid(diff=0.02 vs previous valid)]`. After round 4, `prior_stable_count = state.stable_count = 1` (leftover from round 1). Round 4 compares `valid_history_v[-1]` vs `valid_history_v[-2]` (rounds 1 and 4). If diff < floor, `next_stable_count = 2`, `diff_hit = True` → `STABLE_DIFF_FLOOR`. But rounds 1 and 4 were not consecutive — two invalid rounds occurred between them. The ODR declares convergence based on non-consecutive valid rounds.

A model that oscillates between valid and invalid but produces similar valid content on alternating rounds can satisfy `stable_rounds` without actually being stable.

**Fix:** Reset `next_stable_count = 0` at the start of the invalid branch, just as the valid branch resets `next_invalid_stable_count = 0`.

---

### 4. `_constraint_demotion_violations` fires on intentional removals, preventing legitimate convergence

**File:** `orket/kernel/v1/odr/semantic_validity.py`  
**Function:** `_constraint_demotion_violations`, `evaluate_semantic_validity`

**What it appears to do:** Detect when the architect moves a required constraint out of `REQUIREMENT` into `ASSUMPTIONS` or `OPEN_QUESTIONS` (which would weaken it).

**What it actually does:** The function checks whether a required clause from `previous_requirement` is present in either `current_requirement`, `assumptions`, or `open_questions`. If absent from all three, it fires as a demotion violation.

But `evaluate_semantic_validity` computes `patch_classes` from the auditor's `PATCHES` section — including `[REMOVE]` patches — and then passes those to the return dict. Critically, it does NOT pass `patch_classes` to `_constraint_demotion_violations`. The demotion check has no awareness of explicit `[REMOVE]` patches.

**Concrete failure:** Auditor: `[REMOVE] The 30-day retention clause is incorrect; no retention is required.` → Architect removes the clause. → `_constraint_demotion_violations` fires because the prior required clause is now absent. → `validity_verdict = "invalid"`. → Legitimate requirement refinement is blocked.

This creates a contradictory contract: the auditor is explicitly instructed to use `[REMOVE]` patches (as stated in `prompt_contract.py`), but the semantic validator penalizes the architect for following that instruction.

**Fix:** Pass `patch_classes` into `_constraint_demotion_violations`. For each violated clause, check whether the auditor's patches contain a `[REMOVE]` patch whose text approximately matches the clause. If so, suppress the violation.

---

### 5. `history_v` in `ReactorState` now contains ALL rounds (valid + invalid) but is consumed as if it is the convergence sequence

**File:** `orket/kernel/v1/odr/core.py`, `orket/kernel/v1/odr/live_runner.py`

**What it appears to be:** The sequence of refined requirements produced by the ODR — what the architect actually produced at each round.

**What it actually is:** `history_v` now contains every requirement that was parsed, including invalid ones:

```python
history_v = [*state.history_v, current_requirement]   # always appended
```

Meanwhile, convergence detection runs on `valid_history_v` (valid path) or `invalid_history_v` (invalid path) — separate lists. The original spec (and the published benchmarks) describe `history_v` as the convergence trace. Callers now get a mixed bag.

**Concrete consequences:**

1. `live_runner.py` exports `"history_v": list(state.history_v)` — this includes invalid requirement drafts alongside valid ones. A consumer analyzing the history to understand how the requirement evolved will see spurious entries.

2. `max_hit = n == int(cfg.max_rounds)` where `n = len(history_v)` — max_hit fires based on total attempts including invalid rounds. A run with `max_rounds=8` and 3 valid rounds + 5 invalid rounds hits `MAX_ROUNDS` at round 8, even though only 3 valid refinement attempts were made. If the intent is to allow `max_rounds` of valid refinement, this is wrong.

3. The existing `repro_odr_gate.py` output format includes `"history_v"` from the fixture, and pinned SHA256 hashes depend on its content. If a fixture now produces more entries in `history_v` (because invalid rounds contribute), those hashes change silently.

**Fix:** Rename `history_v` to `all_history_v` or `attempt_history_v` and expose `valid_history_v` as the primary convergence trace. Update `live_runner.py` to export `valid_history_v` as `"history_v"` for backward compatibility. Use `len(valid_history_v)` for `max_hit` if the intent is to cap valid refinement rounds.

---

## 🟡 MEDIUM

---

### 6. `test_constraint_demotion_stops_as_invalid_convergence` is a false-green — the stop is caused by `max_hit`, not demotion detection

**File:** `tests/kernel/v1/test_odr_core.py`  
**Function:** `test_constraint_demotion_stops_as_invalid_convergence`

**What it appears to test:** That demotion detection causes the ODR to stop with `INVALID_CONVERGENCE`.

**What it actually tests:** With `max_rounds=2, stable_rounds=1`, after 2 rounds `n == max_rounds` → `max_hit = True`. The test asserts `stop_reason == "INVALID_CONVERGENCE"` and `record["constraint_demotion_violations"]` is non-empty. But `INVALID_CONVERGENCE` fires because `invalid_terminal = circ_hit or diff_hit or max_hit = True` (via `max_hit`), not because demotion detection triggered a terminal condition.

The test would pass even if `_constraint_demotion_violations` returned an empty list, as long as the second round produced a short enough requirement to fall below `diff_floor_pct`. The demotion assertion is correct, but it does not drive the stop reason in the way the test name implies.

**What would actually test the claim:** Use `max_rounds=8, stable_rounds=2` and produce two consecutive nearly-identical demoted requirements. Assert `stop_reason == "INVALID_CONVERGENCE"` via `diff_hit`, not `max_hit`.

---

### 7. `_unresolved_alternative_hits` early-exit gate is inconsistent with the regex it guards

**File:** `orket/kernel/v1/odr/semantic_validity.py`  
**Function:** `_unresolved_alternative_hits`

**What it appears to do:** Fast-path exit when no alternatives exist.

**What it actually does:**

```python
if " or " not in cleaned.lower() and "either" not in cleaned.lower() and "may" not in cleaned.lower():
    return hits
```

The early exit checks for `" or "` (space-padded). But `_UNRESOLVED_ALTERNATIVE_RE` matches `\bor\b` (word boundary). These are not equivalent:

- `"Files or"` (string ending in "or"): the early exit does NOT catch it because `" or "` (with trailing space) isn't present. But `\bor\b` matches `"or"` at the end. The early exit is bypassed, the regex fires anyway — but for this case only if a clause-level check passes, so the inconsistency is mostly harmless.

- More importantly: `"Files\nor"` (newline-separated). `" or "` substring check misses it. `_split_clauses` splits on `\n` → individual clause `"or"` → `\bor\b` matches.

The early exit provides performance optimization but has inconsistent semantics with the regex it guards. If the early exit is meant to be a correctness gate, it should normalize the check to match word boundaries, not space-padded substrings.

---

### 8. `odr_valid` in `live_runner.run_live_refinement` reads from `final_trace` which lacks `validity_verdict` for `CODE_LEAK` and `FORMAT_VIOLATION` stops

**File:** `orket/kernel/v1/odr/live_runner.py`  
**Function:** `run_live_refinement`

**What it appears to do:** Return whether the final ODR output is semantically valid.

**What it actually does:**

```python
validity_verdict = str(final_trace.get("validity_verdict") or "invalid") if isinstance(final_trace, dict) else "invalid"
odr_valid = validity_verdict == "valid"
```

For `CODE_LEAK` and `FORMAT_VIOLATION` stops, the trace record does not contain a `validity_verdict` key (it's only set on the parse-success path in `run_round`). So `final_trace.get("validity_verdict")` returns `None`, which becomes `"invalid"` → `odr_valid = False`.

This is correct in effect (`CODE_LEAK` output is not valid), but `odr_pending_decisions` is also read from `final_trace`:

```python
"odr_pending_decisions": int(final_trace.get("pending_decision_count") or 0)
```

For `CODE_LEAK`, `pending_decision_count` is absent → returns `0`. A caller checking `odr_valid=False` + `odr_pending_decisions=0` would conclude the failure was due to invalid semantics with no pending decisions, not realizing it was actually a code-leak stop. The stop type is in `"odr_stop_reason"` but a consumer using `odr_valid` + `odr_pending_decisions` as diagnostics gets a misleading signal.

**Fix:** When `stop_reason` is `CODE_LEAK` or `FORMAT_VIOLATION`, set `odr_valid = False` with a distinct `odr_failure_mode` field (`"code_leak"` or `"format_violation"`) so callers can distinguish semantic invalidity from structural parsing failures.

---

### 9. `_contradiction_hits` fires on substring containment, not sentence-level co-occurrence

**File:** `orket/kernel/v1/odr/semantic_validity.py`  
**Function:** `_contradiction_hits`

**What it appears to do:** Detect contradictory clauses in the requirement text.

**What it actually does:**

```python
_CONTRADICTION_PAIRS = (
    ("must", "must not"),
    ("should", "should not"),
    ("allow", "disallow"),
    ("encrypt", "not encrypt"),
    ("retain", "delete"),
    ("store locally", "upload"),
)

def _contradiction_hits(text: str) -> List[str]:
    lowered = str(text or "").lower()
    hits: List[str] = []
    for positive, negative in _CONTRADICTION_PAIRS:
        if positive in lowered and negative in lowered:
            hits.append(f"{positive}|{negative}")
    return hits
```

For the pair `("must", "must not")`: any requirement text that contains BOTH "must" and "must not" fires as a contradiction. But `"must not"` contains `"must"` as a substring. So any requirement containing "must not" ALSO satisfies `"must" in lowered` → this pair fires on every requirement that contains `"must not"`, even if there is no contradictory "must" clause.

Example: `"The system must not store data outside the jurisdiction."` → `"must"` matches (substring of `"must not"`) → `"must not"` matches → fires as `"must|must not"` contradiction.

This causes every "must not" requirement to be classified as contradictory and therefore INVALID.

The same problem affects `("allow", "disallow")`: any text containing "disallow" also contains "allow" as a substring.

**Fix:** Check the negative term first and ensure the positive term appears independently. One clean approach: strip all occurrences of the negative term before checking for the positive term:

```python
positive_in_text = positive in lowered.replace(negative, "")
negative_in_text = negative in lowered
if positive_in_text and negative_in_text:
    hits.append(...)
```

---

## 🔵 LOW

---

### 10. `_normalize_token` suffix stripping produces non-standard stems that break `_matches_any`

**File:** `orket/kernel/v1/odr/semantic_validity.py`  
**Function:** `_normalize_token`

```python
for suffix in ("ing", "ed", "es", "s"):
    if len(value) > len(suffix) + 3 and value.endswith(suffix):
        return value[: -len(suffix)]
return value
```

The suffix order causes `"es"` to be tried before `"s"`. So `"deletes"` → ends in `"es"`, len 7 > 5 → strips to `"delet"`. But `"delete"` (the uninflected form) doesn't end in any listed suffix, so it stays as `"delete"`. Token `"delet"` ≠ `"delete"` — `_matches_any` between "must delete data" and "must deletes data" fails. The same applies to "encrypts" → "encrypt" (good, "encrypt" ends in no listed suffix), but "processes" → "process" via `"es"` → `"process"` (works). The inconsistency is most visible with `"deletes"` vs `"delete"`, `"encodes"` vs `"encode"`.

This is unlikely to affect real constraint detection unless the exact forms happen to diverge, but it's an undocumented asymmetry in the matching logic.

---

### 11. `test_pending_decisions_stop_as_unresolved_decisions` asserts `pending_decision_count >= 1` masking which decision was detected

**File:** `tests/kernel/v1/test_odr_core.py`  
**Function:** `test_pending_decisions_stop_as_unresolved_decisions`

The test asserts `record["pending_decision_count"] >= 1`. With the `_unresolved_alternative_hits` false positives described in Issue #1 above, this test would pass for the wrong reason — it passes because "or" in `"rename files based on metadata or a fallback template"` fires `\bor\b`, not because the `OPEN_QUESTIONS` section contains an unresolved decision. 

If Issue #1 is fixed (making the "or" detection less aggressive), this test may fail unless the question in `OPEN_QUESTIONS` ("What naming template should be used when metadata is missing?") is correctly detected as a pending decision via `_meaningful_list`. The `open_questions` path through `pending_decisions` would still catch it, but the test's assertion is not specific enough to confirm which path fired.

---

## Summary Table

| # | Severity | File | Function | Issue |
|---|---|---|---|---|
| 1 | 🔴 Critical | `odr/semantic_validity.py` | `_unresolved_alternative_hits` | `\bor\b` and `\bmay\b` match common English; valid requirements classified INVALID |
| 2 | 🔴 Critical | `odr/metrics.py` | `diff_ratio` | Measures character length change, not textual similarity; same-length different requirements appear convergent |
| 3 | 🟠 High | `odr/core.py` | `run_round` | `stable_count` not reset on valid→invalid transition; STABLE_DIFF_FLOOR can fire on non-consecutive valid rounds |
| 4 | 🟠 High | `odr/semantic_validity.py` | `_constraint_demotion_violations` | Cannot distinguish intentional [REMOVE] from demotion; auditor-requested removals block convergence |
| 5 | 🟠 High | `odr/core.py`, `odr/live_runner.py` | `ReactorState.history_v`, `run_live_refinement` | `history_v` now contains all rounds (valid + invalid); semantic drift vs spec and consumers |
| 6 | 🟡 Medium | `tests/kernel/v1/test_odr_core.py` | `test_constraint_demotion_stops_as_invalid_convergence` | False-green: stop caused by `max_hit`, not demotion detection; demotion trigger path untested |
| 7 | 🟡 Medium | `odr/semantic_validity.py` | `_unresolved_alternative_hits` | Early-exit uses space-padded `" or "` but regex uses `\bor\b`; inconsistent gates |
| 8 | 🟡 Medium | `odr/live_runner.py` | `run_live_refinement` | `odr_valid=False` with `odr_pending_decisions=0` for CODE_LEAK stops gives misleading diagnostic |
| 9 | 🟡 Medium | `odr/semantic_validity.py` | `_contradiction_hits` | `"must not"` contains `"must"` as substring; every "must not" requirement fires as a contradiction |
| 10 | 🔵 Low | `odr/semantic_validity.py` | `_normalize_token` | Suffix stripping order produces `"delet"` not `"delete"`; asymmetric matching |
| 11 | 🔵 Low | `tests/kernel/v1/test_odr_core.py` | `test_pending_decisions_stop_as_unresolved_decisions` | Assertion `>= 1` masks which detection path fired; will pass for wrong reasons if Issue #1 is fixed |

---

## Priority Recommendations

**Do these before running any live ODR benchmarks:**

1. **Fix Issue #9 (`_contradiction_hits` substring overlap) first** — it is a one-line fix and blocks every "must not" requirement. Add the negative-first check described above.

2. **Fix Issue #1 (`_unresolved_alternative_hits`)** — remove `\bor\b` and `\bmay\b` from `_UNRESOLVED_ALTERNATIVE_RE`. Keep `\beither\b.*\bor\b` and `\bdepending on\b`. Test the five published ODR scenarios against the new detector before re-running live.

3. **Fix Issue #2 (`diff_ratio`)** — replace with `1.0 - jaccard_sim(curr, prev, k=3)`. This requires updating the pinned `EXPECTED_*_SHA256` values in `test_odr_determinism_gate.py` since convergence behavior will change.

4. **Fix Issue #3 (`stable_count` reset)** — one line: `next_stable_count = 0` at the start of the invalid branch.

5. **Fix Issue #4 (`_constraint_demotion_violations`)** — pass `patch_classes` and suppress violations covered by explicit `[REMOVE]` patches.

Issues 6–11 can wait for a subsequent pass once the convergence machinery is trustworthy enough to run meaningful benchmarks against.
