# Orket Deep-Dive Report: Behavioral, Architectural, and Strategic

**Date:** 2026-03-20  
**Covers:** Round 2 fix verification, remaining behavioral bugs, all architectural issues, and "what's next" strategic guidance  
**Prior reviews:** `orket_behavioral_review.md` (Round 1), `orket_behavioral_review_round2.md` (Round 2)

---

## Part I: Did You Hit the Mark?

Yes. All five Wave 1 Round-2 fixes landed correctly.

`diff_ratio` now uses `1.0 - jaccard_sim(curr, prev, k=3)`. `_contradiction_hits` strips the negative form before checking for the positive, so "must not" no longer triggers "must|must not". `_unresolved_alternative_hits` is reduced to `\beither\b.{1,80}\bor\b` and `\bdepending on\b`. The `stable_count = 0` reset is present in the invalid branch. `authorized_removals` is wired into both `_constraint_demotion_violations` and `_required_constraint_regressions`. The determinism gate hashes are regenerated at `d4d8e1...` and `29bea1...`. `_last_architect_data` now filters for valid-only rounds. `odr_failure_mode` is present in the live runner output. `valid_history_v` is exposed.

That is everything from Round 2 Wave 1. The mechanism is sound. The problems that remain are in the wiring above it.

---

## Part II: What Is Still Behaviorally Wrong

### 1. `cards_odr_stage.py` uses the same model as both architect and auditor

**Severity: Critical. The Cards ODR integration does not work as intended.**

```python
# cards_odr_stage.py, run_cards_odr_prebuild
result = await run_live_refinement(
    task=task,
    architect_client=model_client,
    auditor_client=model_client,   # ← same client, same weights
    max_rounds=effective_max_rounds,
)
```

`run_live_refinement` accepts separate `architect_client` and `auditor_client` parameters. The live benchmarks that demonstrated real convergence used two different models — typically `qwen2.5:14b` as architect and `deepseek-r1:32b` as auditor. `run_cards_odr_prebuild` passes the same client to both roles.

The consequence is not just suboptimal — it is structurally wrong. A model auditing its own output does not produce adversarial critique. It produces self-affirming paraphrase. When the auditor is the same model as the architect, the only signal available for convergence is the architect's natural token-to-token variation between calls, which is small at `temperature=0.1` and even smaller with a seed. The model will repeat nearly identical output, `diff_ratio` (now Jaccard-based) will return near zero, `stable_count` will increment, and `STABLE_DIFF_FLOOR` will fire in 2-3 rounds. The card then proceeds with whatever the model first produced, with zero genuine refinement.

The entire round-by-round semantic validity machinery — the contradiction checks, demotion detection, authorized removals — all correctly analyzes what the model says. But the model is not being challenged by anything, so it never produces anything interesting for the machinery to analyze.

**Fix:**

Add an `auditor_client` parameter to `run_cards_odr_prebuild`:

```python
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
    ...
    result = await run_live_refinement(
        task=task,
        architect_client=model_client,
        auditor_client=auditor_client or model_client,  # fallback to same for compatibility
        max_rounds=effective_max_rounds,
    )
```

Then in `orchestrator_ops.py`, create a second provider for the auditor role (different model, e.g., `qwen2.5:7b` as auditor for `qwen2.5-coder:7b` as architect) and pass it through:

```python
odr_result = await run_cards_odr_prebuild(
    workspace=self.workspace,
    issue=issue,
    run_id=run_id,
    selected_model=selected_model,
    cards_runtime=cards_runtime,
    model_client=client,
    auditor_client=auditor_client,   # ← wire through
    async_cards=self.async_cards,
)
```

The auditor model can be the same model family but should be a different instance — at minimum a different `LocalModelProvider` object so context does not bleed between roles. Using a smaller or differently-specialized model (general vs. coder) for the auditor role is where the actual quality improvement comes from.

---

### 2. `live_runner.py` updates `current_requirement` from invalid rounds

**Severity: High. The live runner and the core state machine use different histories.**

