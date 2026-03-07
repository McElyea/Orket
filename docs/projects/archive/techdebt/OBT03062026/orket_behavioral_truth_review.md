# Orket Behavioral Truth Code Review
_Date:_ 2026-03-06  
_Basis:_ uploaded repository dump `project_dump_behavioral.txt`  
_Scope:_ behavioral truth review only. This document ignores broad style or architecture critique unless it directly creates incorrect behavior, false confidence, silent degradation, or proof gaps.

## Executive Summary

This repo has a recurring behavioral pattern:

1. **Narrated behavior instead of real behavior** — code returns success text or “switching” language without performing the underlying state transition.
2. **Silent degradation** — missing configs, malformed assets, and startup/setup failures often collapse into fallback behavior or omission without surfacing a hard signal.
3. **Advertised surface larger than implemented surface** — prompts/help text/abstractions imply capabilities that the actual control flow does not implement.
4. **Truth/proof mismatch** — some of the highest-risk paths are either untested, bypassed in tests, or still visibly mid-flight in the git status included in the dump.

This is not mostly a style problem. It is a **runtime semantics honesty** problem.

## Severity Legend

- **Critical** — behavior can directly mislead operator decisions or cause state/action mismatch in core workflows.
- **High** — strong claimed-vs-actual mismatch, silent fallback, or hidden no-op in important runtime paths.
- **Medium** — meaningful semantic drift, misleading telemetry, weak proof, or brittle parsing that can produce false confidence.
- **Low** — naming/doc/runtime drift that is real but not likely to cause immediate damage.

---

## Finding 1 — `get_engine_recommendations()` contains a complete no-op where the function claims to evaluate installed high-tier coverage
**Severity:** High  
**File / Function:** `orket/discovery.py:get_engine_recommendations()`  
**Evidence:** lines 50-85, especially 66-74

### What the code appears to claim
The docstring says the function cross-references hardware profile and installed models against the engine catalog to suggest what the user is missing for a “Best-in-Class” setup.

The loop structure also strongly implies:
- inspect installed models for a category,
- determine whether the user already has a high-tier engine,
- avoid suggesting an unnecessary upgrade if they do.

### What it actually does
It initializes `has_high_tier = False`, iterates installed models, and then does nothing:

```python
has_high_tier = False
for m in installed:
    if any(k in m.lower() for k in mapping.keywords):
        # If the installed model is in our catalog and is high tier, we're good
        # (This is a simplification, but works for local discovery)
        pass
```

The variable is never updated and never consulted later.

### Behavioral truth
This function is **not** checking whether the user already has a good model for the category. It is simply:
- walking the catalog,
- finding the best catalog candidate the hardware can handle,
- recommending it if it is not string-matched in installed models.

That is a different behavior than the comments, variable naming, and surrounding structure imply.

### Why this matters
This is a **hidden no-op in recommendation logic**. It can make the engine recommendation output look smarter and more grounded than it really is. You could believe Orket is comparing against “already-good-enough” installed capability when it is not.

### Fix direction
Either:
- implement real installed-tier evaluation, or
- delete the dead logic and rewrite the docstring/comments so the function truthfully says it only recommends the highest catalog match missing by keyword.

### Proof gap
I found no test references to `get_engine_recommendations()` in the uploaded dump.

---

## Finding 2 — `perform_first_run_setup()` is not first-run-only for its most important side effect
**Severity:** High  
**File / Function:** `orket/discovery.py:perform_first_run_setup()`  
**Evidence:** lines 106-116

### What the code appears to claim
The name says this is a first-run setup routine.

### What it actually does
Before checking whether setup is complete, it always runs structural reconciliation:

```python
# Run Structural Reconciliation on every startup to clean up orphans
try:
    from orket.domain.reconciler import StructuralReconciler
    reconciler = StructuralReconciler()
    reconciler.reconcile_all()
except ...
    log_event(...)
```

Only after that does it check:

```python
if load_user_settings().get("setup_complete"): return
```

### Behavioral truth
This function is not “first-run setup.” It is:
- **every-startup reconciliation**, plus
- **first-run banner/settings work**.

The function name materially understates the recurring mutation/cleanup side effect.

### Why this matters
If you treat this as benign one-time setup, you will misread startup behavior. This is particularly important because reconciliation is not just observation; it sounds like state-shaping behavior.

### Fix direction
Split it into:
- `perform_startup_reconciliation()`
- `perform_first_run_setup()`

Or keep one wrapper but name/trace/log them separately.

### Proof gap
Multiple CLI tests in the dump explicitly monkeypatch `perform_first_run_setup` to `lambda: None`, which means the startup reconciliation behavior is routinely bypassed in those tests:
- `tests/interfaces/test_cli_protocol_parity_campaign.py`
- `tests/interfaces/test_cli_protocol_replay.py`

So the tests that look like startup/CLI verification are not actually proving the real startup behavior.

---

## Finding 3 — `assign_team` says a team switch happened, but the visible behavior is only logging plus a message
**Severity:** High  
**File / Function:** `orket/driver.py:execute_plan()`  
**Evidence:** lines 224-251, especially 229-233

### What the code appears to claim
For `action == "assign_team"`, the returned string says:

> `Resource Selection: Switching to Team '...' in '...'`

That reads like a real state transition.

### What it actually does
The branch:
- extracts `suggested_team` and `suggested_department`,
- writes a log event,
- returns a message.

It does **not** visibly:
- update driver state,
- persist the selection,
- mutate any current team context,
- change downstream routing within this function.

### Behavioral truth
This is **message-as-action**. The branch narrates that a switch happened, but in the code shown it only logs and returns text.

### Why this matters
Operators can believe Orket changed execution context when it did not. This is one of the clearest behavioral lies in the dump.

### Fix direction
Either:
- implement real team-selection state change and persistence, or
- change the response text to something truthful like “Suggested team assignment” rather than “Switching to Team...”.

### Proof gap
The visible test file `tests/application/test_driver_conversation.py` exercises `execute_plan()` for conversation and unknown-action handling, but not the behavioral effect of `assign_team`. No proof in the dump shows a team selection actually changes runtime state.

---

## Finding 4 — the driver’s fallback prompt advertises a broader structural action surface than the executor actually implements
**Severity:** High  
**File / Functions:** `orket/driver.py:process_request()`, `orket/driver.py:execute_plan()`  
**Evidence:** prompt lines 130-177; executor lines 224-251

### What the code appears to claim
The fallback system prompt tells the model:

- structural requests include create, update, move, delete, direct
- choose the correct Orket action and produce only JSON

That language implies a relatively broad controller surface.

### What it actually does
`execute_plan()` only has concrete branches for:
- `assign_team`
- `turn_directive`
- conversation aliases
- structural actions limited to `create_issue`, `create_epic`, `create_rock`, `adopt_issue`

Everything else falls through to:
- `response_text` if present, else
- generic help text.

### Behavioral truth
The prompt surface is larger than the executor surface. The model is being asked to operate a richer action vocabulary than the runtime actually honors.

### Why this matters
This creates a **false affordance**. You can believe the driver supports general update/move/delete style board control because the prompt says so, while the runtime path does not implement that surface.

### Fix direction
Make the prompt enumerate only the actions that `execute_plan()` can actually execute, or expand the executor to cover the advertised surface.

### Proof gap
The conversation test validates only that certain responses do not emit structural fallback language. It does not establish prompt-to-executor action parity.

---

## Finding 5 — bare `reforge ...` cannot reach the `reforge` handler, even though a `reforge` verb branch exists
**Severity:** High  
**File / Function:** `orket/driver_support_cli.py:_try_cli_command()`  
**Evidence:** lines 25-33 and 42-56; help text lines 178-190

