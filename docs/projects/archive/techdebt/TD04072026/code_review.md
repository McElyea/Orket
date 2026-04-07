# Orket — Brutal Code Review

**Reviewer:** Static analysis of `project_dump.txt` (monorepo snapshot)
**Scope:** `orket/`, `orket_extension_sdk/`, CI scripts, core contracts
**Verdict summary:** Architecturally ambitious, partially coherent, with serious latent defects in the middleware safety path, a fragile tool-call parser, module-level global state that bleeds across tests, and an extension sandbox that is enforcement theater at runtime.

---

## 1. Critical Defects

### 1.1 Silent governance bypass via swallowed interceptor exceptions
**File:** `orket/application/middleware/hooks.py` — `TurnLifecycleInterceptors`

Every interceptor hook (`before_tool`, `before_prompt`, `after_model`, `after_tool`, `on_turn_failure`) catches bare `Exception` from each interceptor and calls `_record_interceptor_error` then **continues**. This means a broken governance interceptor — one that raises an unexpected exception — is silently skipped and execution proceeds as if it returned `None` (no block). This is a fail-open governance path. A governance rule that crashes due to a bug offers zero protection, and the caller has no way to know the rule never ran. This is the most dangerous defect in the codebase.

**Fix required:** Interceptors that are categorized as "blocking" (e.g., approval gates, policy guards) must not be swallowed. Distinguish advisory interceptors from mandatory interceptors, and treat mandatory interceptor failures as a hard `ToolGateViolation`.

---

### 1.2 Partial tool recovery silently replaces all pending tool calls with a hardcoded comment
**File:** `orket/agents/agent.py` — `Agent.run()`

```python
parsed_calls = [
    {
        "tool": "add_issue_comment",
        "args": {"comment": "Blocked: tool-call recovery was partial..."},
    }
]
```

When `ToolParser` reports partial recovery, all original tool calls are discarded and replaced with a single hardcoded invocation of `"add_issue_comment"`. Two problems:

1. The string `"add_issue_comment"` is a Gitea-specific tool name embedded in the agent core. This violates the adapter isolation that the rest of the architecture carefully maintains. If the host system doesn't have this tool, `tool_name not in self.tools` fires and it produces a `ToolCall(error="Unknown tool 'add_issue_comment'")` — silent no-op with a logged error.
2. The original partial parse results are thrown away entirely. A partially recovered call that was safe to execute is now blocked for the same reason as a fully unparseable one. There is no graduated response.

**Fix required:** Remove the hardcoded tool name. Emit a governed `ToolCall` with a structured error code. Let the caller (or a post-turn interceptor) decide the recovery policy.

---

### 1.3 Module-level asyncio.Lock() on `GlobalState` created at import time
**File:** `orket/state.py` — `GlobalState.__init__`

```python
self._ws_lock = asyncio.Lock()
```

The comment says "This is safe on Python 3.11 because asyncio locks no longer bind to a running loop at construction time." This is true for basic usage, but the `GlobalState` is a module-level singleton (`runtime_state = GlobalState()`). Tests that replace loop-scoped state will share this singleton unless they explicitly create a fresh `GlobalState`. The comment acknowledges this but leaves it to callers: "Tests that replace loop-scoped state should also create a fresh GlobalState." This contract is not enforced and will cause test pollution.

Additionally, `active_websockets` is a plain list under `_ws_lock`, but `get_websockets()` returns a shallow copy. Callers who mutate the returned list don't affect internal state, but callers who mutate the websocket *objects* in the list do, without any lock held.

**Fix required:** Make `GlobalState` a proper factory. Enforce per-test isolation at the fixture level. Document the shallow-copy semantics of `get_websockets`.

---

### 1.4 Settings module has unguarded cache reads in a threading context
**File:** `orket/settings.py`

`_SETTINGS_CACHE` and `_PREFERENCES_CACHE` are module-level globals mutated in async code and read in sync code. The `_ENV_LOADED_LOCK` protects `_ENV_LOADED` but nothing protects the cache variables. The `_settings_cache_enabled()` check disables caching in pytest but this is a test-only escape hatch, not a thread-safety mechanism. In production, concurrent settings reads/writes can observe a partially-written cache dict.

Additionally, `_run_settings_sync` calls `asyncio.run()` which creates a brand-new event loop. If called from a thread that has a running loop's context variables, those `contextvars.ContextVar` values set via `set_runtime_settings_context()` will not be visible in the new loop. Settings injected via context vars are invisible to sync callers.

**Fix required:** Protect cache globals with a `threading.RLock`. Document the context var scoping limitation explicitly; either propagate context to `asyncio.run()` or forbid sync access when context vars are set.

---

### 1.5 Tool error codes are unstructured strings
**File:** `orket/core/domain/execution.py` — `ToolCall`

