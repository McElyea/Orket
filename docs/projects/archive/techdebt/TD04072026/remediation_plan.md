# Orket — Remediation Plan

**Source:** Findings from Code Review and Behavioral Review
**Priority:** P0 = system integrity / P1 = architectural correctness / P2 = hygiene

**Implementation status (2026-04-07):**
- Completed: P0-1, P0-2, P0-3, P0-4, P1-1, P1-2, P1-3, P1-4, P1-5, P1-6, P1-7, P2-1, P2-2, P2-3, P2-4, and P2-5.
- Closeout: runtime modules now live under bounded `orket/runtime/{config,evidence,execution,policy,registry,summary}/` packages with flat one-release import aliases, and SDK workloads now execute in a subprocess with manifest-declared stdlib import enforcement.

Items are ordered within each priority by blast radius.

---

## P0 — Fix Before Any External Integration

These defects affect the core governance guarantee. No adapter target should be integrated until these are resolved, because they undermine the value proposition of Orket itself.

---

### P0-1: Make mandatory interceptors fail-hard

**Problem (Code Review §1.1, Behavioral Review §1):** `TurnLifecycleInterceptors` swallows all exceptions from interceptors. A broken governance rule is a no-op, not a circuit-break.

**Plan:**
1. Add an `InterceptorKind` enum: `advisory` | `mandatory`.
2. Extend `TurnLifecycleInterceptor` registration to accept a `kind` argument.
3. In `apply_before_tool()` and `apply_after_model()`, catch exceptions from `mandatory` interceptors, log the error, and return a `MiddlewareOutcome(short_circuit=True, reason="interceptor_crash")` immediately. Do not continue to remaining interceptors.
4. Add a test that verifies a crashing `before_tool` mandatory interceptor prevents tool execution.
5. Update the SDK documentation to classify which interceptors the SDK registers and whether they are mandatory or advisory.

**Effort:** Medium — touches `hooks.py`, SDK, tests
**Risk:** Any interceptor that was accidentally crashing and being silently skipped will now break runs. Run the full test suite; treat new failures as previously hidden bugs.

---

### P0-2: Remove hardcoded `add_issue_comment` from agent core

**Problem (Code Review §1.2):** `Agent.run()` hardcodes a Gitea-specific tool name in the partial parse recovery path. This violates adapter isolation and produces a silent no-op on non-Gitea deployments.

**Plan:**
1. Remove the hardcoded tool replacement block entirely.
2. Replace with: `turn.partial_parse_failure = True`, set a structured error on the turn, and return the turn without executing any tool calls.
3. Let the caller (the orchestrator, not the agent) decide the recovery policy. The orchestrator can route to a human, retry, or escalate.
4. Add a `partial_parse_failure: bool` field to `ExecutionTurn` with a `ToolCallErrorClass.PARSE_PARTIAL` code.
5. Update the orchestrator to handle `partial_parse_failure=True` turns with a configurable recovery policy (default: escalate, not retry).

**Effort:** Small-Medium — touches `agent.py`, `execution.py`, caller
**Risk:** Callers currently relying on the comment being posted must update their handling. Audit all callers of `Agent.run()`.

---

### P0-3: Add `ToolCallErrorClass` to replace string error codes

**Problem (Code Review §1.5):** `ToolCall.error` is an untyped string. Machine-parseable governance is impossible.

**Plan:**
1. Add `class ToolCallErrorClass(str, Enum)` to `orket/core/domain/execution.py`:
   - `GATE_BLOCKED`
   - `UNKNOWN_TOOL`
   - `EXECUTION_FAILED`
   - `PARSE_PARTIAL`
   - `TIMEOUT`
   - `INTERCEPTOR_CRASH` (new, from P0-1)
2. Add `error_class: ToolCallErrorClass | None` to `ToolCall`, alongside the existing `error: str | None` message.
3. Migrate all `ToolCall` construction sites to set `error_class`.
4. Update `FinalTruthRecord` derivation logic to use `error_class` for classification rather than string matching.

**Effort:** Medium — mechanical but touches many construction sites
**Risk:** Low. Non-breaking if `error` field is kept alongside `error_class`.

---

### P0-4: Wire `EffectJournalEntryRecord` writes to the agent tool execution path

**Problem (Behavioral Review §5, §3):** `Agent.run()` calls `log_event("tool_call")` but not `ControlPlaneAuthorityService.append_effect_journal_entry()`. Tool side effects are logged but not journaled.

**Plan:**
1. Add an optional `journal: ControlPlaneAuthorityService | None` parameter to `Agent.__init__()`.
2. After each successful tool execution in `Agent.run()`, if `journal` is set, call `journal.append_effect_journal_entry()` with:
   - `effect_id`: derived from `tool_name + args` hash
   - `uncertainty_classification`: `confirmed` on success, `unconfirmed` on exception
   - `observed_result_ref`: hash of the result or error string
3. Provide a `NullControlPlaneAuthorityService` stub for environments without a persistence backend.
4. Document that without a `journal`, tool effects are logged only.

**Effort:** Large — requires threading the journal service through construction and understanding the journal's ID generation contract
**Risk:** Medium. Must ensure the journal write is not in the hot path for latency-sensitive deployments.

