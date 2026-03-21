# Orket Remediation Plan — Round 3

**Date:** 2026-03-20  
**Status:** Completed 2026-03-20  
**Source:** `orket_deep_dive_report.md`  
**Prior plans:** Round 1 (all closed), Round 2 (all Wave 1 closed)

All Round 2 Wave 1 fixes are confirmed applied. This plan covers what remains.

---

## Status Key

- ☐ Not started  
- ✅ Complete  
- ⚠️ Verified blocked / needs decision

---

## Wave 1 — Gate Condition for Benchmarking (Do These First)

These three items must be done before running `run_odr_7b_baseline.py` or
`run_odr_single_vs_coordinated.py`. Without them, benchmark results are not
meaningful.

---

### W1-A — Fix single-model ODR in `cards_odr_stage.py`

**Status:** ✅  
**Effort:** ~30 minutes  
**Files:** `orket/application/services/cards_odr_stage.py`, `orket/application/workflows/orchestrator_ops.py`

**Problem:** `run_cards_odr_prebuild` passes `model_client` as both architect and
auditor. A model debating itself does not produce adversarial critique and
converges trivially on whatever it first produced.

**Fix part 1 — `cards_odr_stage.py`:**

Add `auditor_client` parameter to `run_cards_odr_prebuild`. The parameter is
optional with `None` default so all existing call sites continue to work
unchanged — if `auditor_client` is `None`, the function falls back to using
`model_client` for both roles (same behavior as today, clearly documented).

```python
# BEFORE (line ~83 in run_cards_odr_prebuild):
async def run_cards_odr_prebuild(
    *,
    workspace: Path,
    issue: Any,
    run_id: str,
    selected_model: str,
    cards_runtime: Dict[str, Any],
    model_client: Any,
    async_cards: Any,
    max_rounds: int = 8,
) -> Dict[str, Any]:

# AFTER:
async def run_cards_odr_prebuild(
    *,
    workspace: Path,
    issue: Any,
    run_id: str,
    selected_model: str,
    cards_runtime: Dict[str, Any],
    model_client: Any,
    auditor_client: Any | None = None,   # ← add this
    async_cards: Any,
    max_rounds: int = 8,
) -> Dict[str, Any]:
```

Then update the `run_live_refinement` call inside that same function:

```python
# BEFORE:
result = await run_live_refinement(
    task=task,
    architect_client=model_client,
    auditor_client=model_client,
    max_rounds=effective_max_rounds,
)

# AFTER:
result = await run_live_refinement(
    task=task,
    architect_client=model_client,
    auditor_client=auditor_client if auditor_client is not None else model_client,
    max_rounds=effective_max_rounds,
)
```

Also update the `artifact_payload` dict to record which auditor model was used,
so runs are traceable:

```python
# Inside artifact_payload dict construction, add:
"auditor_model": str(
    getattr(auditor_client, "model", selected_model) if auditor_client is not None
    else selected_model
),
```

**Fix part 2 — `orchestrator_ops.py`:**

Find the `run_cards_odr_prebuild` call site (the block starting with
`if bool(cards_runtime.get("odr_active")) and not is_review_turn:`).

Add an auditor provider. The simplest correct approach is to create a second
`LocalModelProvider` using a different model for the auditor. The auditor model
should be configurable; use `selected_model` as the fallback so the change is
backward-compatible when no auditor model is configured.

```python
# Add this import near the top of orchestrator_ops.py if not already present:
from orket.adapters.llm.local_model_provider import LocalModelProvider

# Then, just before the run_cards_odr_prebuild call:
if bool(cards_runtime.get("odr_active")) and not is_review_turn:
    # Resolve auditor model — prefer a separate model for genuine debate.
    # Falls back to the same model if no auditor model is configured.
    odr_auditor_model = str(
        (cards_runtime.get("odr_auditor_model") or "").strip()
        or os.environ.get("ORKET_ODR_AUDITOR_MODEL", "").strip()
        or selected_model
    )
    odr_auditor_provider = self.model_client_node.create_provider(odr_auditor_model, env)
    odr_auditor_client = self.model_client_node.create_client(odr_auditor_provider)
    try:
        odr_result = await run_cards_odr_prebuild(
            workspace=self.workspace,
            issue=issue,
            run_id=run_id,
            selected_model=selected_model,
            cards_runtime=cards_runtime,
            model_client=client,
            auditor_client=odr_auditor_client,   # ← wire through
            async_cards=self.async_cards,
        )
    except (RuntimeError, ValueError, TypeError, OSError, AttributeError):
        await _close_provider_transport(provider)
        await _close_provider_transport(odr_auditor_provider)
        raise
    finally:
        await _close_provider_transport(odr_auditor_provider)
    ...
```