### What the code appears to claim
There is a real `if verb == "reforge"` handler and help text documents:
- `/reforge inspect ...`
- `/reforge run ...`

The surrounding control flow makes it look like CLI verbs can be recognized either with or without a slash if they are known verbs.

### What it actually does
The CLI form is recognized only if:
- the text starts with `/`, or
- the first word is in `known_cli_verbs`

But `known_cli_verbs` is:

```python
{"list", "show", "create", "add-card", "add_card", "list-cards", "list_cards"}
```

`reforge` is missing.

So:
- `/reforge ...` works because of the leading slash,
- `reforge ...` does **not** count as CLI form,
- the `if verb == "reforge"` branch is unreachable for bare-text command input.

### Behavioral truth
One natural command form is dead. The branch exists, but the recognizer blocks it.

### Why this matters
This is an **unreachable branch on a plausible user input path**. The code looks wired more broadly than it is.

### Fix direction
Add `reforge` to `known_cli_verbs` or remove the impression that bare command form should work.

### Proof gap
I found no test coverage in the uploaded dump proving bare `reforge` command recognition.

---

## Finding 6 — `_load_engine_configs()` silently degrades from governed config loading to fallback prompting with no hard signal
**Severity:** High  
**File / Function:** `orket/driver.py:_load_engine_configs()`  
**Evidence:** lines 58-81 and downstream prompt selection lines 122-130

### What the code appears to claim
The driver loads role/skill/dialect assets so it can operate under structured governed prompting.

### What it actually does
It swallows config load failures:

```python
try:
    self.skill = loader.load_asset(...)
except (FileNotFoundError, ValueError, CardNotFound):
    pass
...
try:
    self.dialect = loader.load_asset(...)
except (FileNotFoundError, ValueError, CardNotFound):
    pass
```

If either is absent, the driver silently falls back to the generic embedded system prompt.

### Behavioral truth
A config problem does not produce a hard setup failure or even an obvious warning in this function. It silently changes runtime semantics from governed asset-driven prompting to generic fallback prompting.

### Why this matters
This is a **silent guarantee drop**. You could think you are testing one prompting regime while actually exercising another because config load broke.

### Fix direction
At minimum:
- log an explicit degradation event,
- expose whether the driver is operating in governed vs fallback prompt mode,
- consider failing hard in strict/production paths.

### Proof gap
No visible test in the dump asserts that missing skill/dialect assets are surfaced as degradation rather than silently accepted.

---

## Finding 7 — `get_board_hierarchy()` accepts `auto_fix` but never uses it
**Severity:** Medium  
**File / Function:** `orket/board.py:get_board_hierarchy()`  
**Evidence:** line 7 and whole function body

### What the code appears to claim
The signature includes `auto_fix: bool = False`, which implies a behavioral mode switch: inspect-only vs inspect-and-correct.

### What it actually does
The parameter is never used.

### Behavioral truth
`auto_fix` is a dead affordance. The function does not have an auto-fix mode.

### Why this matters
A dead parameter is not just clutter here; it implies a correction capability that does not exist.

### Fix direction
Delete the parameter or implement the behavior.

---

## Finding 8 — `get_board_hierarchy()` silently drops malformed/missing assets, so the returned hierarchy can look cleaner than reality
**Severity:** High  
**File / Function:** `orket/board.py:get_board_hierarchy()`  
**Evidence:** lines 29-72, 74-104

### What the code appears to claim
It “Builds a tree” and “Identifies orphaned Epics and Issues.”

That reads like a truthful structural inventory.

### What it actually does
Multiple exception paths just `pass`:
- failed rock load: lines 71-72
- failed orphan epic load: lines 92-93
- failed issue load: lines 103-104

For nested epic loading within a rock, it records an error stub. But for top-level rock/epic/issue loading in orphan scans, broken assets can just vanish from the output.

### Behavioral truth
The function is not a truthful full inventory. It is a best-effort hierarchy view that can silently omit broken assets.

