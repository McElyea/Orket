# Orket Behavioral Review Round 2 — Remediation Plan

**Source:** `orket_behavioral_review_round2.md` (2026-03-19)  
**Scope:** 11 new behavioral issues in the semantic validity layer, ODR convergence logic, and related tests.  
**Prior plan:** `orket_behavioral_review_remediation_plan.md` — all Wave 1–3 items confirmed resolved.

---

## Guiding Principle

The semantic validity layer is brand-new code with no live benchmark runs behind it yet. The four critical/high issues (1, 2, 3, 9) are all false-positive generators — they cause valid requirements to be classified as invalid. This means every live ODR run with real models will currently terminate as `UNRESOLVED_DECISIONS` or `INVALID_CONVERGENCE` even when the model produces correct, well-formed requirements. Fix these before any benchmarking.

---

## Wave 1 — Fix Before Any Live ODR Run (Critical/High, No Benchmarks Until Done)

### W1-A: Fix `_contradiction_hits` — substring overlap on "must not" and "disallow"

**Issue #9 — 🟡 Medium rated but functionally Critical in practice**  
**File:** `orket/kernel/v1/odr/semantic_validity.py`  
**Function:** `_contradiction_hits`

**Problem:** `"must not"` contains `"must"` as a substring, so any requirement containing "must not" satisfies both `positive in lowered` and `negative in lowered` → fires as a contradiction. Same for `("allow", "disallow")`.

**Fix — exact change:**

```python
def _contradiction_hits(text: str) -> List[str]:
    lowered = str(text or "").lower()
    hits: List[str] = []
    for positive, negative in _CONTRADICTION_PAIRS:
        # Strip all occurrences of the negative form before checking for the
        # positive form, so "must not" does not satisfy the "must" arm.
        positive_in_text = positive in lowered.replace(negative, "")
        negative_in_text = negative in lowered
        if positive_in_text and negative_in_text:
            hits.append(f"{positive}|{negative}")
    return hits
```

**Test to add** in `tests/kernel/v1/test_odr_core.py`:

```python
def test_must_not_alone_does_not_fire_contradiction() -> None:
    """'must not' contains 'must' — must not trigger a contradiction by itself."""
    from orket.kernel.v1.odr.semantic_validity import _contradiction_hits
    text = "The system must not store data outside the jurisdiction."
    assert _contradiction_hits(text) == []

def test_genuine_contradiction_fires() -> None:
    from orket.kernel.v1.odr.semantic_validity import _contradiction_hits
    text = "The system must retain user data. The system must delete user data after 30 days."
    hits = _contradiction_hits(text)
    assert "retain|delete" in hits
```

---

### W1-B: Fix `_unresolved_alternative_hits` — remove `\bor\b` and `\bmay\b`

**Issue #1 — 🔴 Critical**  
**File:** `orket/kernel/v1/odr/semantic_validity.py`  
**Functions:** `_unresolved_alternative_hits`, module-level `_UNRESOLVED_ALTERNATIVE_RE`

**Problem:** `\bor\b` fires on legitimate binary constraints ("must encrypt or hash"). `\bmay\b` fires on RFC 2119 permission language ("may cache results for up to 10 seconds").

**Fix — exact change:**

```python
# Before:
_UNRESOLVED_ALTERNATIVE_RE = re.compile(
    r"\b(either\b.*\bor\b|\bor\b|\bmay\b|\bdepending on\b)", re.IGNORECASE
)

# After:
_UNRESOLVED_ALTERNATIVE_RE = re.compile(
    r"\b(either\b.{1,80}\bor\b|\bdepending on\b)", re.IGNORECASE
)
```

Also update the early-exit gate for consistency:

```python
# Before:
if " or " not in cleaned.lower() and "either" not in cleaned.lower() and "may" not in cleaned.lower():
    return hits

# After:
if "either" not in cleaned.lower() and "depending on" not in cleaned.lower():
    return hits
```