**Configuration:** To use a different auditor model, set either:
- `ORKET_ODR_AUDITOR_MODEL=qwen2.5:7b` environment variable, or  
- `odr_auditor_model: "qwen2.5:7b"` in the `cards_runtime` dict of the issue params.

If neither is set, both roles use `selected_model` — identical to current behavior.

**Verify:** Run the existing ODR integration test. The signature of
`run_cards_odr_prebuild` now has `auditor_client=None` as default, so no other
call sites break. The monkeypatch in the test at line ~292387 patches the
function at the module level; the new parameter passes through transparently.

---

### W1-B — Fix `live_runner.py`: only update `current_requirement` from valid rounds

**Status:** ✅  
**Effort:** 5 minutes  
**File:** `orket/kernel/v1/odr/live_runner.py`

**Problem:** `current_requirement` updates on every round where `architect_parsed`
is non-None — including semantically invalid rounds. The model is being prompted
from a degraded draft while the ODR baseline tracks the last valid version,
putting them out of sync.

**Fix — one conditional:**

```python
# BEFORE (inside the for loop, after run_round):
        if isinstance(trace, dict):
            architect_parsed = trace.get("architect_parsed")
            if isinstance(architect_parsed, dict):
                next_requirement = str(architect_parsed.get("requirement") or "").strip()
                if next_requirement:
                    current_requirement = next_requirement

# AFTER:
        if isinstance(trace, dict):
            # Only update current_requirement from semantically valid rounds.
            # On invalid rounds, architect_parsed is present but the requirement
            # failed semantic validation — prompting from an invalid draft defeats
            # refinement and diverges from the ODR state machine's own baseline.
            if str(trace.get("validity_verdict") or "") == "valid":
                architect_parsed = trace.get("architect_parsed")
                if isinstance(architect_parsed, dict):
                    next_requirement = str(architect_parsed.get("requirement") or "").strip()
                    if next_requirement:
                        current_requirement = next_requirement
```

No test changes needed — the existing `test_odr_core.py` tests exercise this
path transitively. After applying the fix, run:

```bash
python -m pytest tests/kernel/v1/test_odr_core.py -q
```

---

### W1-C — Create `tests/kernel/v1/test_odr_semantic_validity.py`

**Status:** ✅  
**Effort:** 2-3 hours  
**File:** `tests/kernel/v1/test_odr_semantic_validity.py` (new file, does not exist)

**Problem:** `semantic_validity.py` has zero dedicated tests. Every function in
it — `_contradiction_hits`, `_unresolved_alternative_hits`,
`_constraint_demotion_violations`, `_required_constraint_regressions`,
`_matches_any`, `_matches_authorized_removal`, `_tokens`, `classify_patch_classes`,
`evaluate_semantic_validity` — is exercised only transitively. Regressions are
caught only by live runs.

**Fix — create the file with the following tests:**

