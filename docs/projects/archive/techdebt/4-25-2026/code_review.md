# Orket — Brutal Code Review
*Reviewed April 25, 2026 · Claude Sonnet 4.6*

---

## Overview

Orket is a sophisticated local-first AI orchestration runtime. The core intent is strong: deterministic, auditable, local-canonical-authority execution of multi-agent workflows. But the codebase carries real structural debt that will compound as complexity grows. This review identifies **58 issues** across architecture, typing, security, performance, testing, CI/CD, naming, and behavioral correctness.

Severity tags: 🔴 Critical · 🟠 High · 🟡 Medium · 🔵 Low

---

## Section 1 — Architecture & Design (Issues 1–14)

**Issue 1 🔴 — `dict[str, Any]` contagion at module boundaries**

`dict[str, Any]` is used as the primary data carrier across nearly every module boundary: `apply_action`, `is_terminal`, `observe`, `serialize_state`, `run_round`, `build_response`, `_load_fixture`, etc. Once `Any` enters a call chain it bypasses the type checker everywhere downstream. Every function that returns or accepts `dict[str, Any]` is a potential runtime crash waiting on a malformed key. The codebase has typed dataclasses (`ReactorConfig`, `ReactorState`, `AgentConfig`, `ProbeConfig`, `RunConfig`) but uses them inconsistently — real boundary enforcement is absent.

```python
# Current — unchecked on every call
def apply_action(self, state: dict[str, Any], ...) -> TransitionResult:
    next_state["ticks"] = int(next_state.get("ticks", 0)) + 1  # crashes if ticks=None externally set
```

**Fix:** Define typed `State`, `Action`, and `Observation` protocols for the `RuleSystem` contract and enforce them via `Protocol` or `TypeVar` bounds.

---

**Issue 2 🔴 — `organization: Any` in `GiteaStateLoopRunner` — structural duck typing without a contract**

`GiteaStateLoopRunner` stores `organization: Any` and accesses it via `_process_rule` which does:
```python
process_rules = getattr(self.organization, "process_rules", None)
if isinstance(process_rules, dict):
    return process_rules.get(key, default)
getter = getattr(process_rules, "get", None)
if callable(getter):
    return getter(key, default)
return getattr(process_rules, key, default)
```
This is three layers of defensive duck typing for a field that should have a defined interface. If `organization` is ever `None` or a different type, `_process_rule` silently returns `default` for every key — no error, wrong behavior. There is no `Organization` protocol or dataclass enforced at construction time.

---

**Issue 3 🟠 — Empty subclass `GoldenDeterminismRuleSystem` is not a design, it is a stub**

```python
class GoldenDeterminismRuleSystem(LoopRuleSystem):
    pass
```
This one-liner in its own file adds zero logic. It exists only to give a different name to `LoopRuleSystem`. This should be a registry entry (`"golden_determinism": LoopRuleSystem`) not a class. The current approach creates a false impression of behavioral difference and will mislead anyone maintaining it.

---

**Issue 4 🟠 — `State = Any`, `Action = Any`, `Observation = Any` type aliases add zero safety**

```python
AgentId = str
State = Any
Action = Any
Observation = Any
```
These aliases in `rulesim/types.py` look like types but have no enforcement. `Action = Any` means `def apply_action(state: State, action: Action)` is no different from `def apply_action(state, action)` to the type checker. Either use `TypeVar` bounds against a `Protocol` or delete these aliases.

---

**Issue 5 🟠 — RuleSystem toys share identical method bodies with no ABC or Protocol**

`DeadlockRuleSystem`, `LoopRuleSystem`, `IllegalActionRuleSystem`, and the implicit protocol all implement the same 8 methods with no shared base. A `RuleSystem` Protocol exists only conceptually. If a new toy is added with a misspelled method, it silently breaks the runner — no type error, no test failure at registration time.

---

**Issue 6 🟠 — `deepcopy(state)` on every `apply_action` call in all rulesim toys**

Every `apply_action` deep-copies the full state before mutation:
```python
next_state = deepcopy(state)
next_state["ticks"] = int(next_state.get("ticks", 0)) + 1
```
For small states this is fine. But the rulesim is designed to run many episodes — the ODR gate tool loops thousands of permuted rounds. `deepcopy` on large nested state dicts is O(N) per step. No structural sharing, no immutable record approach. This is a latent performance cliff.

---