**Rationale:** `either...or` is a genuine ambiguity marker (choosing between two alternatives). `depending on` is also genuine (conditional behavior with undefined conditions). Bare `\bor\b` and `\bmay\b` are too broad to be useful without sentence-level context analysis, which is not available here.

**Tests to add:**

```python
def test_or_in_requirement_does_not_fire_unresolved() -> None:
    from orket.kernel.v1.odr.semantic_validity import _unresolved_alternative_hits
    # Binary constraint: "or" is a valid implementation choice, not an open decision
    assert _unresolved_alternative_hits(
        "The system must encrypt or hash all stored passwords."
    ) == []

def test_may_in_requirement_does_not_fire_unresolved() -> None:
    from orket.kernel.v1.odr.semantic_validity import _unresolved_alternative_hits
    # RFC 2119 "may" = optional permitted behavior
    assert _unresolved_alternative_hits(
        "The cache layer may store results for up to 10 seconds."
    ) == []

def test_either_or_fires_unresolved() -> None:
    from orket.kernel.v1.odr.semantic_validity import _unresolved_alternative_hits
    # Genuine open decision: "either X or Y" with no specification of which
    hits = _unresolved_alternative_hits(
        "The system must use either AES-128 or AES-256 for encryption."
    )
    assert len(hits) >= 1

def test_depending_on_fires_unresolved() -> None:
    from orket.kernel.v1.odr.semantic_validity import _unresolved_alternative_hits
    hits = _unresolved_alternative_hits(
        "Retention must be 30 or 90 days depending on account tier."
    )
    assert len(hits) >= 1
```

---

### W1-C: Fix `diff_ratio` — replace character length delta with Jaccard distance

**Issue #2 — 🔴 Critical**  
**File:** `orket/kernel/v1/odr/metrics.py`  
**Function:** `diff_ratio`

**Problem:** Current implementation measures `|len(curr) - len(prev)| / len(prev)`. Two completely different requirements of equal length return `0.0`, triggering false convergence.

**Fix — exact change:**

```python
# Before:
def diff_ratio(curr: str, prev: str) -> float:
    return abs(len(str(curr)) - len(str(prev))) / max(1, len(str(prev)))

# After:
def diff_ratio(curr: str, prev: str) -> float:
    """
    Semantic distance between two requirement strings.
    Returns 0.0 for identical content, 1.0 for completely disjoint content.
    Uses 1 - Jaccard similarity on 3-shingles, consistent with loop detection.
    """
    sim = jaccard_sim(curr, prev, k=3)
    return 1.0 - sim
```

**Critical downstream effect — pinned SHA256 hashes must be regenerated.** The convergence behavior of every ODR fixture changes because `diff_ratio` values change. The torture pack fixture rounds currently converge via `STABLE_DIFF_FLOOR` because the three requirements (`epsilon.`, `epsilon!`, `epsilon?`) have similar lengths. With the new metric, they have very high Jaccard similarity (near-identical token sets) and will still converge, but at a different round count — meaning the canonical hash of the output changes.

**Steps to regenerate pinned hashes:**

1. Apply the `diff_ratio` fix.
2. Run the determinism gate with `--print-canon-hash` to capture new expected values:

```bash
python tools/repro_odr_gate.py \
    --fixture tests/kernel/v1/vectors/odr/odr_torture_pack.json \
    --seed 1729 --perm-index 0 --print-canon-hash

python tools/repro_odr_gate.py \
    --fixture tests/kernel/v1/vectors/odr/odr_near_miss.json \
    --seed 1729 --perm-index 0 --print-canon-hash
```

3. Update `test_odr_determinism_gate.py`:

```python
# Replace with values from step 2:
EXPECTED_TORTURE_SHA256 = "<new hash from repro_odr_gate>"
EXPECTED_NEAR_MISS_SHA256 = "<new hash from repro_odr_gate>"
# EXPECTED_HEADER_ORDER_SHA256 should be unaffected (FORMAT_VIOLATION stops before diff_ratio runs)
```