```python
# tests/kernel/v1/test_odr_semantic_validity.py
from __future__ import annotations

import pytest

from orket.kernel.v1.odr.semantic_validity import (
    _contradiction_hits,
    _matches_any,
    _matches_authorized_removal,
    _tokens,
    _unresolved_alternative_hits,
    classify_patch_classes,
    evaluate_semantic_validity,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _contradiction_hits
# ---------------------------------------------------------------------------


def test_contradiction_hits_must_not_alone_does_not_fire() -> None:
    """'must not' contains 'must' as a substring — must not trigger by itself."""
    text = "The system must not store data outside the jurisdiction."
    assert _contradiction_hits(text) == []


def test_contradiction_hits_disallow_alone_does_not_fire() -> None:
    """'disallow' contains 'allow' as a substring — must not trigger by itself."""
    text = "The system must disallow outbound connections."
    assert _contradiction_hits(text) == []


def test_contradiction_hits_genuine_retain_delete_fires() -> None:
    text = "The system must retain user data. The system must delete user data after 30 days."
    hits = _contradiction_hits(text)
    assert "retain|delete" in hits


def test_contradiction_hits_genuine_must_must_not_fires() -> None:
    text = "The system must store all logs. The system must not store PII logs."
    hits = _contradiction_hits(text)
    assert "must|must not" in hits


def test_contradiction_hits_empty_text_returns_empty() -> None:
    assert _contradiction_hits("") == []


# ---------------------------------------------------------------------------
# _unresolved_alternative_hits
# ---------------------------------------------------------------------------


def test_unresolved_or_in_constraint_does_not_fire() -> None:
    """'or' as a binary constraint option is not an open decision."""
    assert _unresolved_alternative_hits(
        "The system must encrypt or hash all stored passwords."
    ) == []


def test_unresolved_may_does_not_fire() -> None:
    """RFC 2119 'may' is permitted behavior, not an open decision."""
    assert _unresolved_alternative_hits(
        "The cache layer may store results for up to 10 seconds."
    ) == []


def test_unresolved_either_or_fires() -> None:
    """'either X or Y' is a genuine open decision."""
    hits = _unresolved_alternative_hits(
        "The system must use either AES-128 or AES-256 for encryption."
    )
    assert len(hits) >= 1


def test_unresolved_depending_on_fires() -> None:
    """'depending on' is a genuine conditional ambiguity."""
    hits = _unresolved_alternative_hits(
        "Retention must be 30 or 90 days depending on account tier."
    )
    assert len(hits) >= 1


def test_unresolved_decision_required_clause_is_suppressed() -> None:
    """A clause already marked DECISION_REQUIRED should not also fire as unresolved."""
    hits = _unresolved_alternative_hits(
        "DECISION_REQUIRED(encryption_algo): either AES-128 or AES-256."
    )
    assert hits == []


def test_unresolved_empty_text_returns_empty() -> None:
    assert _unresolved_alternative_hits("") == []


# ---------------------------------------------------------------------------
# _matches_any
# ---------------------------------------------------------------------------


def test_matches_any_identical_clause_matches() -> None:
    assert _matches_any("must encrypt all backups at rest", ["must encrypt all backups at rest"])


def test_matches_any_near_duplicate_matches() -> None:
    assert _matches_any(
        "must encrypt all backups at rest",
        ["must encrypt all stored backups at rest using AES-256"],
    )


def test_matches_any_unrelated_clause_does_not_match() -> None:
    assert not _matches_any(
        "must encrypt all backups at rest",
        ["must support multi-factor authentication for all users"],
    )


def test_matches_any_short_candidate_returns_false() -> None:
    """Clauses with fewer than 3 meaningful tokens never match."""
    assert not _matches_any("encrypt", ["must encrypt all backups"])


def test_matches_any_empty_others_returns_false() -> None:
    assert not _matches_any("must encrypt all backups at rest", [])


# ---------------------------------------------------------------------------
# _matches_authorized_removal
# ---------------------------------------------------------------------------


def test_matches_authorized_removal_matching_text_suppresses() -> None:
    from orket.kernel.v1.odr.semantic_validity import _matches_authorized_removal

    clause = "must encrypt all backups at rest"
    removal = "[REMOVE] The encryption at rest requirement is not applicable here."
    assert _matches_authorized_removal(clause, [removal])


def test_matches_authorized_removal_unrelated_removal_does_not_suppress() -> None:
    from orket.kernel.v1.odr.semantic_validity import _matches_authorized_removal

    clause = "must encrypt all backups at rest"
    removal = "[REMOVE] The 30-day log retention clause is no longer required."
    assert not _matches_authorized_removal(clause, [removal])


def test_matches_authorized_removal_empty_list_returns_false() -> None:
    from orket.kernel.v1.odr.semantic_validity import _matches_authorized_removal

    assert not _matches_authorized_removal("must encrypt all backups at rest", [])


def test_matches_authorized_removal_none_returns_false() -> None:
    from orket.kernel.v1.odr.semantic_validity import _matches_authorized_removal

    assert not _matches_authorized_removal("must encrypt all backups at rest", None)


# ---------------------------------------------------------------------------
# _tokens
# ---------------------------------------------------------------------------


def test_tokens_strips_stopwords() -> None:
    tokens = _tokens("must store data in the system")
    assert "the" not in tokens
    assert "in" not in tokens
    assert "store" in tokens or "stor" in tokens  # allow stemming


def test_tokens_empty_text_returns_empty_set() -> None:
    assert _tokens("") == set()


def test_tokens_short_words_excluded() -> None:
    """Words of 2 characters or fewer are excluded."""
    tokens = _tokens("it is OK to do it")
    assert "it" not in tokens
    assert "is" not in tokens


# ---------------------------------------------------------------------------
# classify_patch_classes
# ---------------------------------------------------------------------------


def test_classify_patch_classes_tagged_add() -> None:
    rows = classify_patch_classes(["[ADD] Must include audit logging."])
    assert rows[0]["patch_class"] == "ADD"


def test_classify_patch_classes_tagged_remove() -> None:
    rows = classify_patch_classes(["[REMOVE] The encryption clause is not needed."])
    assert rows[0]["patch_class"] == "REMOVE"


def test_classify_patch_classes_tagged_rewrite() -> None:
    rows = classify_patch_classes(["[REWRITE] Clarify the retention period."])
    assert rows[0]["patch_class"] == "REWRITE"


def test_classify_patch_classes_tagged_decision_required() -> None:
    rows = classify_patch_classes(["[DECISION_REQUIRED] Choose between AES-128 and AES-256."])
    assert rows[0]["patch_class"] == "DECISION_REQUIRED"


def test_classify_patch_classes_untagged_remove_inferred() -> None:
    rows = classify_patch_classes(["Drop the redundant encryption clause entirely."])
    assert rows[0]["patch_class"] == "REMOVE"


def test_classify_patch_classes_empty_list() -> None:
    assert classify_patch_classes([]) == []


def test_classify_patch_classes_empty_string_skipped() -> None:
    rows = classify_patch_classes(["", "  ", "[ADD] real patch"])
    assert len(rows) == 1
    assert rows[0]["patch_class"] == "ADD"


# ---------------------------------------------------------------------------
# evaluate_semantic_validity — integration-level
# ---------------------------------------------------------------------------


def _make_architect(requirement: str, assumptions: list[str] | None = None,
                    open_questions: list[str] | None = None) -> dict:
    return {
        "requirement": requirement,
        "changelog": ["changed"],
        "assumptions": assumptions or [],
        "open_questions": open_questions or [],
    }


def _make_auditor(patches: list[str] | None = None) -> dict:
    return {
        "critique": ["c1"],
        "patches": patches or ["[ADD] p1"],
        "edge_cases": ["e1"],
        "test_gaps": ["t1"],
    }


def test_evaluate_valid_clean_requirement() -> None:
    result = evaluate_semantic_validity(
        architect_data=_make_architect(
            "The system must encrypt all stored credentials at rest using AES-256."
        ),
        auditor_data=_make_auditor(),
        previous_architect_data=None,
    )
    assert result["validity_verdict"] == "valid"
    assert result["semantic_failures"] == []


def test_evaluate_invalid_when_decision_required_present() -> None:
    result = evaluate_semantic_validity(
        architect_data=_make_architect(
            "DECISION_REQUIRED(encryption_algo): algorithm not yet chosen."
        ),
        auditor_data=_make_auditor(),
        previous_architect_data=None,
    )
    assert result["validity_verdict"] == "invalid"
    assert "pending_decisions" in result["semantic_failures"]
    assert result["pending_decision_count"] >= 1


def test_evaluate_invalid_when_open_question_present() -> None:
    result = evaluate_semantic_validity(
        architect_data=_make_architect(
            "The system must store backups securely.",
            open_questions=["What encryption algorithm should be used?"],
        ),
        auditor_data=_make_auditor(),
        previous_architect_data=None,
    )
    assert result["validity_verdict"] == "invalid"
    assert "pending_decisions" in result["semantic_failures"]


def test_evaluate_remove_patch_suppresses_demotion() -> None:
    """[REMOVE] patch must prevent a demotion violation from firing."""
    result = evaluate_semantic_validity(
        architect_data=_make_architect("The system handles backups."),
        auditor_data=_make_auditor(
            patches=["[REMOVE] The encryption at rest clause is not applicable here."]
        ),
        previous_architect_data=_make_architect(
            "The system must encrypt all backups at rest."
        ),
    )
    assert result["constraint_demotion_violations"] == []
    assert result["validity_verdict"] == "valid"


def test_evaluate_demotion_fires_without_remove_patch() -> None:
    """Without a [REMOVE] patch, removing a required clause is a demotion violation."""
    result = evaluate_semantic_validity(
        architect_data=_make_architect("The system handles backups."),
        auditor_data=_make_auditor(patches=["[ADD] add more constraints"]),
        previous_architect_data=_make_architect(
            "The system must encrypt all backups at rest.",
            assumptions=["All backups remain encrypted."],
        ),
    )
    # The prior required clause was moved to assumptions — that is a demotion.
    assert len(result["constraint_demotion_violations"]) >= 1
    assert result["validity_verdict"] == "invalid"


def test_evaluate_no_previous_data_never_fires_demotion() -> None:
    """On round 1 (no previous data), demotion detection must not fire."""
    result = evaluate_semantic_validity(
        architect_data=_make_architect("The system must encrypt all backups."),
        auditor_data=_make_auditor(),
        previous_architect_data=None,
    )
    assert result["constraint_demotion_violations"] == []
```