**Issue 7 🟠 — `build_orket_session_id` hash fallback creates silent session collisions**

```python
fallback_payload = {
    "provider_name": provider_name,
    "model": model,
    "messages_head": fallback_messages[:2],
}
digest = hashlib.sha256(...).hexdigest()
return f"derived-{digest[:16]}"
```
Two sessions with the same provider, model, and first two messages will get the same `derived-*` session ID. This is not hypothetical — in testing or when running repeatable benchmarks this collision is guaranteed. Sessions could clobber each other in the control plane database.

---

**Issue 8 🟡 — `extract_openai_timings` has triple-level fallback chains that are unmaintainable**

```python
if prompt_ms is None:
    prompt_ms = _ns_to_ms(timings.get("prompt_eval_duration"))
if predicted_ms is None:
    predicted_ms = _ns_to_ms(timings.get("eval_duration"))
# ... then payload-level fallbacks ...
```
Nine separate fallback assignments across three different payload locations (timings dict, Ollama native fields, top-level payload). This function is essentially a compatibility shim for multiple provider formats crammed into one place. Any new provider will add more branches. This needs a per-provider extractor registry.

---

**Issue 9 🟡 — `_permute_fixture` shuffles a hardcoded key list that may not match fixture schemas**

```python
for key in ("nodes", "edges", "relationships", "links", "refs"):
    values = graph.get(key)
    if isinstance(values, list):
        rng.shuffle(values)
```
If the actual fixture graph uses a key not in this list (e.g., `"connections"`, `"vertices"`), the permutation is silently skipped. The ODR determinism test would then pass trivially because the graph is not actually being permuted. This should fail loudly if no shufflable keys are found.

---

**Issue 10 🟡 — `GiteaStateLoopRunner.run()` runtime guard is on the wrong object**

```python
if self.state_backend_mode != "gitea":
    raise ValueError("run_gitea_state_loop requires state_backend_mode='gitea'")
```
This guard is inside the instance method, meaning the object can be constructed in an invalid state and only fails at `.run()` call time. The check should be in `__post_init__` or a `__init__` equivalent, making invalid construction impossible.

---

**Issue 11 🟡 — `_collect_ready_inputs` raises `RuntimeError` on readiness failure — too generic**

```python
raise RuntimeError(f"State backend mode 'gitea' pilot readiness failed: {failures}")
```
A `RuntimeError` with a freeform string cannot be caught or handled specifically. Define a `GiteaReadinessError(RuntimeError)` so callers can distinguish readiness failures from programming errors.

---

**Issue 12 🟡 — `select_response_headers` has an overly broad `x-` prefix allowlist**

```python
if lower in allowed_exact or lower.startswith("x-"):
    selected[lower] = str(value)
```
Any header starting with `x-` is forwarded, including `x-ratelimit-*`, `x-upstream-cache-*`, or provider-specific internal routing headers. These should not be forwarded to downstream consumers. The allowlist should be explicit, not prefix-based.

---

**Issue 13 🔵 — `chr(92)` used to embed a backslash in a format string**

```python
f"- scatter_dataset: `{str(out_scatter_path).replace(chr(92), '/')}`"
```
`chr(92)` is an intentionally opaque way to write `"\\"`. This is not clever — it is confusing. Use `str(out_scatter_path.as_posix())` which handles cross-platform path rendering correctly and is self-documenting.

---

**Issue 14 🔵 — `_report_file_name` relies on fragile string split for cycle ID parsing**

```python
if "_cycle-" in cycle_id:
    prefix, suffix = cycle_id.split("_cycle-", 1)
```
This works for the current naming convention but is not validated against the format contract. If `cycle_id = "2026-03-07_cycle-"` (empty suffix), `suffix` is empty and the function silently falls through to the normalized name. There is no assertion or error — the caller gets a different filename than expected.

---

## Section 2 — Type System & Runtime Correctness (Issues 15–25)

**Issue 15 🔴 — `str(action.get("kind") or "")` silently coerces wrong types**

This pattern appears in every `apply_action` and `action_key` method across all rulesim toys:
```python
kind = str(action.get("kind") or "")
```
If `kind` is `42` or `{"nested": "dict"}`, `str()` converts it without error. The function then proceeds with a nonsense string. This should be:
```python
kind = action.get("kind")
if not isinstance(kind, str):
    raise TypeError(f"Expected str for action.kind, got {type(kind).__name__}")
```

---

