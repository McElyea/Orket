# Orket Remediation Plan — Round 4

**Date:** 2026-03-20  
**Status:** Completed 2026-03-20  
**Source:** Live benchmark results from `run_odr_7b_baseline.py` and `run_odr_single_vs_coordinated.py`  
**Prior plan:** Round 3 — Wave 1 complete (W1-A, W1-B, W1-C, W2-A confirmed closed)

---

## What the Benchmarks Actually Say

Before fixing anything, it is worth being precise about what the benchmark
results mean.

**7B Baseline:** 0/3 convergence, all `UNRESOLVED_DECISIONS`, `format_violation_rate=0.0`.
Format is not the problem. The models can follow the four-section structure.
The problem is semantic: the models surface open decisions they cannot resolve.

**Single vs Coordinated:** 0/3 coordinated convergence, 9.91x latency overhead,
mean diff from single-shot 0.8864. Coordinated is slower and worse on every
measured proxy.

**What this does not mean:** It does not mean the ODR thesis is wrong or that 7B
models cannot coordinate. It means the current combination of prompt contract,
semantic validity rules, and benchmark scenarios is generating a failure mode
that looks like non-convergence but is actually a detector problem plus a
scenario design problem.

**The two actual root causes:**

**Root cause 1 — Contradiction detector has unavoidable false positives with
the current approach.** The pair `("must", "must not")` fires on any requirement
that contains both tokens — e.g., "The system must encrypt data. The system must
not store PII externally." These are not contradictory but the detector treats
them as contradictions. `("should", "should not")` has the same problem. When
`contradictions` fires, the round is invalid, the model is told to fix it, and
the only "fix" available to the model is to remove one of the clauses — which
may itself trigger a demotion violation. The detector is producing oscillation,
not convergence.

**Root cause 2 — OPEN_QUESTIONS are treated as unresolved decisions.** In
`evaluate_semantic_validity`, `pending_decisions = [*explicit_decisions,
*open_questions, *unresolved_alternatives]`. Any non-empty OPEN_QUESTIONS
section triggers `pending_decisions`, which triggers `UNRESOLVED_DECISIONS` at
max rounds. But the prompt contract instructs the architect: "OPEN_QUESTIONS may
only contain optional follow-up questions." Optional questions are not required
decisions. The model follows the instruction, puts optional questions in
OPEN_QUESTIONS, and the detector penalizes it as if they were blocking decisions.

The models are not failing — they are doing what the prompt says. The detector
is punishing them for it.

---

## Wave 1 — Semantic Detector Repairs (Do Before Next Benchmark Run)

---

### W1-A — Narrow `_contradiction_hits` to clause-scoped detection

**Status:** ✅  
**Effort:** 45 minutes  
**File:** `orket/kernel/v1/odr/semantic_validity.py`

**Problem:** The pair `("must", "must not")` fires whenever both tokens appear
anywhere in the requirement text, even in completely unrelated clauses. A
requirement like "Must encrypt data. Must not store PII externally." correctly
contains both "must" and "must not" but is not self-contradictory — the two
tokens modify different subjects.

The same applies to `("should", "should not")`. The pairs `("retain", "delete")`
and `("store locally", "upload")` are more legitimate because those are genuinely
semantic opposites applied to the same subject (audit records, user data).

**Fix — split the pairs into two tiers:**

```python
# BEFORE:
_CONTRADICTION_PAIRS = (
    ("must", "must not"),
    ("should", "should not"),
    ("allow", "disallow"),
    ("encrypt", "not encrypt"),
    ("retain", "delete"),
    ("store locally", "upload"),
)

# AFTER:
# Tier 1: Semantic opposites — fire only when same clause-level subject context.
# These are genuine domain contradictions.
_CONTRADICTION_PAIRS_SEMANTIC = (
    ("retain", "delete"),
    ("store locally", "upload"),
    ("encrypt", "not encrypt"),
)

# Tier 2: Modal negation — fire only when the same object appears in both a
# positive and negative modal clause. These are too common in valid requirements
# (must X AND must not Y) to use full-text matching.
# These require clause-level subject extraction before firing.
# For now: DISABLED until a clause-scoped implementation is available.
_CONTRADICTION_PAIRS_MODAL: tuple[tuple[str, str], ...] = ()
```