**Run after creating:**

```bash
python -m pytest tests/kernel/v1/test_odr_semantic_validity.py -v
```

All tests should pass. If any fail, that indicates a remaining behavioral issue
in `semantic_validity.py` that needs investigation before benchmarking.

---

## Wave 2 — Quality and Correctness (After Wave 1 Is Green)

---

### W2-A — Fix `test_constraint_demotion_stops_as_invalid_convergence`

**Status:** ✅  
**Effort:** 15 minutes  
**File:** `tests/kernel/v1/test_odr_core.py`

**Problem:** The existing test uses `max_rounds=2`. With only 2 rounds, the stop
reason fires via `max_hit`, not `diff_hit`. The test asserts the right `stop_reason`
and `constraint_demotion_violations`, but the demotion did not *drive* the stop.

**Fix — replace the test body:**

```python
# BEFORE: test_constraint_demotion_stops_as_invalid_convergence
# (uses max_rounds=2, stops via max_hit, not diff_hit)

# AFTER:
def test_constraint_demotion_stops_as_invalid_convergence_via_diff_floor() -> None:
    """
    INVALID_CONVERGENCE must be driven by stable invalid rounds (diff_hit),
    not by exhausting max_rounds (max_hit). Use max_rounds=8 so max_hit
    cannot be the cause at round 3.
    """
    cfg = ReactorConfig(max_rounds=8, diff_floor_pct=0.99, stable_rounds=1)
    state = ReactorState()

    # Round 1: valid baseline with a required constraint
    state = run_round(
        state,
        _architect("The system must encrypt all backups at rest."),
        _auditor(),
        cfg,
    )
    assert state.stop_reason is None

    # Round 2: demotion — required clause moved to ASSUMPTIONS
    demoted = (
        "### REQUIREMENT\n"
        "The system handles backups.\n\n"
        "### CHANGELOG\n"
        "- changed\n\n"
        "### ASSUMPTIONS\n"
        "- All backups remain encrypted at rest.\n\n"
        "### OPEN_QUESTIONS\n"
        "- none\n"
    )
    state = run_round(state, demoted, _auditor(), cfg)
    assert state.stop_reason is None

    # Round 3: same demotion repeated — triggers invalid diff_hit
    state = run_round(state, demoted, _auditor(), cfg)

    assert state.stop_reason == "INVALID_CONVERGENCE", (
        f"Expected INVALID_CONVERGENCE via diff_hit, got {state.stop_reason}. "
        "If MAX_ROUNDS fired, the test config is wrong."
    )
    record = state.history_rounds[-1]
    assert record["validity_verdict"] == "invalid"
    assert record["constraint_demotion_violations"], "demotion violations must be present"
    # n=3, max_rounds=8: confirm this was diff_hit, not max_hit
    assert record["metrics"]["n"] < cfg.max_rounds
```