**Issue 16 🟠 — `_to_int` does not handle negative numbers**

```python
if isinstance(value, str) and value.strip().isdigit():
    return int(value.strip())
```
`isdigit()` returns `False` for `"-1"` or `"+5"`. If a provider returns a negative token count (which happens with some Ollama versions for prompt token refunds), this returns `None` silently and the usage tracking gets corrupted.

---

**Issue 17 🟠 — `extract_openai_content` returns empty string on structural error — callers cannot distinguish missing content from empty content**

```python
choices = payload.get("choices")
if not isinstance(choices, list) or not choices:
    return ""
```
An empty string return value from an LLM call is a legitimate response (e.g., a null tool call). Returning `""` for a malformed payload means the caller cannot tell whether the model returned nothing or the payload was broken. Should return `Optional[str]` with `None` for structural failure.

---

**Issue 18 🟠 — Session ID fallback in `build_orket_session_id` prioritizes `"seat_id"` over `"run_id"`**

```python
for key in ("seat_id", "thread_id", "run_id", "session_id"):
```
`seat_id` uniquely identifies a role within a run (e.g., `"COD-1"`), not a session. Using `seat_id` as the session ID means different seats in the same run could share a session, or the same seat across different runs could collide.

---

**Issue 19 🟠 — `validate_openai_messages` only validates `role` — no content type validation**

```python
def validate_openai_messages(messages: list[dict[str, Any]]) -> list[str]:
    allowed_roles = {"system", "user", "assistant", "tool"}
```
The function only checks roles. It does not validate that `content` exists, that tool messages have `tool_call_id`, or that system messages appear only at position 0. Malformed messages pass validation and cause provider-side errors that are then hard to diagnose.

---

**Issue 20 🟡 — `extract_openai_tool_calls` returns raw provider dicts without normalization**

```python
return [item for item in tool_calls if isinstance(item, dict)]
```
The returned dicts are the raw provider response. Callers receive OpenAI-format tool calls which differ from Ollama-format tool calls in key naming (`function.name` vs `name`). There is no normalization layer — this means adapter-specific parsing is pushed to all callers.

---

**Issue 21 🟡 — `_normalized_tools` fallback chain silently drops required tools**

```python
def _normalized_tools(runtime_context: Mapping[str, Any]) -> list[str]:
    required_action_tools = ...
    if required_action_tools:
        return required_action_tools
    scope = _scope_map(runtime_context)
    return _dedupe([...scope.get('declared_interfaces')...])
```
If neither `required_action_tools` nor `declared_interfaces` is present in the context, this returns an empty list. Downstream, the agent gets no tool constraints. The system does not log or warn when this fallback occurs — governance violations become invisible.

---

**Issue 22 🟡 — `_dedupe` is reimplemented multiple times across different modules**

A local `_dedupe` utility appears in at least `openai_native_tools.py` and likely elsewhere. There is no shared utility module for this idiom. When one implementation gets a bug fix, the others don't. Extract to `orket.utils.collections`.

---

**Issue 23 🟡 — `float(value)` cast in `_to_float` on an `int` input loses no precision but is unnecessary**

```python
if isinstance(value, (int, float)):
    return float(value)
```
`float(True)` returns `1.0` — `bool` is a subclass of `int` in Python, so a boolean field in a JSON response silently becomes `1.0`. This is a data integrity issue for token counts.

---

**Issue 24 🟡 — `build_prompt_fingerprint` computes SHA-256 on every call with no caching**

```python
def build_prompt_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ...).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
```
This is called on every LLM request. For large prompt payloads (context windows, system prompts), JSON serialization + SHA-256 is measurable. If the same payload is fingerprinted multiple times in a request lifecycle, there is no memoization.

---

**Issue 25 🔵 — `recover_structured_reasoning_answer` is called without a null guard on `reasoning_content`**

```python
reasoning_content = _extract_text(message.get("reasoning_content"))
return recover_structured_reasoning_answer(reasoning_content)
```
If `reasoning_content` is empty string, `recover_structured_reasoning_answer` is called on `""`. The behavior of that function on empty input is not visible in this review — if it raises or returns garbage, the caller gets a silent failure path.

---

## Section 3 — Security (Issues 26–33)

**Issue 26 🔴 — No enforcement that `ORKET_ENCRYPTION_KEY`, `SESSION_SECRET`, and `GITEA_WEBHOOK_SECRET` are changed from defaults**