### Why this matters
The UI/consumer can see a seemingly valid board state while data corruption or schema breakage is actually present.

### Fix direction
Do not `pass` on top-level asset load failures in a structural integrity function. Surface them in `alerts` or an explicit `load_errors` section.

---

## Finding 9 — orphan issue detection uses weak identity semantics and the comment does not match the actual implementation language
**Severity:** Medium  
**File / Function:** `orket/board.py:get_board_hierarchy()`  
**Evidence:** lines 50-57, 86-90, 95-102

### What the code appears to claim
The comment says:

> `# We use summary as a weak ID for now ...`

### What it actually does
It stores `i.name` into `issues_in_epics`, then later checks standalone `issue.name` membership against that set.

So the actual weak identifier is `name`, not “summary” as the comment says.

### Behavioral truth
There are two drifts here:
1. comment-to-code mismatch (`summary` vs `name`)
2. orphan detection uses a weak/non-authoritative field instead of a durable standalone issue identity

### Why this matters
You can misclassify orphan status if names collide or drift. The code also invites misunderstanding because the comment describes a different field than the one actually used.

### Fix direction
Use authoritative issue IDs where possible. If only weak matching exists, document the actual field used.

---

## Finding 10 — `process_request()` uses first-brace / last-brace slicing to recover JSON, which is broader and less truthful than the protocol it claims
**Severity:** Medium  
**File / Function:** `orket/driver.py:process_request()`  
**Evidence:** lines 186-194

### What the code appears to claim
The system prompt says the model output must always be a single JSON object and nothing else.

### What it actually does
Instead of requiring the whole response to be JSON, it searches for the first `{` and last `}` and parses the slice.

### Behavioral truth
The runtime parser tolerates extra leading/trailing text as long as there is some brace-bounded object somewhere in the string.

That means the actual protocol is “extract the outermost brace slice and attempt to parse it,” not “response must be only a single JSON object.”

### Why this matters
This can:
- make malformed outputs look acceptable,
- parse the wrong object if braces appear in commentary,
- hide protocol violations.

### Fix direction
If protocol strictness matters, require the whole trimmed response to be valid JSON. Do not repair it by broad brace slicing unless explicitly in a compatibility mode.

---

## Finding 11 — provider telemetry uses the key `provider_backend` for two different concepts
**Severity:** Medium  
**File / Function:** `orket/adapters/llm/local_model_provider.py:_complete_openai_compat()`  
**Evidence:** lines 333-345

### What the code appears to claim
Telemetry should distinguish backend vs provider name.

The class itself has:
- `self.provider_backend` — normalized backend family (`openai_compat` or `ollama`)
- `self.provider_name` — concrete provider label (`lmstudio`, `openai_compat`, `ollama`)

### What it actually does
In the returned `raw` payload:

```python
"provider_backend": self.provider_name,
...
"orket_trace": {
    "provider_backend": self.provider_backend,
    "provider_name": self.provider_name,
},
```

So top-level `provider_backend` contains `provider_name`, while nested `orket_trace.provider_backend` contains the actual backend.

### Behavioral truth
The same field label points to different semantics depending on location.

### Why this matters
This poisons telemetry interpretation and can make analysis code think backend and provider name are the same thing.

### Fix direction
Top-level `provider_backend` should hold `self.provider_backend`; add a separate `provider_name` field if desired.

---

## Finding 12 — local version reporting can lie about the actual checkout during development
**Severity:** Medium  
**Files:** `orket/__init__.py`, `pyproject.toml`  
**Evidence:** `orket/__init__.py` lines 4-8; `pyproject.toml` line 7

### What the code appears to claim
If the package is not installed, it reports a local version.

### What it actually does
It hardcodes:

```python
__version__ = "0.3.9-local"
```

while `pyproject.toml` declares:

```toml
version = "0.3.16"
```

### Behavioral truth
Local/dev code can report a version materially older than the checkout you are actually running.

### Why this matters
This contaminates logs, support output, debugging, and any policy/compatibility decision tied to version labels.