---

### W2-B — Tighten `_matches_any` ratio threshold for short clauses

**Status:** ✅  
**Effort:** 15 minutes  
**File:** `orket/kernel/v1/odr/semantic_validity.py`

**Problem:** With short clauses (3-5 tokens after stopword removal), the 0.7
Jaccard ratio threshold fires on near-coincidental overlap. Security-critical
short clauses like "must encrypt stored data" match "must encrypt backups at rest"
which are related but distinct constraints.

**Fix:**

```python
# BEFORE:
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
        if overlap / max(1, min(len(candidate_tokens), len(other_tokens))) >= 0.7:
            return True
    return False

# AFTER:
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
        # Use a stricter ratio for short clauses to avoid coincidental overlap
        # between distinct security constraints that share common tokens.
        min_tokens = min(len(candidate_tokens), len(other_tokens))
        ratio_threshold = 0.85 if min_tokens <= 5 else 0.7
        if overlap / max(1, min_tokens) >= ratio_threshold:
            return True
    return False
```

Add a test to `test_odr_semantic_validity.py` (created in W1-C):

```python
def test_matches_any_short_distinct_security_clauses_do_not_collide() -> None:
    """Two distinct short security constraints must not be treated as equivalent."""
    assert not _matches_any(
        "must encrypt stored data",
        ["must encrypt backups at rest"],
    )
```