4. Re-run the full determinism gate to confirm stability:

```bash
python -m pytest tests/kernel/v1/test_odr_determinism_gate.py -v
```

**Test to add** that directly validates the fix:

```python
def test_diff_ratio_same_length_different_content_is_nonzero() -> None:
    from orket.kernel.v1.odr.metrics import diff_ratio
    a = "must store data locally on device here"   # 39 chars
    b = "must upload data remotely to cloud now"   # 39 chars
    ratio = diff_ratio(a, b)
    assert ratio > 0.3, (
        f"diff_ratio={ratio:.4f} — two semantically opposite requirements of equal "
        "length must not appear convergent"
    )

def test_diff_ratio_identical_content_is_zero() -> None:
    from orket.kernel.v1.odr.metrics import diff_ratio
    text = "The system must encrypt all stored credentials at rest."
    assert diff_ratio(text, text) == 0.0
```

---

### W1-D: Reset `stable_count` on invalid rounds

**Issue #3 — 🟠 High**  
**File:** `orket/kernel/v1/odr/core.py`  
**Function:** `run_round`

**Problem:** When a round is invalid, `next_stable_count` carries forward unchanged. Valid rounds from before the invalid block contribute to convergence despite not being consecutive.

**Fix — exact change** (in the `else` branch of the semantic verdict check):

```python
# Before:
else:
    invalid_history_v = [*state.invalid_history_v, current_requirement]
    next_invalid_stable_count, diff_hit, circ_hit = _advance_history_metrics(
        history=invalid_history_v,
        prior_stable_count=state.invalid_stable_count,
        cfg=cfg,
        metrics=metrics,
    )
    metrics["invalid_stable_count"] = int(next_invalid_stable_count)

# After:
else:
    next_stable_count = 0   # ← reset valid stable count on any invalid round
    invalid_history_v = [*state.invalid_history_v, current_requirement]
    next_invalid_stable_count, diff_hit, circ_hit = _advance_history_metrics(
        history=invalid_history_v,
        prior_stable_count=state.invalid_stable_count,
        cfg=cfg,
        metrics=metrics,
    )
    metrics["invalid_stable_count"] = int(next_invalid_stable_count)
```

**Test to add:**

```python
def test_stable_count_resets_when_valid_round_followed_by_invalid() -> None:
    """Valid stable count must reset when an invalid round interrupts the sequence."""
    cfg = ReactorConfig(diff_floor_pct=0.99, stable_rounds=2)
    state = ReactorState()

    # Round 1: valid, stable_count → 1
    state = run_round(state, _architect("same text here for testing"), _auditor(), cfg)
    assert state.stable_count == 1
    assert state.stop_reason is None

    # Round 2: valid, stable_count → 2 → should NOT stop yet (need stable_rounds=2
    # consecutive, and this is only round 2, so diff compares rounds 1 and 2)
    # Insert an invalid round between them
    invalid_architect = (
        "### REQUIREMENT\n"
        "The system may either do X or Y depending on configuration.\n\n"  # triggers unresolved (with old regex)
        "### CHANGELOG\n- changed\n\n"
        "### ASSUMPTIONS\n- a\n\n"
        "### OPEN_QUESTIONS\n- none\n"
    )
    # Use a requirement with explicit DECISION_REQUIRED to guarantee invalid verdict
    decision_architect = (
        "### REQUIREMENT\n"
        "DECISION_REQUIRED(retention_days): retention period not yet specified.\n\n"
        "### CHANGELOG\n- changed\n\n"
        "### ASSUMPTIONS\n- a\n\n"
        "### OPEN_QUESTIONS\n- none\n"
    )
    state = run_round(state, decision_architect, _auditor(), cfg)
    assert state.stop_reason is None
    # After the invalid round, stable_count must have been reset
    assert state.stable_count == 0, (
        f"stable_count={state.stable_count} — valid stable count must reset after an invalid round"
    )
```