Replace the `_contradiction_hits` function:

```python
def _contradiction_hits(text: str) -> List[str]:
    """
    Detect genuine semantic contradictions.

    Modal pairs like (must, must not) and (should, should not) are excluded
    because they produce false positives on any requirement that contains both
    a positive and a negative obligation — which is extremely common in valid
    multi-constraint requirements.

    Only domain-specific semantic opposites are checked here.
    """
    lowered = str(text or "").lower()
    hits: List[str] = []
    for positive, negative in _CONTRADICTION_PAIRS_SEMANTIC:
        positive_in_text = positive in lowered.replace(negative, "")
        negative_in_text = negative in lowered
        if positive_in_text and negative_in_text:
            hits.append(f"{positive}|{negative}")
    return hits
```

Update `_CONTRADICTION_PAIRS` to point to the semantic tier so existing
references in tests still work:

```python
# Keep backward-compat alias for tests that import _CONTRADICTION_PAIRS directly
_CONTRADICTION_PAIRS = _CONTRADICTION_PAIRS_SEMANTIC
```

**Update the tests in `test_odr_semantic_validity.py`:**

```python
def test_contradiction_hits_must_not_alone_does_not_fire() -> None:
    text = "The system must not store data outside the jurisdiction."
    assert _contradiction_hits(text) == []


def test_contradiction_hits_must_plus_must_not_different_subjects_does_not_fire() -> None:
    """Must X and must not Y with different subjects is NOT a contradiction."""
    text = "The system must encrypt data. The system must not store PII externally."
    assert _contradiction_hits(text) == [], (
        f"Got: {_contradiction_hits(text)} — modal negation must not fire on "
        "different-subject clauses"
    )


def test_contradiction_hits_should_plus_should_not_does_not_fire() -> None:
    """Same as above for 'should'."""
    text = "Logs should be rotated weekly. Logs should not be deleted before audit."
    assert _contradiction_hits(text) == []


def test_contradiction_hits_retain_delete_fires() -> None:
    text = "Must retain audit records. Must delete records immediately after use."
    hits = _contradiction_hits(text)
    assert "retain|delete" in hits


def test_contradiction_hits_store_locally_upload_fires() -> None:
    text = "Must store profile data locally only. Must upload profile data to remote."
    hits = _contradiction_hits(text)
    assert "store locally|upload" in hits
```

**Expected change to benchmark results:** The `missing_constraint` and
`overfitting` scenarios that were producing spurious `contradiction_hits` will no
longer fire on modal patterns. The `contradiction` scenario will continue to fire
on `retain|delete` which is a real contradiction in that fixture.

---

### W1-B — Stop treating OPEN_QUESTIONS as blocking decisions

**Status:** ✅  
**Effort:** 30 minutes  
**File:** `orket/kernel/v1/odr/semantic_validity.py`

**Problem:** The current pipeline:

```python
pending_decisions = [*explicit_decisions, *open_questions, *unresolved_alternatives]
```

includes every non-empty OPEN_QUESTIONS item as a pending decision. The prompt
contract explicitly says OPEN_QUESTIONS "may only contain optional follow-up
questions." Optional questions are not required decisions. A model following the
prompt correctly will be penalized for putting genuinely optional questions in
the correct section.

This means: any requirement that has even one non-trivial optional question is
classified `invalid` and will eventually stop as `UNRESOLVED_DECISIONS` instead
of `STABLE_DIFF_FLOOR`. The model cannot converge unless OPEN_QUESTIONS is
literally empty or contains only "- none."

**Fix — remove `open_questions` from `pending_decisions`:**

```python
# BEFORE:
pending_decisions = [*explicit_decisions, *open_questions, *unresolved_alternatives]

# AFTER:
# Only explicit DECISION_REQUIRED markers and unresolved alternatives in REQUIREMENT
# text count as blocking decisions. OPEN_QUESTIONS are optional by contract and
# must not prevent convergence.
pending_decisions = [*explicit_decisions, *unresolved_alternatives]
```

`open_questions` can still be reported in the trace output for observability but
should not contribute to `pending_decision_count` or trigger `UNRESOLVED_DECISIONS`.

To preserve the distinction in the trace, add a separate field:

```python
    return {
        "validity_verdict": "valid" if not failures else "invalid",
        "semantic_failures": failures,
        "pending_decision_count": len(pending_decisions),
        "pending_decisions": pending_decisions,
        "open_questions": open_questions,           # ← add: non-blocking, informational
        "open_question_count": len(open_questions), # ← add
        ...
    }
```

**Update tests in `test_odr_semantic_validity.py`:**

```python
def test_optional_open_question_does_not_block_convergence() -> None:
    """
    OPEN_QUESTIONS contains an optional follow-up, not a required decision.
    Must not contribute to pending_decision_count or cause invalid verdict.
    """
    result = evaluate_semantic_validity(
        architect_data={
            "requirement": "The system must encrypt all stored credentials using AES-256.",
            "changelog": ["added encryption constraint"],
            "assumptions": [],
            "open_questions": ["Should we also support ChaCha20 for mobile clients?"],
        },
        auditor_data={
            "critique": ["c1"],
            "patches": ["[ADD] p1"],
            "edge_cases": ["e1"],
            "test_gaps": ["t1"],
        },
        previous_architect_data=None,
    )
    assert result["validity_verdict"] == "valid", (
        f"Optional open questions must not invalidate an otherwise clean requirement. "
        f"failures={result['semantic_failures']}"
    )
    assert result["pending_decision_count"] == 0
    # But the question is still tracked
    assert result["open_question_count"] >= 1


def test_decision_required_in_requirement_still_blocks() -> None:
    """DECISION_REQUIRED in the REQUIREMENT section is still a blocking decision."""
    result = evaluate_semantic_validity(
        architect_data={
            "requirement": "DECISION_REQUIRED(encryption_algo): algorithm not yet chosen.",
            "changelog": [],
            "assumptions": [],
            "open_questions": [],
        },
        auditor_data={"critique": [], "patches": [], "edge_cases": [], "test_gaps": []},
        previous_architect_data=None,
    )
    assert result["validity_verdict"] == "invalid"
    assert result["pending_decision_count"] >= 1
```

**Update `test_odr_core.py`** — the `test_pending_decisions_stop_as_unresolved_decisions`
test uses a question in OPEN_QUESTIONS as the pending decision trigger. After this
change, that question will no longer block. Update the test to use an explicit
`DECISION_REQUIRED` marker instead:

```python
def test_pending_decisions_stop_as_unresolved_decisions() -> None:
    cfg = ReactorConfig(max_rounds=1, diff_floor_pct=0.05, stable_rounds=1)
    state = ReactorState()
    architect = (
        "### REQUIREMENT\n"
        "The tool must rename files. DECISION_REQUIRED(naming_template): "
        "no fallback template specified.\n\n"
        "### CHANGELOG\n"
        "- changed\n\n"
        "### ASSUMPTIONS\n"
        "- a1\n\n"
        "### OPEN_QUESTIONS\n"
        "- none\n"
    )
    state = run_round(state, architect, _auditor(), cfg)
    assert state.stop_reason == "UNRESOLVED_DECISIONS"
    record = state.history_rounds[-1]
    assert record["validity_verdict"] == "invalid"
    assert record["pending_decision_count"] >= 1
    assert any("naming_template" in str(p).lower() for p in record["pending_decisions"])
```

**Expected change to benchmark results:** The `missing_constraint` and
`overfitting` scenarios that were stopping as `UNRESOLVED_DECISIONS` because the
model put optional questions in OPEN_QUESTIONS will now be able to converge. Only
scenarios with explicit `DECISION_REQUIRED` markers or genuine `either...or`
ambiguity in the REQUIREMENT section will remain blocked.

---

### W1-C — Fix the benchmark summary interpretation logic

**Status:** ✅  
**Effort:** 20 minutes  
**File:** `scripts/odr/run_odr_7b_baseline.py`

**Problem:** The `_interpret_7b_results` function emits a `FAIL_NO_CONVERGENCE`
note that blames "format maintenance" even when `format_violation_rate=0.0`. Jon
already partially patched this but the artifact from the previous run still
contains the stale interpretation, and the function doesn't distinguish the
dominant failure mode precisely enough.

**Fix — update `_interpret_7b_results`:**