The `.env.example` has:
```
ORKET_ENCRYPTION_KEY=your-32-byte-hex-key-here
SESSION_SECRET=your-session-secret-here
GITEA_WEBHOOK_SECRET=change-me-webhook-secret
```
There is no visible startup check that these are not default/empty values in non-local environments. A deployment that copies `.env.example` directly runs with placeholder secrets. This should be an explicit `FATAL` startup error when `ORKET_ALLOW_INSECURE_NO_API_KEY` is not set.

---

**Issue 27 🔴 — `MSSQL_SA_PASSWORD=YourStrong!Passw0rd` in `.env.example` looks like a real password**

This is a Microsoft documentation example password that passes common password strength checks. Developers scanning for placeholder credentials may not recognize it as a placeholder. It should be `MSSQL_SA_PASSWORD=change-me-sql-server-sa`.

---

**Issue 28 🟠 — API key is compared in `X-API-Key` header with no timing-safe comparison visible**

The API key auth uses header comparison. If the comparison is done with `==` on plain strings (the most natural Python approach), it is vulnerable to timing attacks. The SHA-256 fingerprint is logged (`api_key_fingerprint:sha256:...`) but the comparison itself should use `hmac.compare_digest`.

---

**Issue 29 🟠 — `ORKET_GITEA_ALLOW_INSECURE` env var allows TLS bypass with a comment note only**

```
# Local plaintext Gitea only. Do not enable in CI/prod.
# ORKET_GITEA_ALLOW_INSECURE=false
```
This is enforced only by a comment. If enabled in a CI environment by mistake, all Gitea traffic runs over plain HTTP including tokens and webhook secrets. The server should check the combination of `ORKET_GITEA_ALLOW_INSECURE=true` with `GITEA_URL` containing `https://` and emit a loud warning.

---

**Issue 30 🟠 — No CORS configuration visible for the FastAPI application**

The API exposes control plane endpoints. Without explicit CORS configuration, browser-based clients may rely on default permissive behavior or the framework's defaults. The CORS policy should be explicit, not implicit.

---

**Issue 31 🟡 — Rate limiting comment is ambiguous: "30 with ORKET_WEBHOOK_WORKERS=2"**

```
# Size ORKET_RATE_LIMIT for total workers, for example 30 with ORKET_WEBHOOK_WORKERS=2.
```
This implies the rate limit is per-worker and that the operator must multiply manually. But it is documented as a per-process limit. A naive operator sets `ORKET_RATE_LIMIT=60` believing it is the total, gets 120 actual requests/interval (60 per worker × 2 workers). The math and the description should be unambiguous.

---

**Issue 32 🟡 — `GITEA_ADMIN_EMAIL=admin@viberail.local` uses a `.local` mDNS domain**

`.local` domains are resolved via mDNS, not DNS. In containerized CI environments, mDNS is often unavailable. This default email will cause Gitea's own SMTP validation to fail silently in environments without mDNS. Use `admin@localhost.invalid` (RFC 6761 reserved) for placeholder emails.

---

**Issue 33 🔵 — No key rotation mechanism for `ORKET_ENCRYPTION_KEY`**

The encryption key for sensitive card data has no documented rotation procedure. If the key is compromised, there is no visible path to re-encrypt existing records with a new key. Encrypted-at-rest data has a lifecycle problem from day one.

---

## Section 4 — Database & Concurrency (Issues 34–38)

**Issue 34 🟠 — SQLite without WAL mode for concurrent async writes**

The control plane uses `aiosqlite` (SQLite). Default SQLite journal mode is `DELETE`, which serializes all writes at the file level and causes `database is locked` errors under concurrent access. No WAL mode configuration is visible. For a local-first async runtime, this will be the first scaling wall.

**Fix:** Add `PRAGMA journal_mode=WAL;` on connection open.

---

**Issue 35 🟠 — Lease/reservation system has TOCTOU race conditions with SQLite**

SQLite's transaction isolation prevents dirty reads but `aiosqlite` with the asyncio event loop releases the GIL between await points. A claim-check-then-update sequence across two `await` calls is not atomic unless wrapped in a `BEGIN IMMEDIATE` transaction. The current lease renewal and cleanup logic almost certainly has this gap.

---

**Issue 36 🟠 — No visible database schema migration framework**

There is no Alembic, Yoyo, or custom migration runner visible. Schema changes require manual `ALTER TABLE` or database recreation. In a runtime that stores durable control plane state, this is a production deployment risk with every release.