---

### W1-E: Suppress demotion violations covered by explicit `[REMOVE]` patches

**Issue #4 — 🟠 High**  
**File:** `orket/kernel/v1/odr/semantic_validity.py`  
**Functions:** `_constraint_demotion_violations`, `evaluate_semantic_validity`

**Problem:** Auditor `[REMOVE]` patches direct the architect to remove clauses, but the demotion validator fires when the architect follows that instruction. This makes `[REMOVE]` patches unusable — the auditor tool is wired to block its own instructions.

**Fix — pass patch_classes to demotion check:**

In `evaluate_semantic_validity`:

```python
# Before:
demotion_violations = _constraint_demotion_violations(
    previous_requirement=previous_requirement,
    current_requirement=requirement,
    assumptions=assumptions,
    open_questions=open_questions,
)

# After:
remove_patch_texts = [
    row["text"] for row in patch_classes if row["patch_class"] == "REMOVE"
]
demotion_violations = _constraint_demotion_violations(
    previous_requirement=previous_requirement,
    current_requirement=requirement,
    assumptions=assumptions,
    open_questions=open_questions,
    authorized_removals=remove_patch_texts,
)
```

In `_constraint_demotion_violations`, add the `authorized_removals` parameter:

```python
def _constraint_demotion_violations(
    *,
    previous_requirement: str,
    current_requirement: str,
    assumptions: Sequence[str],
    open_questions: Sequence[str],
    authorized_removals: Sequence[str] | None = None,
) -> List[str]:
    previous = _required_clauses(previous_requirement)
    current = _required_clauses(current_requirement)
    sidecar = _required_clauses("\n".join([*assumptions, *open_questions]))
    authorized_text = "\n".join(authorized_removals or [])
    authorized = _required_clauses(authorized_text) if authorized_text.strip() else []
    violations: List[str] = []
    for clause in previous:
        if _matches_any(clause, current):
            continue
        if _matches_any(clause, sidecar):
            violations.append(clause)
            continue
        if authorized and _matches_any(clause, authorized):
            continue   # ← authorized by explicit [REMOVE] patch — not a violation
        if _matches_any(clause, sidecar):
            violations.append(clause)
    return violations
```

Wait — the original logic is: fire if clause is absent from current AND present in sidecar (demoted). The fix is slightly different — fire only if absent from current, not covered by an authorized removal, and not simply dropped without explanation. Revised:

```python
def _constraint_demotion_violations(
    *,
    previous_requirement: str,
    current_requirement: str,
    assumptions: Sequence[str],
    open_questions: Sequence[str],
    authorized_removals: Sequence[str] | None = None,
) -> List[str]:
    previous = _required_clauses(previous_requirement)
    current = _required_clauses(current_requirement)
    sidecar = _required_clauses("\n".join([*assumptions, *open_questions]))
    authorized = _required_clauses("\n".join(authorized_removals or []))
    violations: List[str] = []
    for clause in previous:
        if _matches_any(clause, current):
            continue   # still present in REQUIREMENT — no issue
        if authorized and _matches_any(clause, authorized):
            continue   # explicitly authorized for removal by auditor [REMOVE] patch
        if _matches_any(clause, sidecar):
            violations.append(clause)  # demoted to sidecar — violation
    return violations
```

**Test to add:**

```python
def test_remove_patch_suppresses_demotion_violation() -> None:
    from orket.kernel.v1.odr.semantic_validity import evaluate_semantic_validity

    previous_data = {
        "requirement": "The system must encrypt all backups at rest.",
        "changelog": [],
        "assumptions": [],
        "open_questions": [],
    }
    current_data = {
        "requirement": "The system handles backups.",
        "changelog": ["removed encryption clause per auditor"],
        "assumptions": [],
        "open_questions": [],
    }
    auditor_data = {
        "critique": ["Encryption clause incorrect — no at-rest requirement"],
        "patches": ["[REMOVE] The encryption at rest requirement is not applicable here."],
        "edge_cases": [],
        "test_gaps": [],
    }
    result = evaluate_semantic_validity(
        architect_data=current_data,
        auditor_data=auditor_data,
        previous_architect_data=previous_data,
    )
    assert result["constraint_demotion_violations"] == [], (
        "A [REMOVE] patch should authorize removal without triggering a demotion violation"
    )
```