```python
def _interpret_7b_results(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"verdict": "NO_DATA"}

    best = rows[0]
    all_zero_convergence = all(r["convergence_rate"] == 0.0 for r in rows)
    high_code_leak = any(r["code_leak_rate"] > 0.5 for r in rows)
    high_format_violation = any(r["format_violation_rate"] > 0.5 for r in rows)

    # Determine the dominant stop-reason across all pairings
    all_stop_reasons: dict[str, int] = {}
    for r in rows:
        for reason, count in r.get("stop_reason_distribution", {}).items():
            all_stop_reasons[reason] = all_stop_reasons.get(reason, 0) + count
    dominant_stop = max(all_stop_reasons, key=lambda k: all_stop_reasons[k]) if all_stop_reasons else "NONE"

    if all_zero_convergence:
        # Distinguish failure mode from dominant stop reason
        if high_format_violation:
            failure_mode = "format_instability"
            failure_note = (
                "Models cannot reliably maintain the required structured format across rounds. "
                "Consider prompt hardening or a format-correction pre-pass before entering the loop."
            )
        elif dominant_stop == "UNRESOLVED_DECISIONS":
            failure_mode = "semantic_non_convergence_unresolved_decisions"
            failure_note = (
                "Models surface required decisions they cannot resolve from available context. "
                "The requirement tasks may need seeded decision values, or the auditor prompt "
                "needs to push the architect to commit to specific values rather than deferring."
            )
        elif dominant_stop == "CODE_LEAK":
            failure_mode = "code_leak"
            failure_note = (
                "Models are producing source code in requirement text. "
                "Consider using a general-purpose model as architect rather than a coder model."
            )
        else:
            failure_mode = f"non_convergence_{dominant_stop.lower()}"
            failure_note = f"Dominant stop reason was {dominant_stop}."

        verdict = "FAIL_NO_CONVERGENCE"
        notes = [
            f"No model pair achieved ODR convergence. Dominant failure mode: {failure_mode}.",
            failure_note,
        ]
    elif best["convergence_rate"] >= 0.6:
        verdict = "PASS_USABLE"
        notes = [
            f"Best pair {best['architect_model']} / {best['auditor_model']} "
            f"converged on {int(best['convergence_rate'] * 100)}% of scenarios."
        ]
        failure_mode = "none"
    else:
        verdict = "PARTIAL_MIXED"
        failure_mode = "partial"
        notes = [
            f"Best pair achieved {int(best['convergence_rate'] * 100)}% convergence — usable but unreliable."
        ]

    if high_code_leak:
        notes.append(
            "WARNING: High CODE_LEAK rate. Coder-specialized models frequently emit source code "
            "in requirement text. Use a general-purpose model as architect."
        )
    if high_format_violation:
        notes.append(
            "WARNING: High FORMAT_VIOLATION rate. Models are missing required section headers."
        )

    return {
        "verdict": verdict,
        "failure_mode": failure_mode,
        "dominant_stop_reason": dominant_stop,
        "best_pairing": {
            "architect": best["architect_model"],
            "auditor": best["auditor_model"],
            "convergence_rate": best["convergence_rate"],
        },
        "notes": notes,
    }
```

---

## Wave 2 — Scenario and Prompt Improvements (After W1 Is Green and Re-Benchmarked)

---

### W2-A — Seed decision values into the `missing_constraint` scenario

**Status:** ✅  
**Effort:** 20 minutes  
**File:** `tests/kernel/v1/vectors/odr/refinement/missing_constraint/seed.json`  
**File:** `scripts/odr/run_odr_7b_baseline.py` (scenario loading)

**Problem:** The `missing_constraint` seed has `"retention_days": null`. The
scenario is explicitly designed to test whether the model flags a missing
retention constraint. The model correctly marks it as `DECISION_REQUIRED`. But
in the baseline script, the decision is never provided, so the model loops
forever on an explicitly unanswerable question.

There are two valid approaches. Choose one:

**Option A — Provide the decision in the task prompt (recommended for live runs):**

In `_build_odr_task` in `cards_odr_stage.py` and in the baseline script's
scenario task builder, include any resolved seed decisions in the task text:

```python
def _build_odr_task(*, issue: Any, cards_runtime: Dict[str, Any]) -> str:
    ...
    seed_decisions = dict(cards_runtime.get("seed_decisions") or {})
    resolved = {k: v for k, v in seed_decisions.items() if v is not None}
    if resolved:
        lines.append("Resolved decisions:")
        for key, value in resolved.items():
            lines.append(f"  {key}: {value}")
    ...
```