---

## Wave 3 — Architectural Debt (Scheduled, Not Blocking)

These items do not affect behavioral correctness today but will compound as
maintenance cost if deferred indefinitely. Do them in order after Wave 2.

---

### W3-A — Extract `DEFAULT_LOCAL_MODEL` constant

**Status:** ✅  
**Effort:** 1 hour  
**Files:** New `orket/runtime/defaults.py`, then grep-and-replace

**Problem:** `"qwen2.5-coder:7b"` appears hardcoded in 217 locations across
constructor defaults, companion service, workload scripts, and test fixtures.

**Fix:**

Create `orket/runtime/defaults.py`:

```python
# orket/runtime/defaults.py
"""
Single-source defaults for model and provider configuration.
All code that needs a default model name imports from here.
"""
from __future__ import annotations

# Default local model for all Orket components.
# To change the system default, change this one value.
DEFAULT_LOCAL_MODEL: str = "qwen2.5-coder:7b"
```

Then replace all occurrences:

```bash
# Find all files with the hardcoded string
grep -rn '"qwen2.5-coder:7b"' orket/ scripts/ tests/ --include="*.py" > /tmp/model_occurrences.txt

# Verify count before replacing
wc -l /tmp/model_occurrences.txt
```

For each file, replace `"qwen2.5-coder:7b"` with `DEFAULT_LOCAL_MODEL` and add
the import `from orket.runtime.defaults import DEFAULT_LOCAL_MODEL` at the top.

Priority files (do these first, they are in the hot path):
- `orket/adapters/llm/local_model_provider.py`
- `orket/application/services/companion_runtime_service.py`
- `orket/application/services/companion_runtime_helpers.py`
- `scripts/workloads/code_review_probe.py`
- `scripts/workloads/generate_and_verify.py`
- `scripts/workloads/decompose_and_route.py`
- `scripts/odr/run_odr_7b_baseline.py`
- `scripts/odr/run_odr_single_vs_coordinated.py`

Test fixtures can use the string literal directly — they pin specific model
names for reproducibility and should not import from defaults.

**Verify:**

```bash
python -m pytest -q  # full suite, ensure no import errors
grep -rn '"qwen2.5-coder:7b"' orket/ scripts/ --include="*.py" | grep -v "test_\|tests/"
# Should return only test files, which are exempt
```

---

### W3-B — Add FORMAT_VIOLATION retry path in `cards_odr_stage.py`

**Status:** ✅  
**Effort:** 2 hours  
**File:** `orket/application/services/cards_odr_stage.py`