---

## Wave 2 — Medium Issues (After Wave 1 Is Green)

### W2-A: Expose `valid_history_v` in `ReactorState` output and clarify `history_v` semantics

**Issue #5 — 🟠 High**  
**Files:** `orket/kernel/v1/odr/core.py`, `orket/kernel/v1/odr/live_runner.py`

`history_v` now contains all rounds (valid + invalid mixed). Callers treat it as the convergence trace. Update `live_runner.run_live_refinement` to expose both:

```python
return {
    "task": str(task),
    "rounds": rounds,
    "rounds_completed": len(state.history_rounds),
    "stop_reason": stop_reason or None,
    "history_v": list(state.history_v),          # all attempts (for tracing)
    "valid_history_v": list(state.valid_history_v),  # convergence trace
    "history_rounds": list(state.history_rounds),
    "final_requirement": final_requirement,
    "final_trace": final_trace,
    "odr_valid": odr_valid,
    ...
}
```

Also check whether `max_hit = n == int(cfg.max_rounds)` should use `len(valid_history_v)` rather than `len(history_v)`. Document the decision explicitly in a comment either way — right now there is no comment and the choice is silent.

---

### W2-B: Add `odr_failure_mode` to `run_live_refinement` return value for non-semantic stops

**Issue #8 — 🟡 Medium**  
**File:** `orket/kernel/v1/odr/live_runner.py`  
**Function:** `run_live_refinement`

Add explicit stop-type discrimination:

```python
if stop_reason in {"CODE_LEAK", "FORMAT_VIOLATION"}:
    odr_failure_mode = stop_reason.lower()
elif not odr_valid:
    odr_failure_mode = "semantic_invalid"
else:
    odr_failure_mode = None

return {
    ...
    "odr_valid": odr_valid,
    "odr_failure_mode": odr_failure_mode,   # ← new field
    "odr_pending_decisions": ...,
    ...
}
```

---

### W2-C: Fix `test_constraint_demotion_stops_as_invalid_convergence` — test must stop via `diff_hit`, not `max_hit`

**Issue #6 — 🟡 Medium**  
**File:** `tests/kernel/v1/test_odr_core.py`  
**Function:** `test_constraint_demotion_stops_as_invalid_convergence`

Replace the current test with one that verifies demotion actually drives the stop reason through convergence detection, not via `max_hit`:

```python
def test_constraint_demotion_stops_as_invalid_convergence_via_diff_floor() -> None:
    """
    INVALID_CONVERGENCE must be triggered by stable invalid rounds (diff_hit),
    not by max_hit. This test uses enough rounds that max_hit cannot be the cause.
    """
    # high max_rounds, low stable_rounds — convergence, not exhaustion
    cfg = ReactorConfig(max_rounds=8, diff_floor_pct=0.99, stable_rounds=1)
    state = ReactorState()

    demoted = (
        "### REQUIREMENT\n"
        "The system handles backups.\n\n"
        "### CHANGELOG\n- changed\n\n"
        "### ASSUMPTIONS\n- All backups remain encrypted at rest.\n\n"
        "### OPEN_QUESTIONS\n- none\n"
    )
    # Run two nearly identical demoted requirements — triggers invalid diff_hit
    state = run_round(state, _architect("The system must encrypt all backups at rest."), _auditor(), cfg)
    state = run_round(state, demoted, _auditor(), cfg)
    state = run_round(state, demoted, _auditor(), cfg)  # second identical demoted round

    assert state.stop_reason == "INVALID_CONVERGENCE", (
        f"Expected INVALID_CONVERGENCE via diff_hit, got {state.stop_reason}"
    )
    record = state.history_rounds[-1]
    assert record["validity_verdict"] == "invalid"
    assert record["constraint_demotion_violations"], "demotion violations must be present"
    # Confirm it was diff_hit, not max_hit (n=3, max_rounds=8)
    assert record["metrics"]["stable_count"] == 0  # valid stable_count was reset
    assert int(record["metrics"]["invalid_stable_count"]) >= 1
```