`ToolCall.error` is typed as `str | None`. Gate rejections prepend `"[GATE] "` as a string prefix. Unknown tool errors are `f"Unknown tool '{tool_name}'"`. Subprocess errors are `str(exc)`. These are all formatted with different conventions and there is no machine-parseable error code enum. Downstream logic that needs to distinguish a gate block from a runtime exception from an unknown tool must parse these strings — which is brittle and will silently misclassify errors as the error message formats evolve.

**Fix required:** `ToolCall` needs a `ToolCallErrorClass` enum with values like `GATE_BLOCKED`, `UNKNOWN_TOOL`, `EXECUTION_FAILED`, `TIMEOUT`. Keep the human message alongside it.

---

## 2. Significant Defects

### 2.1 Tool call parser operates on raw natural-language text
**File:** `orket/application/services/tool_parser.py` (referenced, not shown in full)

`ToolParser.parse(text, diagnostics=capture)` parses tool calls from model output text using regex or XML-ish extraction. This is a known fragile pattern. The partial recovery path (`parse_partial_recovery`) already demonstrates that this parser cannot reliably handle model outputs. Any model output that embeds tool-call-like syntax in an explanatory sentence will produce false positives. Any model that emits slightly malformed XML will silently skip calls. The governance record for a turn that had calls skipped by the parser is a lie — it says the calls were made when they weren't.

### 2.2 `Agent._load_configs` silently degrades to bare description
**File:** `orket/agents/agent.py`

If `skill` or `dialect` config fail to load (FileNotFoundError, CardNotFound, ValueError), the agent falls back to using `self.description` as the system prompt with only a warning log. A mis-deployed config file silently runs governance without the governance skill's constraints, policies, and hallucination guard. There is no circuit-breaker. This is a silent-degradation failure in a system that claims fail-closed execution.

### 2.3 OpenClaw JSONL adapter has no partial recovery on subprocess failure
**File:** `orket/adapters/execution/openclaw_jsonl_adapter.py`

`run_requests()` sends all requests to a subprocess in sequence. If the subprocess crashes on request #3 of 10, the `finally` block kills the process and the exception propagates up. The caller has no way to know which of the 10 requests were already processed, so they cannot safely retry only the failed tail without potentially re-executing completed requests. For governed side effects, re-executing completed requests is a correctness violation.

### 2.4 ControllerRunSummary validator has an asymmetric invariant
**File:** `orket_extension_sdk/controller.py` — `ControllerRunSummary`

The model validator checks `status == "blocked" and any(item.status == "success")` but does NOT check `status == "success" and any(item.status == "failed")`. A summary that claims overall success while containing failed children passes validation. This is a truthfulness gap in the outcome classification layer.

### 2.5 ConfigPrecedenceResolver section keys are hardcoded
**File:** `orket/application/services/config_precedence_resolver.py`

`_SECTION_KEYS = frozenset({"mode", "memory", "voice"})` is a module-level frozen constant. Adding a new companion config section requires modifying this constant, redeploying, and there is no extension manifest path to declare new config sections. This will become a bottleneck as extensions need to carry their own config.

### 2.6 Extension sandbox is import-scan-only (no runtime enforcement)
**File:** `orket_extension_sdk/import_scan.py`

The import scanner correctly prevents `import orket` in extension code. But it only scans source text at build/registration time. At runtime, nothing prevents an extension's `Workload.run()` from calling `subprocess.run()`, `os.system()`, writing to arbitrary filesystem paths, or making network requests. The `CapabilityRegistry` restricts which Orket capabilities the extension *receives*, but cannot restrict what the extension does with Python's stdlib. The sandbox is advisory, not enforced.

---

## 3. Architecture Smells

### 3.1 `orket/runtime/` is a namespace graveyard
The runtime package contains 50+ files including:
- `run_evidence_graph_projection.py`
- `run_evidence_graph_projection_collect.py`
- `run_evidence_graph_projection_supplemental.py`
- `run_evidence_graph_projection_support.py`

Four files for one concept's projection logic. This pattern repeats across the runtime package (`run_summary`, `run_summary_artifact_provenance`, `run_summary_control_plane`, `run_summary_packet2`). This is organic file splitting without module boundary discipline. There is no `__init__.py`-enforced public API for the runtime package, meaning any module can import any other directly. Change blast radius is unknowable without static analysis.

### 3.2 The ODR is a verification mechanism, not an execution gate
The Output Determinism Reactor (`kernel/v1/`) computes canonical hashes and signatures over run outputs. It is used extensively in benchmarks and CI. But nothing in the visible execution path calls the ODR to *gate* whether a run is allowed to proceed. The ODR is downstream verification, not upstream governance. A run can complete, publish side effects, and write a `FinalTruthRecord` without the ODR ever being consulted. This is an architectural gap between the benchmark-level guarantees and the production-path guarantees.