---

**Issue 37 🟡 — `resolve_control_plane_db_path` is called at `_build_worker` call time, not at construction**

If the database path changes between worker construction and worker execution (e.g., env var overridden in test), the worker silently uses the wrong database. The path should be resolved at construction time and stored on the worker object.

---

**Issue 38 🔵 — Test suite creates real `OrchestrationEngine` instances without explicit connection teardown**

```python
real_engine = OrchestrationEngine(workspace_root=workspace_root, db_path=...)
```
Tests using `tmp_path` rely on pytest's cleanup to remove the temp directory. But open `aiosqlite` connections hold a file handle on the database. On Windows this prevents directory deletion. Engines should be closed with `await real_engine.close()` in test teardown.

---

## Section 5 — Testing (Issues 39–46)

**Issue 39 🟠 — `monkeypatch.setenv("ORKET_API_KEY", "test-key")` is shared global state in async test contexts**

Multiple tests set the same env var. In a parallel test run (e.g., with `pytest-xdist`), one test's monkeypatch can bleed into another test's execution window. At minimum, this pattern should be in a fixture with session scope, not repeated inline.

---

**Issue 40 🟠 — `CardStatus.DONE` is used in tests without a visible import**

```python
await real_engine.cards.update_status("CARD-B", CardStatus.DONE)
```
`CardStatus` must be imported somewhere in the test file. If it is not, tests fail at collection time, not at runtime. When reviewing only the function body (as shown in the dump), the import dependency is invisible — a maintainability debt.

---

**Issue 41 🟠 — Module-level `client` in API tests interacts with module-level `engine` monkeypatching**

`client = TestClient(app)` is created at module import time. Tests that `monkeypatch.setattr(api_module, "engine", ...)` are patching a module-level global that the `TestClient` accesses. This works in serial execution but is not safe under parallel test execution.

---

**Issue 42 🟡 — `test_sandboxes_reject_unsupported_runtime_methods` uses a lambda that ignores `_sandbox_id`**

```python
lambda _sandbox_id: {"method_name": "nope", "args": []},
```
The underscore prefix correctly signals "unused," but the lambda returns a static dict regardless of input. This means the test cannot verify that the `sandbox_id` is correctly passed through the invocation chain.

---

**Issue 43 🟡 — Test helper `fake_get_sandboxes` and `fake_stop_sandbox` are defined inline in test functions**

Reusable fakes are defined inside individual test functions. When multiple tests need similar fakes, they are reimplemented. Extract to fixtures or a shared test utilities module.

---

**Issue 44 🟡 — No coverage threshold enforced in CI**

The CI runs `python -m pytest -q` but no coverage report is generated or minimum threshold enforced. The governance docs discuss "live proof" as the highest authority, but there is no automated gating on unit test coverage percentage.

---

**Issue 45 🟡 — `repro_odr_gate.py` uses `random.Random(seed + (perm_index * 7919))` — poor stream separation**

Multiplying by a prime does not create independent random streams. Two seeds that differ by `7919` produce the same permutation sequence for `perm_index=0` and `perm_index=1` respectively. Use `random.Random((seed, perm_index))` — Python's `Random` accepts hashable tuples as seeds and produces properly independent streams.

---

**Issue 46 🔵 — `_print_failure` function in `repro_odr_gate.py` prints to stdout and returns `1` — mixed concerns**

```python
def _print_failure(...) -> int:
    print(f"seed={seed}")
    ...
    return 1
```
A function that both produces output and returns an exit code is doing two things. Callers cannot suppress the output for testing. Split into `_format_failure_message(...) -> str` and let `main` decide whether to print.

---

## Section 6 — CI/CD & Governance (Issues 47–52)

**Issue 47 🟠 — `core-release-policy.yml` uses `github.event.before` which is empty on force pushes**

```yaml
BASE_SHA="${{ github.event.before }}"
```
On a force push to `main`, `github.event.before` is the zero SHA (`0000000000000000000000000000000000000000`). The commit range check then spans from the beginning of history, which is expensive and may produce false positives.

---

**Issue 48 🟠 — CalVer stamping in CI uses `--dry-run` — version numbers are never actually stamped**