---

### W2-D: Fix `_normalize_token` suffix order to produce standard stems

**Issue #10 — 🔵 Low**  
**File:** `orket/kernel/v1/odr/semantic_validity.py`  
**Function:** `_normalize_token`

```python
# Before:
for suffix in ("ing", "ed", "es", "s"):

# After:
for suffix in ("ing", "ed", "es", "e", "s"):
```

Adding `"e"` before `"s"` ensures `"delete"` (no suffix) and `"deletes"` (→ `"delet"` via `"es"`) still diverge, but `"encode"` → strips nothing and `"encodes"` → strips `"es"` → `"encod"`. This is still imperfect. The clean fix is to use a proper stemmer (e.g., Porter) or simply document that `_normalize_token` is a heuristic and add a comment explaining its known asymmetry:

```python
def _normalize_token(token: str) -> str:
    # Minimal suffix stripping heuristic. Not a standards-compliant stemmer.
    # Known asymmetry: "deletes" → "delet", "delete" → "delete".
    # Acceptable for overlap detection; do not rely on it for exact matching.
    value = str(token or "").strip().lower()
    for suffix in ("ing", "ed", "es", "s"):
        if len(value) > len(suffix) + 3 and value.endswith(suffix):
            return value[: -len(suffix)]
    return value
```

---

### W2-E: Tighten `test_pending_decisions_stop_as_unresolved_decisions` assertion

**Issue #11 — 🔵 Low**  
**File:** `tests/kernel/v1/test_odr_core.py`  
**Function:** `test_pending_decisions_stop_as_unresolved_decisions`

After W1-B (removing `\bor\b` from the regex), this test must pass via the `OPEN_QUESTIONS` path, not via the now-removed "or" trigger. Add an assertion that the pending decision comes from the open questions:

```python
def test_pending_decisions_stop_as_unresolved_decisions() -> None:
    cfg = ReactorConfig(max_rounds=1, diff_floor_pct=0.05, stable_rounds=1)
    state = ReactorState()
    architect = (
        "### REQUIREMENT\n"
        "The tool must rename files based on metadata.\n\n"
        "### CHANGELOG\n- changed\n\n"
        "### ASSUMPTIONS\n- a1\n\n"
        "### OPEN_QUESTIONS\n"
        "- What naming template should be used when metadata is missing?\n"
    )
    state = run_round(state, architect, _auditor(), cfg)
    assert state.stop_reason == "UNRESOLVED_DECISIONS"
    record = state.history_rounds[-1]
    assert record["validity_verdict"] == "invalid"
    assert record["pending_decision_count"] >= 1
    # The pending decision must come from OPEN_QUESTIONS, not from a false positive
    pending = record.get("pending_decisions", [])
    assert any("naming template" in str(p).lower() for p in pending), (
        "Expected the OPEN_QUESTIONS item to appear in pending_decisions"
    )
```

---

## Completion Checklist