**Problem:** Any ODR failure — including a `FORMAT_VIOLATION` caused by a 7B
model failing to maintain the four-section structure — permanently blocks the
card. Format violations are a model capability issue, not a requirement quality
issue, and should not cause permanent card failure.

**Fix:**

Add a single-pass retry when `odr_failure_mode == "format_violation"`:

```python
# In run_cards_odr_prebuild, after the first run_live_refinement call:

odr_failure_mode = str(result.get("odr_failure_mode") or "")

# If the failure was a format violation (model couldn't maintain structure),
# retry once with max_rounds=1 (single pass, no loop).
# Format violations are a model capability issue, not a requirement issue.
if odr_failure_mode == "format_violation" and effective_max_rounds > 1:
    log_event(
        "odr_prebuild_format_violation_retry",
        {
            "session_id": str(run_id),
            "issue_id": str(getattr(issue, "id", "")),
            "original_stop_reason": str(result.get("odr_stop_reason") or ""),
        },
        workspace,
    )
    retry_result = await run_live_refinement(
        task=task,
        architect_client=model_client,
        auditor_client=auditor_client if auditor_client is not None else model_client,
        max_rounds=1,  # single pass only on retry
    )
    # Use the retry result if it did not also format-violate
    if str(retry_result.get("odr_failure_mode") or "") != "format_violation":
        result = retry_result

stop_reason = str(result.get("odr_stop_reason") or "")
odr_valid = bool(result.get("odr_valid"))
pending_decisions = int(result.get("odr_pending_decisions") or 0)
```

---

### W3-C — Centralize env var resolution

**Status:** ✅  
**Effort:** 4-6 hours  
**Files:** New `orket/runtime/settings.py`, then incremental migration

**Problem:** 245 direct `os.environ.get()` / `os.getenv()` reads, each with a
hand-rolled three-layer precedence chain (env → process_rules → user_settings).
Chains are inconsistent — different code paths accept different truthy strings
for the same setting.

**Fix:**

Create `orket/runtime/settings.py` with a shared resolver:

```python
# orket/runtime/settings.py
from __future__ import annotations

import os
from typing import Any

from orket.settings import load_user_settings


def resolve_str(
    *env_names: str,
    process_rules: dict[str, Any] | None = None,
    process_key: str = "",
    user_key: str = "",
    default: str = "",
) -> str:
    """
    Resolve a string setting with standard Orket precedence:
      1. Environment variable (first matching env_name wins)
      2. process_rules dict (if process_rules and process_key provided)
      3. user_settings (if user_key provided)
      4. default
    """
    for name in env_names:
        value = str(os.getenv(name, "")).strip()
        if value:
            return value
    if process_rules and process_key:
        value = str(process_rules.get(process_key, "")).strip()
        if value:
            return value
    if user_key:
        value = str(load_user_settings().get(user_key, "")).strip()
        if value:
            return value
    return default


def resolve_bool(
    *env_names: str,
    process_rules: dict[str, Any] | None = None,
    process_key: str = "",
    user_key: str = "",
    default: bool = False,
) -> bool:
    """
    Resolve a boolean setting. Truthy strings: 1, true, yes, on, enabled.
    Falsy strings: 0, false, no, off, disabled.
    """
    _TRUTHY = {"1", "true", "yes", "on", "enabled"}
    _FALSY = {"0", "false", "no", "off", "disabled"}

    raw = resolve_str(*env_names, process_rules=process_rules,
                      process_key=process_key, user_key=user_key).lower()
    if raw in _TRUTHY:
        return True
    if raw in _FALSY:
        return False
    return default
```

Then, incrementally replace the hand-rolled patterns. Start with the highest-
impact files: `orchestrator_ops.py` has 15+ copies of the old pattern.

**Migration example:**

```python
# BEFORE (in orchestrator_ops.py):
def _resolve_architecture_mode(self) -> str:
    env_raw = (os.environ.get("ORKET_ARCHITECTURE_MODE") or "").strip()
    process_raw = ""
    if self.org and isinstance(getattr(self.org, "process_rules", None), dict):
        process_raw = str(self.org.process_rules.get("architecture_mode", "")).strip()
    user_raw = str(load_user_settings().get("architecture_mode", "")).strip()
    return resolve_architecture_mode(env_raw, process_raw, user_raw)

# AFTER:
from orket.runtime.settings import resolve_str

def _resolve_architecture_mode(self) -> str:
    process_rules = (
        self.org.process_rules
        if self.org and isinstance(getattr(self.org, "process_rules", None), dict)
        else None
    )
    raw = resolve_str(
        "ORKET_ARCHITECTURE_MODE",
        process_rules=process_rules,
        process_key="architecture_mode",
        user_key="architecture_mode",
    )
    return resolve_architecture_mode(raw, "", "")
```