```yaml
python scripts/ci/stamp_calver.py --pyproject "..." --dry-run
```
The `--dry-run` flag means the pyproject.toml version is never updated by CI. The published package likely ships with the version set at development time, not the CI-stamped CalVer. This is either intentional (and the comment misleads) or a bug.

---

**Issue 49 🟡 — 14 releases in 5 days (0.4.0 through 0.4.12) undermines semantic versioning meaning**

The changelog shows 14 patch releases in 5 days (March 12–17, 2026). The `Required Operator or Extension-Author Action` section is non-empty on several of these. Rapid micro-releases with operator action requirements defeat the purpose of semantic versioning — consumers cannot track what requires attention.

---

**Issue 50 🟡 — Docs-to-code ratio is extreme — documentation authority can diverge from implementation**

The project dump contains more lines of specification, contract delta, lane closeout, and governance documentation than actual Python source code. While thorough specs are valuable, this ratio increases the risk of documentation drift. There is no visible mechanism to detect when a contract doc is out of sync with the implementation it describes.

---

**Issue 51 🟡 — Baseline retention workflow produces results to `benchmarks/results/quant/quant_sweep/`**

The weekly baseline retention workflow writes artifacts to a path that overlaps with quant sweep result paths. If a quant sweep is running concurrently with the retention job, result files can be overwritten. The retention job should write to a dedicated timestamped directory.

---

**Issue 52 🔵 — `fail-fast: false` in monorepo CI matrix means broken packages don't block other packages**

```yaml
strategy:
  fail-fast: false
```
This is a pragmatic choice but means the CI can report partial success when one package is broken. A broken `orket` package should gate `orket-sdk` since the SDK depends on the core. Consider `fail-fast: true` or an explicit dependency ordering in the matrix.

---

## Section 7 — Naming & Modularity (Issues 53–58)

**Issue 53 🟡 — `openclaw_torture_adapter` is a violent and confusing module name**

Regardless of the testing framework origin, this name will cause pause for new contributors and is not self-documenting. Rename to `challenge_corpus_adapter` or `adversarial_test_adapter`.

---

**Issue 54 🟡 — `extract_openai_*` functions handle Ollama payloads — naming is misleading**

The functions `extract_openai_content`, `extract_openai_usage`, `extract_openai_tool_calls` are all in `openai_native_tools.py` but the fallback chains explicitly handle Ollama-format responses (`prompt_eval_duration`, `eval_duration`, `total_duration`). Rename to `extract_provider_content`, or split into per-provider extractors behind a common interface.

---

**Issue 55 🟡 — `GoldenDeterminismRuleSystem` as a separate file is modular overkill**

A zero-logic subclass in its own file is a module structure antipattern. It bloats the module count, adds an extra import, and gives the false impression of distinct behavior. See Issue 3 — this should be a registry alias.

---

**Issue 56 🟡 — `_work_claimed_card` raises `ValueError` for missing `card_id`**

```python
if not target:
    raise ValueError("missing card_id in gitea snapshot payload")
```
`ValueError` is appropriate for wrong argument types. A missing `card_id` in a snapshot payload is a domain error — it should be a named exception (e.g., `MalformedSnapshotError`) that the coordinator can catch and handle distinctly from programming errors.

---

**Issue 57 🔵 — `DEFAULT_SECTION_B_SKIP_REASON` is a module-level constant with a long human-readable string**

```python
DEFAULT_SECTION_B_SKIP_REASON = "not a release-candidate or enforce-window refresh cycle"
```
Long default strings as module constants are difficult to override in tests and become part of the public API surface unintentionally. These should be configuration parameters with no hardcoded defaults in the module body.

---

**Issue 58 🔵 — The `iDesign Validator Service` mentioned in changelog has no corresponding visible Python source in the dump**

The 0.3.8 changelog entry mentions `orket/services/idesign_validator.py` as a new service. This file is either absent from the dump or was removed. If removed, the changelog entry is stale documentation. If present but not dumped, the governance tooling may have an exclusion that hides key service code from review.

---

## Summary Table