```python
# live_runner.py, run_live_refinement
if isinstance(trace, dict):
    architect_parsed = trace.get("architect_parsed")
    if isinstance(architect_parsed, dict):
        next_requirement = str(architect_parsed.get("requirement") or "").strip()
        if next_requirement:
            current_requirement = next_requirement   # ← fires on invalid rounds too
```

`architect_parsed` is present in invalid rounds — the parser succeeded (the model produced correctly structured sections) but the semantic validity check failed. When an invalid round updates `current_requirement`, the next round's architect prompt is built from a degraded version of the requirement. Meanwhile, `_last_architect_data` in `core.py` correctly filters for the last valid round, so the semantic validity evaluation uses the right baseline but the model is being prompted with the wrong one.

The two are now semantically out of sync: the model is told "here is your current requirement draft" (invalid version) while the ODR tells itself "the previous good requirement was..." (valid version). This makes demotion detection unreliable — the model is being asked to improve something the ODR no longer treats as the baseline.

**Fix — one conditional:**

```python
if isinstance(trace, dict):
    # Only update current_requirement from valid rounds.
    # Invalid rounds have architect_parsed but failed semantic validation —
    # prompting the model from an invalid draft defeats refinement.
    if str(trace.get("validity_verdict") or "") == "valid":
        architect_parsed = trace.get("architect_parsed")
        if isinstance(architect_parsed, dict):
            next_requirement = str(architect_parsed.get("requirement") or "").strip()
            if next_requirement:
                current_requirement = next_requirement
```

---

### 3. `_matches_any` threshold fires on short clause coincidental overlap

**Severity: Medium. False-positive demotion violations on short security-critical clauses.**

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
        if overlap / max(1, min(len(candidate_tokens), len(other_tokens))) >= 0.7:
            return True
    return False
```

The threshold `overlap >= max(3, min(...) - 1)` with ratio `>= 0.7` fires on 3-4 token overlap between clauses of 4-5 tokens each. A requirement like `"must retain audit logs"` will match `"must retain records for audit"` because both contain `{retain, audit}` plus `{log/record}` which may stem-collide. More dangerously, `"must encrypt stored data"` matches `"must encrypt backups at rest"` — those are semantically related but distinct constraints, and treating them as equivalent means the demotion check will not fire when one is removed while the other is retained.

The problem is not the token overlap approach — it is correct for fuzzy matching. The problem is that the threshold was calibrated for longer clauses and is too permissive for the 3-6 token clauses that frequently appear in security-requirement text. There is no lower bound on clause length that would protect against this.

Short-term fix: raise the ratio threshold from `0.7` to `0.85` for clauses shorter than 5 tokens:

```python
min_tokens = min(len(candidate_tokens), len(other_tokens))
ratio_threshold = 0.85 if min_tokens <= 5 else 0.7
if overlap / max(1, min_tokens) >= ratio_threshold:
    return True