### 3.3 The `Session` model has no schema enforcement on `transcript`
**File:** `orket/session.py`

`transcript: list[dict[str, Any]]` — the replay and traceability claims of the system depend on this transcript being structurally valid. It is a list of untyped dicts. `add_turn()` appends anything. There is no validation on turn shape, no schema version, no required fields. A corrupted or schema-drifted transcript will produce silent garbage on replay.

### 3.4 `GenerateRequest.max_tokens` defaults to 128
**File:** `orket_extension_sdk/llm.py`

128 tokens is a fragment for most governed actions. Any extension using the SDK's `LLMProvider` without explicitly setting `max_tokens` will silently truncate model output. Truncated outputs in a governed context will parse as partial tool calls and trigger the fragile recovery path described in 1.2.

### 3.5 Retry decision is buried in card config, not in the runtime policy
`IssueConfig.max_retries: int = 3` is embedded in the card data model. The retry policy file (`runtime/retry_classification_policy.py`) exists but the relationship between card-level `max_retries` and the runtime policy is not visible. Who wins when they disagree? There is no documented override order.

### 3.6 Gitea is the only VCS/state backend
Every VCS adapter in `orket/adapters/vcs/` and `orket/adapters/storage/` is Gitea-specific. `gitea_state_adapter.py`, `gitea_lease_manager.py`, `gitea_artifact_exporter.py`, `gitea_webhook_handler.py` — Gitea is not an abstracted backend, it is a hard dependency. If Gitea is unavailable, there is no fallback. The lease manager cannot grant leases. The state transitioner cannot transition state. The system has one point of failure for all durable operations.

---

## 4. Minor Issues

- `load_env()` is a hand-rolled .env parser instead of `python-dotenv`. It handles one edge case (comments, `key=value`) but not quoted values, multi-line values, or `export KEY=value` syntax. Silent mis-parse of a complex `.env` will produce wrong config with no error.
- `AgentFactory` exists but the factory pattern isn't enforced; `Agent` can be constructed directly. No deprecation path.
- `sanitize_name()` is called on agent names before loading role configs but the implementation isn't shown. If it's lossy (e.g., lowercases), two agents with names that differ only in case will load the same config. Whether this is intentional is undocumented.
- `model_config = ConfigDict(extra="allow")` on `EnvironmentConfig` silently accepts arbitrary keys. Unknown configuration is accepted without warning, making misconfiguration invisible.
- `ControllerRunEnvelope` has `extra="forbid"` but `ControllerRunSummary` uses `extra="forbid"` with a model_validator that raises `ValueError` — Pydantic will wrap this in a `ValidationError`, not a domain error. Callers catching domain errors will miss it.

---

## 5. Summary Table

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 1.1 | CRITICAL | `middleware/hooks.py` | Interceptor exceptions swallowed → fail-open governance |
| 1.2 | CRITICAL | `agents/agent.py` | Hardcoded `add_issue_comment` on partial parse recovery |
| 1.3 | CRITICAL | `state.py` | Module-level asyncio singleton bleeds across tests |
| 1.4 | HIGH | `settings.py` | Unguarded cache globals + context var invisibility in sync path |
| 1.5 | HIGH | `core/domain/execution.py` | `ToolCall.error` is untyped string — no machine-parseable error class |
| 2.1 | HIGH | `tool_parser.py` | Raw-text tool call parsing is structurally fragile |
| 2.2 | HIGH | `agents/agent.py` | Silent skill/dialect load failure degrades governance without alarm |
| 2.3 | HIGH | `openclaw_jsonl_adapter.py` | No partial recovery on subprocess failure |
| 2.4 | MEDIUM | `controller.py` | Asymmetric invariant in `ControllerRunSummary` validator |
| 2.5 | MEDIUM | `config_precedence_resolver.py` | Hardcoded section keys block extension config expansion |
| 2.6 | MEDIUM | `import_scan.py` | Runtime sandbox has no enforcement — import scan only |
| 3.1 | SMELL | `orket/runtime/` | 50+ file namespace graveyard with no public API boundary |
| 3.2 | SMELL | `kernel/v1/` | ODR is verification-only; not an execution gate |
| 3.3 | SMELL | `session.py` | `transcript` is untyped `list[dict[str, Any]]` |
| 3.4 | SMELL | SDK `llm.py` | `max_tokens=128` default causes silent truncation |
| 3.5 | SMELL | `schema.py` + runtime | Retry policy split between card config and runtime |
| 3.6 | SMELL | `adapters/vcs/`, `adapters/storage/` | Gitea is hard-wired, not an abstracted backend |