---

## P1 — Fix Before Production Hardening

These issues affect correctness and architectural integrity but do not immediately break governance.

---

### P1-1: Circuit-break agent on skill/dialect load failure

**Problem (Code Review §2.2, Behavioral Review §1 Gap 2):** Silent fallback to bare `description` when governance config fails to load.

**Plan:**
1. Add a `strict_config: bool = True` parameter to `Agent.__init__()`.
2. When `strict_config=True` (default), if `skill` or `dialect` fail to load, raise `AgentConfigurationError` rather than logging a warning and continuing.
3. Provide `strict_config=False` for development/local environments only.
4. Add `AgentConfigurationError` to the SDK so callers can catch and handle it.

**Effort:** Small
**Risk:** Runs that were silently degraded will now fail loudly. This is intentional.

---

### P1-2: Add partial-result recovery to OpenClaw adapter

**Problem (Code Review §2.3):** Subprocess failure on request N loses all context about which of 0..N-1 succeeded.

**Plan:**
1. Add a `completed_count: int` field to the exception raised on subprocess failure.
2. Return a `PartialAdapterResult(responses=responses_so_far, failed_at=index)` from `run_requests()` rather than raising.
3. Let the caller decide whether to retry from `failed_at` or abort.
4. Ensure the call site (wherever OpenClaw is invoked) records which indices were completed before deciding to retry, to prevent double-execution of governed actions.

**Effort:** Medium
**Risk:** Callers must update to handle `PartialAdapterResult`. Old callers treating `run_requests` as atomic need to be audited.

---

### P1-3: Fix `ControllerRunSummary` validator asymmetry

**Problem (Code Review §2.4):** `status="success"` with failed children passes validation.

**Plan:**
1. Add to `_validate_result_error_invariants`:
   ```python
   if self.status == "success" and any(item.status == "failed" for item in self.child_results):
       raise ValueError("controller.run_result_invariant_invalid")
   ```
2. Add tests for this invariant.
3. Review all other `ControllerRunStatus` / child_results combinations for missing invariants.

**Effort:** Small
**Risk:** Workloads that were reporting false success will now fail validation. Treat as found bugs.

---

### P1-4: Protect settings globals with threading primitives

**Problem (Code Review §1.4):** `_SETTINGS_CACHE` and `_PREFERENCES_CACHE` are unprotected module globals.

**Plan:**
1. Add `_SETTINGS_CACHE_LOCK = threading.RLock()` alongside the existing `_ENV_LOADED_LOCK`.
2. Wrap all reads and writes of `_SETTINGS_CACHE` and `_PREFERENCES_CACHE` in `with _SETTINGS_CACHE_LOCK:`.
3. Document the context var scoping limitation: "Settings injected via `set_runtime_settings_context()` are not visible to sync callers using `_run_settings_sync()`."
4. Add a warning log if `_run_settings_sync` is called when context vars are set.

**Effort:** Small
**Risk:** Low.

---

### P1-5: Schema-enforce `Session.transcript`

**Problem (Code Review §3.3, Behavioral Review §4):** The transcript is the primary replay record and it is untyped.

**Plan:**
1. Create `TranscriptTurn` as a Pydantic model with required fields: `role`, `summary`, `turn_index`, `tool_calls: list[ToolCallRecord]`, `schema_version: str`.
2. Change `transcript: list[dict[str, Any]]` to `transcript: list[TranscriptTurn]`.
3. Update `add_turn()` to accept and validate `TranscriptTurn`.
4. Add a migration path for reading old untyped transcripts (parse defensively, default missing fields).
5. Tag the schema with a version string to enable future migration.

**Effort:** Large — downstream callers of `transcript` must be updated
**Risk:** Breaking change for any caller constructing transcript dicts directly. Prioritize after identifying all callers.

---

### P1-6: Make extension config sections extensible

**Problem (Code Review §2.5):** `_SECTION_KEYS = frozenset({"mode", "memory", "voice"})` is a hardcoded constant.

**Plan:**
1. Move `_SECTION_KEYS` to a class attribute `ConfigPrecedenceResolver.SECTION_KEYS`.
2. Add a class method `ConfigPrecedenceResolver.register_section(name: str)` that adds to the set.
3. In `ExtensionManifest`, add an optional `config_sections: list[str]` field.
4. During extension registration, call `ConfigPrecedenceResolver.register_section()` for each declared section.
5. Document the section registration lifecycle in the SDK.

**Effort:** Small-Medium
**Risk:** Low. Non-breaking if existing sections remain.

---

### P1-7: Refactor `orket/runtime/` into bounded sub-packages

**Problem (Code Review §3.1):** 50+ files with no public API boundary, repeated organic splitting of single concepts.

**Plan:**
1. Identify the 5-7 conceptual domains in `orket/runtime/` (evidence graph, run summary, policy contracts, settings, loop control, artifact management, truth contracts).
2. Create sub-packages: `orket/runtime/evidence/`, `orket/runtime/summary/`, `orket/runtime/policy/`, etc.
3. Add `__init__.py` with explicit `__all__` to each sub-package, enforcing the public surface.
4. Migrate files incrementally. Add deprecation shims at the old module paths for one release cycle.
5. Add a CI lint rule that prevents direct cross-sub-package imports except through `__init__.py`.