| # | Area | Severity | One-Line Description |
|---|------|----------|----------------------|
| 1 | Architecture | 🔴 | `dict[str, Any]` contagion at all module boundaries |
| 2 | Architecture | 🔴 | `organization: Any` with unsafe duck typing |
| 3 | Architecture | 🟠 | Empty `GoldenDeterminismRuleSystem` subclass |
| 4 | Architecture | 🟠 | `State/Action/Observation = Any` adds no safety |
| 5 | Architecture | 🟠 | No Protocol or ABC for RuleSystem contract |
| 6 | Architecture | 🟠 | `deepcopy` on every game step |
| 7 | Architecture | 🟠 | Session ID hash fallback causes collisions |
| 8 | Architecture | 🟡 | `extract_openai_timings` triple fallback chains |
| 9 | Architecture | 🟡 | `_permute_fixture` hardcoded key list |
| 10 | Architecture | 🟡 | Runtime guard in wrong lifecycle location |
| 11 | Architecture | 🟡 | `RuntimeError` too generic for readiness failures |
| 12 | Architecture | 🟡 | `x-` prefix allowlist too broad |
| 13 | Architecture | 🔵 | `chr(92)` for backslash is opaque |
| 14 | Architecture | 🔵 | Fragile `_report_file_name` string parsing |
| 15 | Typing | 🔴 | Silent `str()` coercion of wrong types |
| 16 | Typing | 🟠 | `_to_int` fails for negative numbers |
| 17 | Typing | 🟠 | Empty string returned for structural error |
| 18 | Typing | 🟠 | `seat_id` misused as session fallback key |
| 19 | Typing | 🟠 | `validate_openai_messages` only validates role |
| 20 | Typing | 🟡 | Raw provider dicts returned without normalization |
| 21 | Typing | 🟡 | `_normalized_tools` silently drops tools |
| 22 | Typing | 🟡 | `_dedupe` reimplemented across modules |
| 23 | Typing | 🟡 | `bool` coerces to `1.0` via `float()` cast |
| 24 | Typing | 🟡 | No caching on `build_prompt_fingerprint` |
| 25 | Typing | 🔵 | No null guard before `recover_structured_reasoning_answer` |
| 26 | Security | 🔴 | No startup enforcement of required secrets |
| 27 | Security | 🔴 | `YourStrong!Passw0rd` looks legitimate |
| 28 | Security | 🟠 | API key comparison may not be timing-safe |
| 29 | Security | 🟠 | `ORKET_GITEA_ALLOW_INSECURE` enforced only by comment |
| 30 | Security | 🟠 | No visible CORS configuration |
| 31 | Security | 🟡 | Rate limit math is ambiguous in docs |
| 32 | Security | 🟡 | `.local` domain in admin email default |
| 33 | Security | 🔵 | No key rotation mechanism documented |
| 34 | Database | 🟠 | SQLite without WAL mode |
| 35 | Database | 🟠 | TOCTOU race in lease/reservation system |
| 36 | Database | 🟠 | No schema migration framework |
| 37 | Database | 🟡 | DB path resolved at call time, not construction |
| 38 | Database | 🔵 | No explicit engine teardown in tests |
| 39 | Testing | 🟠 | `monkeypatch.setenv` shared global state |
| 40 | Testing | 🟠 | `CardStatus` used without visible import |
| 41 | Testing | 🟠 | Module-level client + module-level engine patch |
| 42 | Testing | 🟡 | Lambda ignores `sandbox_id` parameter |
| 43 | Testing | 🟡 | Inline fakes not extracted to fixtures |
| 44 | Testing | 🟡 | No coverage threshold in CI |
| 45 | Testing | 🟡 | Poor random stream separation in ODR gate |
| 46 | Testing | 🔵 | `_print_failure` mixes output and return value |
| 47 | CI/CD | 🟠 | `github.event.before` empty on force push |
| 48 | CI/CD | 🟠 | CalVer `--dry-run` never stamps actual version |
| 49 | CI/CD | 🟡 | 14 releases in 5 days dilutes SemVer meaning |
| 50 | CI/CD | 🟡 | Docs-to-code ratio risks drift |
| 51 | CI/CD | 🟡 | Retention job writes to quant sweep path |
| 52 | CI/CD | 🔵 | `fail-fast: false` ignores inter-package deps |
| 53 | Naming | 🟡 | `openclaw_torture_adapter` violent/confusing name |
| 54 | Naming | 🟡 | `extract_openai_*` handles non-OpenAI payloads |
| 55 | Naming | 🟡 | `GoldenDeterminismRuleSystem` is a module antipattern |
| 56 | Naming | 🟡 | `ValueError` for domain error in `_work_claimed_card` |
| 57 | Naming | 🔵 | Long default strings as module constants |
| 58 | Naming | 🔵 | `iDesign Validator` missing from source dump |

---

*End of Code Review*