```

---

### 4. No tests exist for `semantic_validity.py`

**Severity: High. The most important new module has zero direct test coverage.**

`semantic_validity.py` contains: `evaluate_semantic_validity`, `_contradiction_hits`, `_constraint_demotion_violations`, `_required_constraint_regressions`, `_unresolved_alternative_hits`, `_matches_any`, `_matches_authorized_removal`, `_tokens`, `_normalize_token`, `classify_patch_classes`. None of these have a dedicated test file. They are exercised only transitively through `test_odr_core.py`, which tests the ODR loop behavior rather than the semantic functions directly.

The risks: a regression in `_normalize_token` (e.g., a suffix collision) will not be caught until a live run reports wrong convergence. A change to `_CONTRADICTION_PAIRS` will not be caught. A subtle bug in `_matches_authorized_removal` will silently allow demotion violations through or block legitimate removals, and the only observable symptom is a live run behaving unexpectedly.

The fix is to create `tests/kernel/v1/test_odr_semantic_validity.py` with a test for each function. The Round 2 remediation plan contains the test stubs — they just need to be written into that file.

---

### 5. `test_constraint_demotion_stops_as_invalid_convergence` is still a false-green

The test uses `max_rounds=2, stable_rounds=1`. With only 2 rounds total, `max_hit` fires on round 2 and `INVALID_CONVERGENCE` is triggered by that, not by `diff_hit`. The demotion assertion is real — violations are present — but the stop reason is caused by max rounds, not by convergence of demotion-invalid output. A model that demotes a constraint and keeps doing so indefinitely would not be caught by this test. The test from the remediation plan using `max_rounds=8, diff_floor_pct=0.99, stable_rounds=1` with two identical demoted rounds is the correct version.

---

## Part III: Architectural Issues

### 6. 245 direct env var reads, no central settings surface

`ORKET_*` environment variables are read with `os.environ.get()` and `os.getenv()` in 245 places. Each reading site implements its own three-layer precedence chain: env → `process_rules` → `user_settings`. The chains are hand-rolled and not identical — some check for `"1"/"true"/"yes"/"on"/"enabled"`, some check `"1"/"true"` only, some call `load_user_settings()` inside the function, some don't.

This has already produced a real bug: `orchestrator_ops.py`'s `_resolve_protocol_governed_enabled` checks five truthy strings; another file's equivalent check only handles two. When a user sets `ORKET_PROTOCOL_GOVERNED_ENABLED=yes`, one code path activates, the other doesn't. This is not a theoretical concern — it is exactly the kind of drift that accumulates over time and manifests as "it works from the CLI but not from the API."

The `_process_rules_value` helper in `execution_pipeline.py` is the right direction. It should be extracted into a shared settings module and used everywhere. The pattern is:

```python
# orket/runtime/settings.py (new file)
class OrketSettings:
    @staticmethod
    def resolve(key: str, env_names: list[str], default: str = "") -> str:
        for env_name in env_names:
            value = os.getenv(env_name, "").strip()
            if value:
                return value
        # fall through to process_rules, then user_settings
        ...