Do not migrate all 245 reads at once. Migrate `orchestrator_ops.py` first
(highest value), then `execution_pipeline.py`, then others incrementally.

---

### W3-D — Move `orchestrator_ops.py` pseudo-methods into the Orchestrator class

**Status:** ✅  
**Effort:** 1-2 days  
**File:** `orket/application/workflows/orchestrator_ops.py`

**Problem:** ~90 free functions in `orchestrator_ops.py` receive `self` as their
first argument but are not class members. They are only discoverable by reading
the module; type checkers and IDEs cannot find them as methods of any class.

**Fix approach:** This is a mechanical refactor — the logic does not change.

1. Identify all free functions that take `self` as first argument. They follow the
   pattern `def _resolve_*(self)` or `def _build_*(self, ...)`.
2. Move them into the `Orchestrator` class in `orchestrator.py` as proper `def`
   methods (no decorator needed since they already accept `self`).
3. Remove them from `orchestrator_ops.py` one batch at a time, keeping the module
   runnable after each batch.
4. Update any explicit `self._func(self, ...)` call sites (there should be none —
   these are called like `_func(self, ...)` at module level).

Do this in three batches to keep diffs reviewable:
- Batch 1: `_resolve_*` functions (~15 functions, all config resolution)
- Batch 2: `_build_*` and `_compute_*` functions (~10 functions)
- Batch 3: Remaining free functions and cleanup

Run `python -m pytest -q` after each batch.

---

## Completion Checklist

| # | Item | Wave | Status |
|---|---|---|---|
| W1-A | `cards_odr_stage.py`: add `auditor_client` param; wire second provider in `orchestrator_ops.py` | 1 | ✅ |
| W1-B | `live_runner.py`: only update `current_requirement` from valid rounds | 1 | ✅ |
| W1-C | Create `tests/kernel/v1/test_odr_semantic_validity.py` | 1 | ✅ |
| W2-A | Replace `test_constraint_demotion_stops_as_invalid_convergence` with diff_hit version | 2 | ✅ |
| W2-B | Tighten `_matches_any` ratio threshold for short clauses | 2 | ✅ |
| W3-A | Extract `DEFAULT_LOCAL_MODEL` constant to `orket/runtime/defaults.py` | 3 | ✅ |
| W3-B | Add FORMAT_VIOLATION single-pass retry in `run_cards_odr_prebuild` | 3 | ✅ |
| W3-C | Centralize env var resolution in `orket/runtime/settings.py` | 3 | ✅ |
| W3-D | Move `orchestrator_ops.py` pseudo-methods into Orchestrator class | 3 | ✅ |

---

## Verification Gate After Wave 1

Run this before benchmarking:

```bash
python -m pytest -q \
    tests/kernel/v1/test_odr_core.py \
    tests/kernel/v1/test_odr_semantic_validity.py \
    tests/kernel/v1/test_odr_determinism_gate.py \
    tests/kernel/v1/test_odr_leak_policy_balanced.py \
    tests/kernel/v1/test_odr_refinement_behavior.py
```

All must pass. Then run the benchmarks:

```bash
# 7B baseline — establishes honest single-model baseline
python scripts/odr/run_odr_7b_baseline.py \
    --architect-models qwen2.5-coder:7b \
    --auditor-models qwen2.5:7b \
    --rounds 5

# Single vs coordinated — tests the core thesis
python scripts/odr/run_odr_single_vs_coordinated.py \
    --architect-model qwen2.5-coder:7b \
    --auditor-model qwen2.5:7b \
    --rounds 5
```

Set `ORKET_ODR_AUDITOR_MODEL=qwen2.5:7b` before running if you want the Cards
ODR path to also use a two-model setup during those runs.
