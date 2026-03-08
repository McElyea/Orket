# Orket Behavioral Truth Review
## Current-state verification against the uploaded repo dump

**Basis:** uploaded `project_dump.txt` plus the archived 2026-03-06 behavioral-truth review as a verification target, not as an authority.  
**Method:** static behavioral code review only. I did not execute the repo, talk to live services, or validate runtime behavior beyond what the checked-in code and tests prove.  
**Question answered:** How much of the last review is actually left, and where does the current snapshot still lie about behavior?

## Executive summary

The previous review is no longer an accurate description of the repo as a whole. The major driver prompt/action parity issues, startup semantics gaps, board-load integrity gaps, provider telemetry naming drift, and stale local version fallback are now either fixed or materially improved.

What remains is not repo-wide chaos. It is a narrower set of behavioral seams where the code still says more than it really does, or where tests/workflows still prove a weaker thing than their names suggest.

The highest-value remaining fixes are:
1. remove message-as-action from `adopt_issue`,
2. stop pretending `clear_context` clears LM Studio/OpenAI-compatible sessions when explicit session ids are in play,
3. tighten or retire compatibility JSON slicing, and
4. replace fixture-to-itself determinism gates with proof over real run artifacts.

## Status of the last review

This section answers the follow-up directly: how much is actually left from the last review.

## What is still left to do

Ranked by severity and by how directly each issue can mislead you about actual runtime behavior or proof strength.

### 1. `adopt_issue` is still message-as-action `[High]`

**Where:** `orket/driver_support_resources.py` lines 85-88; `tests/application/test_driver_action_parity.py` lines 23-48

**What it appears to claim:** The action registry and tests treat `adopt_issue` as a real supported structural action.

**What it actually does:** The runtime branch only formats and returns a sentence: it does not load an issue, mutate an epic, persist a move, invoke the reconciler, or record any transaction.

**Why this matters:** This is still one of the clearest behavioral lies left. A supported structural action exists in the advertised action surface, but the concrete implementation is narration only.

**Fix direction:** Either implement the actual move with persistence and auditable logging, or downgrade the action to an explicit suggestion response. Do not keep it in the structural-action set while it is just text.

**Evidence notes:**
- The branch is literally: `if action == 'adopt_issue': ... return 'Structural Reconciler: Moving issue ...'.`
- The action parity test only checks that advertised actions do not fall into unsupported-action handling. It does not assert any persisted move happened.

### 2. `clear_context` does not clear the context that the runtime now explicitly creates `[High]`

**Where:** `orket/adapters/llm/local_model_provider.py` lines 293-295 and 391-393; `orket/application/workflows/orchestrator_ops.py` line 1529

**What it appears to claim:** The orchestrator awaits `provider.clear_context()` after each turn, which strongly implies a real per-turn context reset.

**What it actually does:** For `openai_compat` calls, the provider attaches explicit session identifiers in request headers, but `clear_context` is a no-op that just returns. The code comment says chat-completion calls are stateless unless explicit sessions are used — but this provider does use explicit session ids.

**Why this matters:** That is a wrong-layer abstraction. The orchestrator thinks it is resetting model session state; the provider is not doing it. If LM Studio or another backend honors those session ids, turn-to-turn carryover can survive a “clear” that never happened.

**Fix direction:** Either implement a real session-reset mechanism for providers that use explicit sessions, or rename/remove `clear_context` so the call site stops implying a reset that is not happening.

**Evidence notes:**
- Headers include `X-Orket-Session-Id` and `X-Client-Session`.
- `clear_context` contains only `pass`.
- The orchestrator still calls `await provider.clear_context()` in the success path.

### 3. Driver compatibility mode still accepts non-JSON output by slicing from the first brace to the last brace `[Medium]`

**Where:** `orket/driver.py` lines 236-261

**What it appears to claim:** The driver presents itself as a JSON-disciplined action router, and strict mode does enforce pure JSON envelopes.

**What it actually does:** The default compatibility path still finds the first `{` and the last `}` anywhere in the model output and hands that substring to `json.loads`.

**Why this matters:** This is softer than the previous snapshot because strict mode now exists, but it still means the default path can convert “chatty output with embedded JSON” into a passing plan. That is not the same behavioral contract as “model returned valid JSON only.”

**Fix direction:** Promote strict mode to the default for governed paths, or at minimum make compatibility mode visibly degraded in the user-facing response and telemetry so it is never mistaken for full protocol conformance.

**Evidence notes:**
- Compatibility mode logs itself, then does `start = text.find('{')`, `end = text.rfind('}')`, and `json.loads(text[start:end+1])`.

### 4. Startup reconciliation now reports status, but the CLI still discards that status and continues `[Medium]`

**Where:** `orket/discovery.py` lines 122-159; `orket/interfaces/cli.py` line 128

**What it appears to claim:** Startup now has better truth surfaces: reconciliation and onboarding are separated, and telemetry records success/failure/no-op.

**What it actually does:** `run_cli()` calls `perform_first_run_setup()` and ignores the returned dict entirely. A failed reconciliation only becomes a log event; CLI behavior does not branch on it.