**Effort:** X-Large — must be done incrementally over multiple PRs
**Risk:** High — many import paths will change. Must do one sub-package at a time with full test coverage.

---

## P2 — Hygiene and Technical Debt

These are lower-urgency improvements that reduce future maintenance cost.

---

### P2-1: Replace hand-rolled `.env` parser with `python-dotenv`

**Problem (Code Review §4):** `load_env()` doesn't handle quoted values, multi-line, or `export KEY=val` syntax.

**Plan:** Add `python-dotenv` as a dependency. Replace `load_env()` internals with `dotenv.dotenv_values()`. Keep the same public interface. Add test for quoted values.

**Effort:** Small

---

### P2-2: Raise `GenerateRequest.max_tokens` default in extension SDK

**Problem (Code Review §3.4):** 128 tokens causes silent truncation.

**Plan:** Change default to `2048`. Add a docstring: "Set this to the maximum safe output length for your model. 128 (old default) causes truncation for most tasks." Add a runtime warning if `max_tokens < 256`.

**Effort:** Trivial

---

### P2-3: Add `ConfigDict(extra="forbid")` to `EnvironmentConfig`

**Problem (Code Review §4):** `extra="allow"` silently accepts unknown config keys.

**Plan:** Change to `extra="ignore"` (not `allow`) as an intermediate step — unknown keys are dropped without error. Evaluate changing to `extra="forbid"` once all deployments are audited for unknown keys. Log a deprecation warning for any dropped key using `model_validator`.

**Effort:** Small-Medium — may break deployments with custom env config keys

---

### P2-4: Document and test the `GlobalState` per-test isolation contract

**Problem (Code Review §1.3):** The singleton comment says "tests should create a fresh GlobalState" but this is unenforced.

**Plan:** Add a pytest fixture `fresh_runtime_state` that creates a new `GlobalState` and monkey-patches `orket.state.runtime_state`. Document in `CONTRIBUTING.md` that all tests touching global state must use this fixture. Add a linting rule that flags direct references to `runtime_state` in test files without the fixture.

**Effort:** Small

---

### P2-5: Add runtime capability sandboxing to extensions

**Problem (Code Review §2.6):** Extension sandbox is import-scan-only.

**Plan (longer-term):**
1. Short term: Add a `allowed_stdlib_modules` field to `ExtensionManifest`. Document which stdlib modules are considered safe (e.g., `json`, `pathlib`, `dataclasses`) vs. dangerous (e.g., `subprocess`, `os`, `socket`).
2. Medium term: Run extension workloads in a subprocess with a restricted module import hook (`sys.meta_path` based) that blocks undeclared imports.
3. Long term: Evaluate `RestrictedPython` or a similar sandboxing library.

**Effort:** Large (medium term) / Trivial (short term documentation only)

---

## Remediation Priority Summary

| ID | Priority | Effort | Verdict |
|----|----------|--------|---------|
| P0-1 Mandatory interceptor fail-hard | P0 | Medium | Do first |
| P0-2 Remove hardcoded tool name | P0 | Small | Do first |
| P0-3 ToolCallErrorClass | P0 | Medium | Do with P0-2 |
| P0-4 Wire effect journal to exec path | P0 | Large | Plan in sprint |
| P1-1 Circuit-break on config failure | P1 | Small | Next sprint |
| P1-2 OpenClaw partial recovery | P1 | Medium | Next sprint |
| P1-3 Fix ControllerRunSummary invariant | P1 | Small | Do immediately |
| P1-4 Settings cache thread-safety | P1 | Small | Next sprint |
| P1-5 Schema-enforce transcript | P1 | Large | Plan in quarter |
| P1-6 Extensible config sections | P1 | Small | Next sprint |
| P1-7 Runtime package refactor | P1 | X-Large | Roadmap item |
| P2-1 dotenv | P2 | Small | Any sprint |
| P2-2 max_tokens default | P2 | Trivial | Do now |
| P2-3 extra=forbid on EnvironmentConfig | P2 | Small | Next sprint |
| P2-4 GlobalState test isolation | P2 | Small | Next sprint |
| P2-5 Extension sandboxing | P2 | Large | Roadmap item |

---

## Sequencing Recommendation

**Sprint 1 (Integrity):** P0-1 → P0-2 → P0-3 → P1-3 → P2-2
These are the highest-impact, lowest-effort fixes. They close the most dangerous behavioral gaps without requiring architectural surgery.

**Sprint 2 (Correctness):** P1-1 → P1-4 → P1-6 → P2-4 → P2-1
These harden the governance model and remove hidden failure modes.

**Sprint 3 (Architecture):** P0-4 (begin) → P1-2 → P1-5 (design)
These are the larger architectural changes that require design review before implementation.

**Roadmap:** P1-7 (runtime refactor) → P2-5 (extension sandboxing)
These are quarter-scale investments with significant test coverage requirements.