| # | Item | Wave | Done |
|---|---|---|---|
| W1-A | Fix `_contradiction_hits` substring overlap | 1 | yes |
| W1-B | Fix `_unresolved_alternative_hits` — remove `\bor\b` and `\bmay\b` | 1 | yes |
| W1-C | Fix `diff_ratio` — replace with Jaccard; regenerate pinned SHA256 hashes | 1 | yes |
| W1-D | Reset `stable_count = 0` in invalid branch of `run_round` | 1 | yes |
| W1-E | Pass `authorized_removals` to `_constraint_demotion_violations` | 1 | yes |
| W2-A | Expose `valid_history_v` in `live_runner` output; document `max_hit` choice | 2 | yes |
| W2-B | Add `odr_failure_mode` field to `run_live_refinement` return | 2 | yes |
| W2-C | Fix `test_constraint_demotion_stops_as_invalid_convergence` to use `diff_hit` | 2 | yes |
| W2-D | Document `_normalize_token` asymmetry (or fix suffix order) | 2 | yes |
| W2-E | Tighten `test_pending_decisions` assertion to pin which path fired | 2 | yes |

---

## Verification Gate for Wave 1

Run this before proceeding to Wave 2 or any live ODR benchmarks:

```bash
python -m pytest -q \
    tests/kernel/v1/test_odr_core.py \
    tests/kernel/v1/test_odr_determinism_gate.py \
    tests/kernel/v1/test_odr_leak_policy_balanced.py \
    tests/kernel/v1/test_odr_refinement_behavior.py
```

All four files must pass. `test_odr_determinism_gate.py` will fail until the pinned SHA256 hashes are regenerated per W1-C. That regeneration step is mandatory — do not skip it or comment out the hash assertions.

After Wave 1 passes, re-run `run_odr_7b_baseline.py` with `qwen2.5-coder:7b` and `qwen2.5:7b`. The `UNRESOLVED_DECISIONS` results that were occurring in all five P-02 baseline runs should now either converge properly or fail for a real reason.

Status on 2026-03-19:

1. The Wave 1 gate passed:
   `python -m pytest -q tests/kernel/v1/test_odr_core.py tests/kernel/v1/test_odr_determinism_gate.py tests/kernel/v1/test_odr_leak_policy_balanced.py tests/kernel/v1/test_odr_refinement_behavior.py`
2. `python tools/repro_odr_gate.py --fixture tests/kernel/v1/vectors/odr/odr_torture_pack.json --seed 1729 --perm-index 0 --print-canon-hash` confirmed `EXPECTED_TORTURE_SHA256=d4d8e1d66653270c84d84f373dbba011574f9d1b7757f12434255df2243f57f5`.
3. `python tools/repro_odr_gate.py --fixture tests/kernel/v1/vectors/odr/odr_near_miss.json --seed 1729 --perm-index 0 --print-canon-hash` produced `EXPECTED_NEAR_MISS_SHA256=29bea1a72385d2f3abe7d44345f541abf3bd32b0c482348b4135785a13a5c403`.
4. Both required live models passed preflight:
   `ORKET_DISABLE_SANDBOX=1 python scripts/providers/check_model_provider_preflight.py --provider ollama --model-id qwen2.5-coder:7b --smoke-stream`
   `ORKET_DISABLE_SANDBOX=1 python scripts/providers/check_model_provider_preflight.py --provider ollama --model-id qwen2.5:7b --smoke-stream`
5. `ORKET_DISABLE_SANDBOX=1 python scripts/odr/run_odr_7b_baseline.py --architect-models qwen2.5-coder:7b --auditor-models qwen2.5:7b --out .tmp/behavioral-review-round2_odr_7b_baseline.json` completed live and produced `UNRESOLVED_DECISIONS` in all three scenario runs with `code_leak_rate=0.0` and `format_violation_rate=0.0`; the remaining failures were model-authored open questions in `OPEN_QUESTIONS` rather than false-positive semantic hits.
6. `ORKET_DISABLE_SANDBOX=1 python scripts/probes/p02_odr_isolation.py --model qwen2.5-coder:7b --runs 5 --output .tmp/behavioral-review-round2_p02_odr_isolation.json --json` completed live with `stop_reason_distribution={"UNRESOLVED_DECISIONS": 1, "STABLE_DIFF_FLOOR": 4}`. The prior all-`UNRESOLVED_DECISIONS` baseline no longer reproduces.