### Fix direction
Derive local version from package metadata, git metadata, or `pyproject.toml`; do not hardcode a stale fallback.

---

## Finding 13 — startup/config load failures are repeatedly swallowed in driver initialization, collapsing truth into fallback behavior
**Severity:** Medium  
**File / Functions:** `orket/driver.py:__init__()`, `_load_engine_configs()`  
**Evidence:** lines 39-45, 61-64, 78-80

### What the code appears to claim
Driver initialization selects org/model/governed configs.

### What it actually does
Failures to load:
- organization config,
- skill config,
- dialect config

are each swallowed with `pass`.

### Behavioral truth
Initialization can fail partially and still produce a functioning driver object, but with different semantics than intended and without an obvious operator-visible signal.

### Why this matters
This is the broader pattern behind Findings 6 and 12: **silent downgrade to “something still runs.”** That is often the fastest path to false-green operation.

### Fix direction
Emit explicit degradation markers and expose them in capabilities/diagnostics.

---

## Finding 14 — the startup/CLI protocol tests visibly bypass real startup behavior
**Severity:** Medium  
**Files:**  
- `tests/interfaces/test_cli_protocol_parity_campaign.py`
- `tests/interfaces/test_cli_protocol_replay.py`

### What the code appears to claim
These are CLI protocol parity/replay tests, so they look like meaningful end-to-end-ish startup/CLI proofs.

### What they actually do
They repeatedly monkeypatch:

```python
monkeypatch.setattr(cli_module, "perform_first_run_setup", lambda: None)
```

### Behavioral truth
These tests prove CLI protocol behavior **with startup setup/reconciliation disabled**. They do not prove what happens in the real CLI startup path.

### Why this matters
Given that `perform_first_run_setup()` actually performs every-startup reconciliation, bypassing it changes the semantics of the tested execution path.

### Fix direction
Keep fast tests if needed, but add at least one real startup-path test that exercises the actual setup/reconciliation behavior.

---

## Finding 15 — the runtime-context bridge looks important, but the repo status shows the proof surface is still in-flight
**Severity:** Medium  
**Files:**  
- `orket/application/workflows/turn_executor_runtime.py`
- `tests/application/test_turn_executor_runtime_context_bridge.py`
- `review-git-status.txt`
- `review-git-diffstat.txt`

### What the code appears to claim
`invoke_model_complete()` tries to preserve `runtime_context` by:
1. calling `model_client.complete(..., runtime_context=...)` if supported,
2. otherwise calling `model_client.provider.complete(..., runtime_context=...)` if supported,
3. otherwise calling `complete(messages)` without context.

### What it actually means behaviorally
This is a real, meaningful fallback chain. But the repo status embedded in the dump shows this area is not settled:
- `orket/application/workflows/turn_executor_runtime.py` modified
- `tests/adapters/test_model_invocation.py` modified
- `tests/application/test_turn_executor_runtime_context_bridge.py` untracked

### Behavioral truth
The code path may be improving, but the proof surface is visibly still under construction in this snapshot. That matters because this is exactly the kind of seam where context silently disappears.

### Why this matters
A high-risk semantic path can look “covered” while still being mid-edit. The danger is not necessarily that the code is wrong; the danger is false confidence that it is already truly locked.

### Fix direction
Land and stabilize the bridge tests, then add one integrated proof at the provider path that verifies runtime context survives the actual invocation seam you care about.

---

## Finding 16 — the driver claims deterministic JSON discipline, but its error/fallback model still allows soft protocol drift
**Severity:** Medium  
**File / Function:** `orket/driver.py:process_request()`  
**Evidence:** lines 179-222

### What the code appears to claim
The system prompt emphasizes precise JSON-only responses and deterministic structure.

### What it actually does
There are at least three softness points:
1. broad brace-slice parsing (Finding 10),
2. if no JSON is found, it returns a freeform failure message string,
3. if parsing or execution fails, it returns another freeform failure string.