**Why this matters:** This is no longer a swallowed failure in the old sense, but it is still a semantic downgrade. The code records startup truth without making startup truth consequential.

**Fix direction:** Decide whether reconciliation failure should block, warn loudly on stdout/stderr, or mark the session degraded. Right now the behavior is “telemetry knows; operator may not.”

**Evidence notes:**
- `perform_first_run_setup` returns `{'reconciliation': ..., 'onboarding': ...}`.
- `run_cli` calls `perform_first_run_setup()` and does not inspect the result.

### 5. Determinism CI still contains fixture-to-itself proof that can only go green `[Medium]`

**Where:** `.gitea/workflows/quality.yml` lines 359-373; `.gitea/workflows/nightly-benchmark.yml` lines 95-107

**What it appears to claim:** These workflow steps are named as determinism enforcement.

**What it actually does:** They synthesize a memory trace fixture, then compare the file to itself and the retrieval trace to itself. That only proves the comparator can say identical fixtures are identical.

**Why this matters:** This is classic false-green proof. It is not useless as a smoke test for the comparator, but it is not runtime determinism evidence and should not be presented or mentally counted as that.

**Fix direction:** Rename these steps as comparator smoke tests, or replace them with comparisons over two independently produced traces from the same real run recipe.

**Evidence notes:**
- Both left and right arguments point to the same `memory_trace_fixture.json`.
- Both `left-retrieval` and `right-retrieval` arguments point to the same `memory_retrieval_trace_fixture.json`.

### 6. The Ollama strict-json/tool-call path still silently drops format enforcement when client support is missing `[Medium]`

**Where:** `orket/adapters/llm/local_model_provider.py` lines 159-176 and 220-225

**What it appears to claim:** For `strict_json` and `tool_call` tasks, the provider requests `format='json'`.

**What it actually does:** If the client raises `TypeError` about the `format` keyword, the provider clears `request_format`, marks a telemetry flag, and continues with a plain request.

**Why this matters:** This is an explicit compatibility fallback, but it is still a meaningful semantic downgrade: a call that started in “strict json” mode can end up using no format enforcement at all while the outer flow still succeeds.

**Fix direction:** Escalate this to a hard failure in strict paths, or expose the downgrade at a higher layer so the caller cannot mistake the result for strict-format proof.

**Evidence notes:**
- `request_format` is set for `strict_json` / `tool_call` tasks.
- On `TypeError` mentioning `format`, `format_fallback_used` becomes `True`, `request_format` becomes `''`, and the request is retried.

### 7. Epic schema drift is still being masked instead of eliminated `[Medium]`

**Where:** `orket/driver_support_resources.py` lines 22-39 and 182-189; `orket/driver_support_cli.py` lines 291-300

**What it appears to claim:** The driver CLI and structural paths appear to operate on one epic-card model.

**What it actually does:** One path creates epics with `cards: []`, another path appends `issues`, and list/add-card code quietly chooses whichever key already exists.

**Why this matters:** This is semantic drift, not just style. Multiple write paths are encoding different shapes, and read paths are smoothing it over. That makes the repo look more internally coherent than it is.

**Fix direction:** Pick one authoritative epic child key and migrate all writers and readers to it. Do not keep dual-shape masking as the normal behavior.

**Evidence notes:**
- The epic template writes `cards: []`.
- `create_issue` appends to `issues`.
- `add-card` picks `cards` if present, else `issues`.

## Items from the old review that are no longer the main problem

- **Board hierarchy truthfulness improved materially.** The function now uses `load_failures`, `result_status='partial_success'`, and explicit alerts instead of silently returning a cleaner board than the assets justify.
- **Driver config loading is much more honest.** The code now tracks `config_load_failures`, `config_degraded`, and `prompting_mode`, and strict mode can turn missing governed assets into a hard failure.
- **The fallback prompt/executor parity problem is mostly gone.** The supported action surface is now derived from a canonical registry, and `assign_team` explicitly says it is suggestion-only.
- **The old startup-proof gap is no longer a repo-wide indictment.** Replay tests still bypass startup on purpose, but there is now a dedicated startup semantics test that proves reconciliation runs when startup is not bypassed.

## Recommended order of attack

1. Remove `adopt_issue` from the “real structural action” set unless you implement the move for real.
2. Fix `clear_context` versus explicit LM Studio/OpenAI-compatible sessioning. This is the highest-risk wrong-abstraction seam still left.
3. Decide whether compatibility JSON slicing is still acceptable. If not, flip strict mode on the governed path and make compatibility opt-in.
4. Reclassify the memory determinism workflow steps as smoke tests or replace them with evidence from independently produced traces.
5. Unify epic child schema around one key and stop papering over `cards`-versus-`issues` drift.
6. Treat Ollama format fallback as degraded or blocked, not just retried compatibility.

## Verification limits

This review is grounded in the uploaded repo dump, not a live run. I am judging behavior from code paths, tests, and workflow definitions.

Where I marked something fixed, that means the snapshot now contains code and usually tests that materially address the prior mismatch. It does not mean every production seam has been live-verified.

Where I marked something “mostly fixed,” the original lie is substantially reduced, but the runtime still has a compatibility or degradation path that can hide more truth than ideal.