**Option B — Add a "closed" scenario with decisions seeded:**

Create a second scenario in `scenarios.json` with a seed file that provides the
retention value, so there is one scenario that tests detection of missing
constraints and one that tests convergence once decisions are provided:

```json
// tests/kernel/v1/vectors/odr/refinement/missing_constraint/seed_resolved.json
{
  "decisions": {
    "retention_days": 30
  }
}
```

Add to `scenarios.json`:
```json
{
  "id": "missing_constraint_resolved",
  "path": "missing_constraint",
  "seed_file": "seed_resolved.json",
  "forbidden_patterns": ["upload\\s+profile\\s+data\\s+to\\s+external"],
  "expected_unresolved": [2, 0, 0],
  "require_decision_required_for_missing_values": []
}
```

Option B is lower risk (doesn't change existing scenario, adds a new one) and
makes the distinction between "can the model detect a missing constraint" and
"can the model converge when decisions are provided" explicit and testable.

---

### W2-B — Harden the auditor prompt to resolve, not escalate

**Status:** ✅  
**Effort:** 30 minutes  
**File:** `orket/kernel/v1/odr/prompt_contract.py`

**Problem:** The current auditor prompt instructs the auditor to use
`[DECISION_REQUIRED]` when a required field is unresolved. This makes the
auditor an escalation mechanism, not a resolution mechanism. When both the
architect and auditor only escalate, the loop cannot resolve decisions — it can
only surface them.

The auditor should first try to propose a concrete value, and only fall back to
`[DECISION_REQUIRED]` when no reasonable default exists.

**Fix — update `build_auditor_messages`:**

```python
def build_auditor_messages(*, task: str, architect_output: str) -> list[dict[str, str]]:
    system = (
        "You are the Auditor role in a requirements refinement loop.\n"
        "Return exactly these four sections, once each, in this exact order:\n"
        "### CRITIQUE\n"
        "### PATCHES\n"
        "### EDGE_CASES\n"
        "### TEST_GAPS\n"
        "Rules:\n"
        "- No code fences.\n"
        "- No source code.\n"
        "- Be adversarial and specific.\n"
        "- Reject demotion of required behavior into ASSUMPTIONS or OPEN_QUESTIONS.\n"
        "- Reject unresolved mandatory alternatives and hallucinated constants.\n"
        "- Each PATCHES bullet must start with one class tag: [ADD], [REMOVE], [REWRITE], or [DECISION_REQUIRED].\n"
        "- When proposing a value for a DECISION_REQUIRED field, use [REWRITE] with the resolved value. "
        "  Only use [DECISION_REQUIRED] when no reasonable default exists and the information is not "
        "  available from the task context.\n"
        "- If the requirement already specifies a concrete value for a constraint, do not re-escalate it "
        "  as a decision.\n"
    )
    user = f"Original task:\n{task}\n\nArchitect output to audit:\n{architect_output}\n"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
```

The key addition is: "When proposing a value for a DECISION_REQUIRED field, use
`[REWRITE]` with the resolved value." This gives the auditor a resolution path
instead of only an escalation path.

---

### W2-C — Raise the `_matches_any` ratio threshold for short clauses (from Round 3 W2-B)

**Status:** ✅  
**Effort:** 15 minutes  
**File:** `orket/kernel/v1/odr/semantic_validity.py`

This was listed as W2-B in Round 3 and is still open. Now is the right time to
close it since we are already touching the semantic validity file.

```python
def _matches_any(candidate: str, others: Iterable[str]) -> bool:
    candidate_tokens = _tokens(candidate)
    if len(candidate_tokens) < 3:
        return False
    for other in others:
        other_tokens = _tokens(other)
        if len(other_tokens) < 3:
            continue
        overlap = len(candidate_tokens & other_tokens)
        if overlap >= max(3, min(len(candidate_tokens), len(other_tokens)) - 1):
            return True
        min_tokens = min(len(candidate_tokens), len(other_tokens))
        ratio_threshold = 0.85 if min_tokens <= 5 else 0.7
        if overlap / max(1, min_tokens) >= ratio_threshold:
            return True
    return False
```

---

## Verification Gate

After applying Wave 1:

```bash
python -m pytest -q \
    tests/kernel/v1/test_odr_semantic_validity.py \
    tests/kernel/v1/test_odr_core.py \
    tests/kernel/v1/test_odr_determinism_gate.py \
    tests/kernel/v1/test_odr_refinement_behavior.py
```

All must pass. Note that the determinism gate hashes may need to be regenerated
if W1-A or W1-B change the convergence behavior of the torture pack or near-miss
fixtures. Run:

```bash
python tools/repro_odr_gate.py \
    --fixture tests/kernel/v1/vectors/odr/odr_torture_pack.json \
    --seed 1729 --perm-index 0 --print-canon-hash

python tools/repro_odr_gate.py \
    --fixture tests/kernel/v1/vectors/odr/odr_near_miss.json \
    --seed 1729 --perm-index 0 --print-canon-hash
```

Update `EXPECTED_TORTURE_SHA256` and `EXPECTED_NEAR_MISS_SHA256` in
`test_odr_determinism_gate.py` if the values change.

Then re-run the benchmarks:

```bash
python scripts/odr/run_odr_7b_baseline.py \
    --architect-models qwen2.5-coder:7b \
    --auditor-models qwen2.5:7b \
    --rounds 5

python scripts/odr/run_odr_single_vs_coordinated.py \
    --architect-model qwen2.5-coder:7b \
    --auditor-model qwen2.5:7b \
    --rounds 5
```

**What to look for in the re-run:**

- `missing_constraint` and `overfitting` should no longer stop as `UNRESOLVED_DECISIONS` due to optional questions (W1-B fix)
- `missing_constraint` and `overfitting` should no longer report spurious `contradiction_hits` (W1-A fix)
- `contradiction` should still stop as `UNRESOLVED_DECISIONS` or `INVALID_CONVERGENCE` (genuine contradiction, unfixable without domain input)
- `missing_constraint` with null `retention_days` may still stop as `UNRESOLVED_DECISIONS` if the seed decision is not provided (that is the correct behavior — it is a legitimately missing value)

If `missing_constraint` still fails after W1-A and W1-B, the failure is genuine
and the right response is W2-A (seed the resolved decision value) rather than
more detector tuning.

---

## Completion Checklist

| # | Item | Wave | Status |
|---|---|---|---|
| W1-A | Narrow `_contradiction_hits` to semantic pairs only (remove modal pairs) | 1 | ✅ |
| W1-B | Remove `open_questions` from `pending_decisions`; add `open_question_count` to trace | 1 | ✅ |
| W1-C | Fix `run_odr_7b_baseline.py` interpretation to distinguish failure modes | 1 | ✅ |
| — | Regenerate determinism gate hashes if changed | 1 | ✅ |
| — | Re-run benchmarks and compare to prior results | 1 | ✅ |
| W2-A | Seed resolved decisions into `missing_constraint` scenario | 2 | ✅ |
| W2-B | Update auditor prompt to propose values before escalating to DECISION_REQUIRED | 2 | ✅ |
| W2-C | Tighten `_matches_any` ratio threshold for short clauses (Round 3 W2-B, still open) | 2 | ✅ |

---

## What to Expect After Wave 1

The benchmark will still show failures. The `contradiction` scenario is
legitimately contradictory and cannot converge without resolving the delete-vs-retain
tension — that requires a domain decision the model cannot make from the prompt alone.
The `missing_constraint` scenario with null `retention_days` is legitimately
unresolvable without a provided value.

What should improve: `missing_constraint` and `overfitting` should stop
generating false-positive invalidity from optional questions and modal-negation
pattern matching. If those two scenarios converge after W1, coordinated
performance should improve substantially — from 0/3 to at least 1/3 or 2/3,
which would meaningfully change the single-vs-coordinated comparison.

If after W1 you still see 0/3 convergence with different stop reasons
(e.g., `MAX_ROUNDS` instead of `UNRESOLVED_DECISIONS`), that means the models
are producing outputs that are clean but too different across rounds for the
Jaccard-based `diff_ratio` to call stable. In that case the next step is
adjusting `diff_floor_pct` upward (e.g., from 0.05 to 0.15) to require less
similarity before calling convergence.