### Behavioral truth
The function is not running a strict machine envelope all the way through. It is machine-aspirational on the input side, but user-facing string-fallback on failure.

### Why this matters
That may be okay for a human-facing CLI, but it is not the same as a strict deterministic protocol boundary. If downstream code starts relying on this as machine-disciplined control, this softness becomes a lie.

### Fix direction
Separate strict protocol mode from operator-friendly compatibility mode, and surface which mode is active.

---

## Finding 17 — `get_board_hierarchy()` is a mixed integrity/reporting function without a trustworthy error contract
**Severity:** Medium  
**File / Function:** `orket/board.py:get_board_hierarchy()`  
**Evidence:** whole function

### What the code appears to claim
One function builds the hierarchy, finds orphans, exposes artifacts, and adds alerts.

### What it actually does
It mixes:
- inventory
- integrity checking
- artifact listing
- partial nested error stubs
- silent top-level omission on some failures

### Behavioral truth
The caller cannot cleanly tell the difference between:
- “no issue exists,”
- “issue exists but is broken,”
- “issue load failed and was swallowed.”

### Why this matters
This is not primarily an architecture critique. It is a runtime semantics problem: the function does not provide a truthful error contract for an integrity-sensitive view.

### Fix direction
Return separate sections for:
- loaded entities,
- load failures,
- integrity orphans,
- derived alerts.

---

## False-Green / Proof-Gap Summary

These are the most important proof gaps from the dump:

1. **No visible test hit for `get_engine_recommendations()`**  
   The no-op recommendation logic appears untested.

2. **No visible test proving bare `reforge ...` command routing**  
   The recognizer/handler mismatch appears untested.

3. **`assign_team` lacks a state-effect proof**  
   Visible tests do not prove a team switch actually changes runtime state.

4. **CLI protocol tests bypass startup reconciliation**  
   They monkeypatch out `perform_first_run_setup()`, so they are not proof of real startup semantics.

5. **Runtime context bridge area is visibly in-flight in repo status**  
   Important change, but the proof surface in this snapshot is not yet stable.

---

## Pattern-Level Diagnosis

The repo’s main behavioral danger is not random bugs. It is **semantic overclaim**:

- names imply stronger guarantees than the function delivers,
- prompts/help text imply broader action surfaces than the executor supports,
- fallback behavior hides degraded mode,
- test surfaces prove curated slices, not the full real runtime seam.

This is exactly how local-LLM systems drift into false-green operation: things “work” enough to produce output, while key guarantees are not actually present.

---

## Remediation Order

### 1. Stop narrated actions that do not mutate state
Start with:
- `assign_team`
- any similar message-as-action branches

### 2. Eliminate silent downgrade paths
Start with:
- `_load_engine_configs()`
- org config load in driver init
- structural hierarchy load omissions

### 3. Remove dead affordances and hidden no-ops
Start with:
- `get_engine_recommendations()` high-tier logic
- `auto_fix` in `get_board_hierarchy()`
- bare `reforge` recognizer mismatch

### 4. Tighten the protocol boundary
Start with:
- strict JSON parsing mode instead of brace-slice recovery
- explicit governed-vs-fallback prompt mode visibility

### 5. Repair proof
Add tests that prove:
- engine recommendation logic actually matches intended semantics,
- `assign_team` changes real runtime state or is truthfully only a suggestion,
- bare and slash-prefixed CLI verbs both behave as documented,
- startup reconciliation is exercised in at least one real CLI path,
- runtime context survives the actual provider seam.

---

## Bottom Line

The strongest truth claim I can make from this dump is:

**Orket often still “does something,” but several important paths do not do the exact thing their names, comments, prompts, or returned messages lead you to believe.**

The core fix is not cosmetic cleanup. It is to make the runtime tell the truth:
- truthful names,
- truthful fallbacks,
- truthful action effects,
- truthful telemetry,
- truthful tests.