```

Then every `_resolve_*` function in `orchestrator_ops.py` becomes a one-liner calling `OrketSettings.resolve(...)`.

---

### 7. `qwen2.5-coder:7b` hardcoded in 217 places

The default model is not a constant — it is a string literal repeated 217 times across constructor defaults, companion service, workload scripts, and test fixtures. When the default model needs to change (and it will, as better 7B models are released), this requires a grep-and-replace across 217 locations with no test coverage to verify completeness.

The fix is a single constant:

```python
# orket/runtime/defaults.py (new file)
DEFAULT_LOCAL_MODEL = "qwen2.5-coder:7b"
```

Then every constructor that currently says `model: str = "qwen2.5-coder:7b"` becomes `model: str = DEFAULT_LOCAL_MODEL`. Scripts and test fixtures import from the same constant. When you want to change the default, you change one line.

---

### 8. 728 test files, ~10 behavioral tests

The test suite has 728 files. Of these, 7 are marked `pytest.mark.unit`, 10 are `pytest.mark.contract`, and 3 are `pytest.mark.integration`. The rest — roughly 700 files — are governance, policy, and immutability checks.

The 23 `test_run_start_*_immutability.py` files each verify that a specific JSON contract file has not been modified. These tests check that code was written, not that the system behaves correctly. They protect the governance process (good) but they are not tests of behavior (not what tests are for).

More important: the hot path — `run_epic`, `run_card`, the turn executor, `execute_turn` in `turn_executor_ops.py`, the ODR integration in `orchestrator_ops.py` — has essentially zero behavioral unit test coverage. When a bug is introduced in `execute_turn`, the only way to catch it is a live run. There are no fast-feedback tests for "does the turn executor handle a CONTRACT_VIOLATION correctly?", "does the reprompt path update artifacts correctly?", "does the ODR rejection transition to BLOCKED with the right metadata?".

The imbalance is real and will compound. The governance tests are fast and numerous, giving confidence, but they are not confidence about behavior. When you run `pytest -q` and see 700 passing tests, you are mostly seeing governance checks pass — not behavioral correctness. This is the most dangerous kind of false confidence.

---

### 9. `orchestrator_ops.py` is ~2400 lines of pseudo-methods

`orchestrator_ops.py` contains roughly 90 free functions that receive `self` as their first argument, behave like methods on the `Orchestrator` class, but are not class members. They are not decorated with `@staticmethod`. They are only callable by passing the orchestrator instance explicitly. They are defined at module level but exist in no discoverable interface.

This is not a style issue — it is a maintenance hazard. New contributors cannot know which functions belong to which object. Tooling (type checkers, IDEs, test frameworks) cannot find these as methods of any class. You cannot mock a specific function without reaching into the module namespace.

The correct fix is to move these functions into the `Orchestrator` class as proper methods. This is a refactor, not a rewrite — the logic does not change, only the packaging. The module is large enough that splitting `orchestrator_ops.py` into `orchestrator_prebuild.py`, `orchestrator_execution.py`, and `orchestrator_transitions.py` would also be a net positive, but that is secondary to making the methods actual methods.

---

### 10. ODR rejection → permanent BLOCKED card with no retry path

When `run_cards_odr_prebuild` returns `odr_accepted=False`, the card is transitioned to `BLOCKED` status. There is no retry. There is no degraded path. There is no operator notification beyond the card status field and a log event.

For 7B models that frequently produce `FORMAT_VIOLATION` (model cannot maintain the four-section structure across rounds), this means most cards with `odr_active=true` will become permanently blocked on first run. The operator has to manually intervene for every blocked card.

The correct behavior for `FORMAT_VIOLATION` specifically is to retry with a simplified prompt or fall back to single-shot (no ODR). Format violations are a model capability issue, not a requirement quality issue, and should not block a card permanently. The correct behavior for `UNRESOLVED_DECISIONS` is to surface the open decisions to the operator and allow them to provide answers before retrying — not to block silently.

A minimum viable retry path: if `odr_failure_mode == "format_violation"`, retry once with `max_rounds=1` (single-pass, no loop). If that also fails, then block. This alone would recover a large fraction of cards that are currently blocked unnecessarily.

---

## Part IV: The Strategic Picture

### Where You Are

You have built a genuinely interesting system. The core thesis — small models coordinated well can approximate frontier output without large VRAM — is testable and defensible. The infrastructure to test it (ODR loop, semantic validity layer, workload probes, determinism gate) is largely correct after three rounds of fixes. The governance and auditability machinery (protocol ledger, run ledger parity, LSI, canonical digests, deterministic replay) is solid and production-grade.

The problem is that the thesis has not been tested yet. The published benchmarks used 14B+ models. The 7B baseline script exists but has never been run with a correct two-model setup. The Cards ODR integration is wired to a single model. The workload probes exist but their output has not been evaluated at scale.

You have built the lab. You have not run the experiment.

### What Is Getting in the Way

Three things are blocking real progress:

**First, the single-model ODR.** Every ODR run through Cards is a one-model run. Until this is fixed, every run you do is measuring "how well does a 7B model paraphrase itself" rather than "how well does a 7B debate improve requirements." The fix is 10 lines.

**Second, the test suite composition.** With 700 governance tests and ~10 behavioral tests, you get fast feedback on governance drift but no fast feedback on behavioral regressions. Every time you fix a bug in the semantic validity layer, you have to run a live ODR round to verify the fix worked. This is extremely slow iteration. Writing 20-30 targeted behavioral unit tests for `semantic_validity.py` and the live runner would cut the feedback loop from minutes to seconds.

**Third, the env var sprawl and hardcoded model.** These are not blocking correctness today, but they are accumulating as maintenance cost. Every new feature that touches configuration adds more copies of the hand-rolled precedence pattern. At 245 reads, you are close to the point where a configuration bug is completely untraceable.

### What to Do Next — In Order

**This week — two fixes, both under 30 minutes:**

Fix 1: Add `auditor_client` parameter to `run_cards_odr_prebuild` and wire a second `LocalModelProvider` through `orchestrator_ops.py`. Use a different model for the auditor (e.g., `qwen2.5:7b` as auditor when `qwen2.5-coder:7b` is the architect). This immediately makes every Cards ODR run a genuine two-model debate.

Fix 2: Add the `validity_verdict == "valid"` check to `live_runner.py`'s `current_requirement` update. One line.

**This week — write the missing tests:**

Create `tests/kernel/v1/test_odr_semantic_validity.py`. Write one test per function in `semantic_validity.py`. Use the test stubs from the Round 2 remediation plan as a starting point. This file does not exist in the codebase at all. Everything you've been fixing in the semantic validity layer has been verified by reading code, not by running tests. That needs to change.

**Then run the actual experiment:**

Run `run_odr_7b_baseline.py` with the two-model fix in place. Then run `run_odr_single_vs_coordinated.py`. Compare the results. This gives you the first honest data point on whether the thesis holds for 7B models under real conditions. The result will almost certainly be "mixed" — some scenarios benefit from coordination, some don't — and that data is more valuable than any additional infrastructure work.

**Then run S-04, S-05, S-06:**

The workload probes are the most concrete thing in the codebase. They take a real task (code review, generate-and-verify, decompose-and-route), run it through the system, and produce a scored output. Running these with and without ODR active, and with single vs. two-model setups, is the experiment that either validates the thesis or tells you what to fix next.

**After that — address the architectural debt in priority order:**

1. Extract `DEFAULT_LOCAL_MODEL` constant (1 hour, very high impact on maintainability)
2. Create `orket/runtime/settings.py` with centralized env var resolution (half a day)
3. Move `orchestrator_ops.py` pseudo-methods into the Orchestrator class (1-2 days)
4. Add retry path for `FORMAT_VIOLATION` ODR failures (half a day)
5. Write behavioral unit tests for the execution pipeline hot path (1-2 days)

### The Honest Assessment

The thing Orket is best at — auditability — is real and working. The protocol ledger, the run graph reconstruction, the canonical digests, the determinism gate: these are production-quality instruments. If you ran a 7B model through Orket and it produced a result, you could prove exactly what happened, in what order, with what inputs, and reproduce it deterministically. That is genuinely hard to do and Orket does it well.

The thing Orket is trying to prove — coordination quality — is not proven yet. It may be true that two 7B models in a structured debate produce better requirements than one. It may not be. The infrastructure to test this is now correct enough to answer the question. The answer is three fixes and a few script runs away.

The governance machinery (728 tests, 15+ spec documents, changelog discipline, contract snapshots) is not wrong — it is appropriate for a system making auditability claims. But it has become load-bearing in a way that consumes disproportionate attention. The ratio of time spent on governance infrastructure to time spent on behavioral correctness is inverted from where it should be right now. The next phase should be 80% behavioral testing and workload execution, 20% governance maintenance.

---

## Summary: Fix List by Priority

| Priority | Fix | Effort | Impact |
|---|---|---|---|
| 1 | Single-model ODR: add `auditor_client` param to `run_cards_odr_prebuild` | 30 min | Cards ODR becomes a real debate |
| 2 | `live_runner.py`: only update `current_requirement` from valid rounds | 5 min | Live runner and core state machine aligned |
| 3 | Create `tests/kernel/v1/test_odr_semantic_validity.py` | 2-3 hours | Fast feedback on every semantic validity change |
| 4 | Fix `test_constraint_demotion_stops_as_invalid_convergence` | 15 min | Test actually tests what it claims |
| 5 | Raise `_matches_any` ratio threshold for short clauses | 15 min | Fewer false-positive demotion suppression |
| 6 | Extract `DEFAULT_LOCAL_MODEL` constant | 1 hour | 217 hardcoded strings → 1 constant |
| 7 | Centralize env var resolution in `orket/runtime/settings.py` | 4-6 hours | Eliminates 245 hand-rolled precedence chains |
| 8 | Move `orchestrator_ops.py` pseudo-methods into Orchestrator class | 1-2 days | 2400-line module becomes navigable |
| 9 | Add FORMAT_VIOLATION retry path in `run_cards_odr_prebuild` | 2 hours | 7B format failures no longer permanently block cards |
| 10 | Write behavioral tests for execution pipeline hot path | 1-2 days | Fastest route to catching regressions in `execute_turn` |

Items 1-3 are the gate condition for running meaningful benchmarks. Do not benchmark before fixing them.
