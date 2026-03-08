I have now thoroughly read all 31 files. Let me compile the behavioral truth audit findings.

---

# BEHAVIORAL TRUTH AUDIT: Orchestration & Workflow Layer

## FINDINGS

---

### 1. `__getattr__` delegation on Orchestrator hides missing methods as runtime AttributeErrors

**File**: `C:\Source\Orket\orket\application\workflows\orchestrator.py`, lines 92-97

**Behavioral lie**: The `Orchestrator.__getattr__` delegates *any* attribute access to `orchestrator_ops`, binding module-level functions as bound methods via `MethodType`. If a method doesn't exist in orchestrator_ops, it raises `AttributeError` -- but the `_sync_patchable_symbols()` call on every attribute access is a hidden side-effect that silently mutates `orchestrator_ops` module globals.

**Severity**: MEDIUM

**Fix**: Remove the `__getattr__` delegation entirely. Declare all delegated methods explicitly (as already done for `verify_issue`, `_trigger_sandbox`, `execute_epic`, `_save_checkpoint`). This was already flagged in the prior review.

---

### 2. `__getattr__` delegation on TurnExecutor creates a 47-entry lookup table on every miss

**File**: `C:\Source\Orket\orket\application\workflows\turn_executor.py`, lines 87-138

**Behavioral lie**: Every call to a delegated method (e.g., `executor._prepare_messages`) constructs a fresh 47-entry dictionary, looks up the name, and returns a lambda/method reference. This dictionary is rebuilt on *every* call because `__getattr__` is only invoked on misses -- but since these are not set as instance attributes, the dict is reconstructed every time.

**Severity**: MEDIUM

**Fix**: Replace `__getattr__` with explicit properties or set the delegated methods in `__init__` so they are cached as instance attributes.

---

### 3. `_resolve_bool_flag` never checks env_raw for "0"/"false"/"no"/"off" -- falls through to `default`

**File**: `C:\Source\Orket\orket\application\workflows\orchestrator_ops.py`, lines 424-434

**Behavioral lie**: The `_resolve_bool_flag` only checks if `env_raw` is truthy. If the env var is set to "0", "false", "no", or "off", the function does NOT return `False` -- it falls through to check org process_rules. This means environment variable explicitly set to "false" can be overridden by org config, violating the stated env > org > default precedence.

**Severity**: HIGH

**Fix**: Add `if env_raw in {"0", "false", "no", "off"}: return False` after the truthy check at line 427.

---

### 4. GuardEvaluator.evaluate_contract is a pure identity function (no-op)

**File**: `C:\Source\Orket\orket\application\services\guard_agent.py`, lines 50-51

**Behavioral lie**: The class docstring says "This class owns check evaluation output and emits GuardContract." The method `evaluate_contract` simply returns its input unchanged. The `GuardAgent.evaluate` method calls this, making it look like evaluation happens in two stages, but the first stage does nothing.

**Severity**: LOW

**Fix**: Either implement actual check evaluation logic, or remove the `GuardEvaluator` class and call `GuardController.decide` directly. Add a comment that this is a placeholder for future evaluation logic.

---

### 5. `RuntimeVerifier._default_commands_for_profile` always returns empty list

**File**: `C:\Source\Orket\orket\application\services\runtime_verifier.py`, lines 138-141

**Behavioral lie**: The method name and the `_resolve_runtime_command_plan` flow suggest that default commands will be returned for different stack profiles (python, node, polyglot). In reality, both branches return `[]`. The entire command-execution pipeline in `verify()` (lines 55-68) will never execute unless org process_rules explicitly provides commands.

**Severity**: HIGH

**Fix**: Either add default commands (e.g., `["python", "-m", "py_compile"]` for python profiles), or rename the method and add a comment documenting that no default commands exist and the pipeline is config-driven only.

---

### 6. RuntimeVerifier._run_command uses `shell=True` for string commands -- security risk

**File**: `C:\Source\Orket\orket\application\services\runtime_verifier.py`, lines 239-275

**Behavioral lie**: This is in the "runtime verifier" (a security/integrity component) but accepts arbitrary string commands from org config and runs them with `shell=True`. The verifier that is supposed to validate safety introduces a shell injection vector.

**Severity**: CRITICAL

**Fix**: Always use list-form commands (`shell=False`). If the config provides a string, use `shlex.split()` to parse it safely.

---

### 7. `coordinator_store.py` uses `threading.Lock` in what should be an async context

**File**: `C:\Source\Orket\orket\application\services\coordinator_store.py`, lines 1-2, 14

**Behavioral lie**: The `InMemoryCoordinatorStore` uses `threading.Lock`. Since it is accessed from a FastAPI application (imported from fastapi at line 7), it will be used in an async event loop. A `threading.Lock` blocks the entire event loop when contended, defeating the purpose of async. The docstring doesn't warn about this.

**Severity**: HIGH

**Fix**: Replace `threading.Lock` with `asyncio.Lock` and make the methods async, or document that this store is only for sync/test contexts and must not be used in the async FastAPI path.

---

### 8. Swallowed TypeError in Scaffolder/DependencyManager/DeploymentPlanner construction

**File**: `C:\Source\Orket\orket\application\workflows\orchestrator_ops.py`, lines 700-705, 741-745, 779-784

**Behavioral lie**: The code wraps each service constructor in `try/except TypeError` and falls back to a simpler constructor signature. This silently swallows genuine TypeErrors (e.g., wrong argument types, None where a value is expected) that are not signature mismatches. The except clause catches ALL TypeErrors, not just "unexpected keyword argument" errors.

**Severity**: MEDIUM

**Fix**: Inspect the TypeError message for "unexpected keyword argument" before falling back, or use `inspect.signature` to check which parameters are supported before calling.

---

### 9. `_resolve_architecture_pattern` ignores "architect_decides" mode

**File**: `C:\Source\Orket\orket\application\workflows\orchestrator_ops.py`, lines 88-92

**Behavioral lie**: When architecture_mode is "architect_decides", this function returns "monolith" as default. The name suggests it resolves the architecture pattern from the mode, but for the "architect_decides" case it hardcodes monolith rather than deferring to the architect's decision. The architect decision contract exists (in turn_contract_rules.py) but this resolution overrides it at the scaffolding level.

**Severity**: MEDIUM

**Fix**: Return a sentinel like "pending" or "unresolved" for "architect_decides" mode, and have downstream consumers handle it appropriately.

---

### 10. `turn_executor_ops.py` broad except clause catches too many exception types

**File**: `C:\Source\Orket\orket\application\workflows\turn_executor_ops.py`, lines 379-397

**Behavioral lie**: The catch clause `except (ValueError, TypeError, KeyError, RuntimeError, OSError, AttributeError)` catches virtually all common exceptions including programming bugs (AttributeError, TypeError). These are returned as `TurnResult.failed("Unexpected error: ...", should_retry=False)` -- swallowing the distinction between operational errors and programming bugs.

**Severity**: HIGH

**Fix**: Narrow the catch to expected operational errors only (ValueError, RuntimeError, OSError). Let programming errors (AttributeError, TypeError, KeyError) propagate to be caught by proper error handling or crash visibly.

---

### 11. `synthesize_required_status_tool_call` silently mutates turn.tool_calls

**File**: `C:\Source\Orket\orket\application\workflows\turn_executor_runtime.py`, lines 76-116

**Behavioral lie**: The function name says "synthesize" but it silently appends a ToolCall to `turn.tool_calls` as a side effect. The caller in `turn_executor_ops.py` (line 186) calls this without checking the return value. The mutated tool call then gets executed by the tool dispatcher, which may fail with governance violations for a call the model never actually made.

**Severity**: HIGH

**Fix**: Return the synthesized tool call and let the caller decide whether to append it. Log when synthesis occurs so it's auditable.

---

### 12. `_normalize_reasoning_residue` silently clears residue for "thinking" prefixes

**File**: `C:\Source\Orket\orket\application\workflows\turn_contract_rules.py`, lines 346-364

**Behavioral lie**: When `consistency_tool_calls_only` is enabled, this function exempts any residue that starts with "thinking"-like prefixes by returning empty string. This means the consistency contract can be bypassed by any model output that starts with `<think` or `"# thinking"`. A model can emit arbitrary prose as long as it starts with a thinking marker.

**Severity**: MEDIUM

**Fix**: Only strip recognized thinking block formats (XML think tags), not arbitrary prefixes like "reasoning:" or "thought process:". The current implementation is too permissive.

---

### 13. `_is_tool_only_truncated_payload` false-positive heuristic

**File**: `C:\Source\Orket\orket\application\workflows\turn_contract_rules.py`, lines 367-390

**Behavioral lie**: This function uses a heuristic (unbalanced braces + tool markers + residue starting with `{` or `[`) to determine if residue is from a truncated tool-call payload. This can false-positive on any JSON-like output that happens to have unbalanced braces, silently clearing the residue and bypassing the consistency contract.

**Severity**: LOW

**Fix**: Add logging when this heuristic fires so truncation events are visible in observability artifacts.

---

### 14. `tool_result.get("ok", False)` called on potentially non-dict result

**File**: `C:\Source\Orket\orket\application\workflows\turn_tool_dispatcher.py`, line 419 and 426

**Behavioral lie**: At line 419, `result` could be a non-dict if the middleware `apply_after_tool` returns something unexpected (the type annotation says `Dict[str, Any]` but the middleware chain processes `MiddlewareOutcome.replacement` which is typed as `Any`). At line 426, `.get("ok", False)` would throw `AttributeError` on non-dict.

**Severity**: LOW

**Fix**: Add `isinstance(result, dict)` guard before calling `.get()` at lines 419 and 426, consistent with the guards used elsewhere in the same function.

---

### 15. `collect_protocol_preflight_violations` duplicates logic from `execute_tools`

**File**: `C:\Source\Orket\orket\application\workflows\turn_tool_dispatcher_protocol.py`, lines 25-119 vs `turn_tool_dispatcher.py`, lines 125-444

**Behavioral lie**: The preflight check and the actual execution loop duplicate gate validation, skill contract checks, approval checks, and compatibility translation. If one is updated and the other is not, they will diverge silently. The preflight returns violations immediately on first failure (early return) while the execution loop collects all violations. This means an input that passes preflight could still fail during execution with a different set of violations.

**Severity**: MEDIUM

**Fix**: Extract shared validation into a single function called by both paths. Or document explicitly that preflight is a strict superset check that validates all tools before any execution begins.

---

### 16. `_resolve_protocol_governed_enabled` env-var check inconsistency

**File**: `C:\Source\Orket\orket\application\workflows\orchestrator_ops.py`, lines 110-128

**Behavioral lie**: This function checks two env vars (`ORKET_PROTOCOL_GOVERNED_ENABLED` and `ORKET_PROTOCOL_GOVERNED`), then process rules, then user settings. But if the env var is explicitly set to "0"/"false", it returns `False` *before* checking process rules -- correctly. However, `_resolve_bool_flag` (line 424) does NOT have this same "explicit false" check for env. The two functions implement the same pattern with different behavior for explicit-false.

**Severity**: MEDIUM

**Fix**: Unify the resolution pattern. Use the same three-tier resolution logic (`_resolve_bool_flag` with explicit-false support) for all boolean settings.

---

### 17. `MessageBuilder.prepare_messages` is async but does no async work

**File**: `C:\Source\Orket\orket\application\workflows\turn_message_builder.py`, lines 20-194

**Behavioral lie**: The method is declared `async` but contains zero `await` calls. It builds messages purely synchronously. The caller `turn_executor_ops.py` line 56 awaits it, which works but adds unnecessary overhead from the coroutine machinery.

**Severity**: LOW

**Fix**: Remove the `async` keyword and change the caller to not await it, or document that it is async for future extensibility.

---

### 18. `_maybe_schedule_team_replan` silently swallows save failures

**File**: `C:\Source\Orket\orket\application\workflows\orchestrator_ops.py`, lines 1030-1036

**Behavioral lie**: When clearing the `replan_requested` flag on triggering issues, any save failure is caught by a broad except that includes `CardNotFound, ExecutionFailed, ValueError, TypeError, RuntimeError, OSError` and `continue`s silently. This means the replan flag may remain set, causing infinite replan loops that are only stopped by the `next_count > 3` guard.

**Severity**: MEDIUM

**Fix**: Log the save failure so it's visible in observability. The retry limit guards against infinite loops, but silent failures make debugging difficult.

---

### 19. `semaphore_wrapper` closure captures stale `issue_data` reference

**File**: `C:\Source\Orket\orket\application\workflows\orchestrator_ops.py`, lines 905-909

**Behavioral lie**: The `semaphore_wrapper` is defined inside a `while` loop. In the `asyncio.gather` call at line 912, the closures correctly capture each `issue_data` from the generator expression, but the function also references `self`, `epic`, `team`, `env`, `run_id`, etc. from the outer scope. These are stable across iterations, but if any upstream code mutated `team` (e.g., `_auto_inject_small_project_reviewer_seat` at line 641 mutates team.seats in-place), concurrent tasks would see the mutation.

**Severity**: LOW

**Fix**: Document that team/epic must not be mutated during parallel dispatch, or deep-copy them before the loop.

---

### 20. `_load_previous_prompt_structure` skips turn_index=1 but allows turn_index=0

**File**: `C:\Source\Orket\orket\application\workflows\turn_prompt_budget_artifacts.py`, lines 77-78

**Behavioral lie**: The guard `if turn_index <= 1: return None` means turn_index=0 returns None (correct, no previous), and turn_index=1 returns None (skips looking at turn 0). But turn_index=0 artifacts exist and could be compared. The comment is absent, so it's unclear if this is intentional or off-by-one.

**Severity**: LOW

**Fix**: Change to `if turn_index < 1: return None` to allow turn 1 to diff against turn 0.

---

### 21. `ResponseParser._parse_strict_envelope` rejects content != "" but docstring says "tool-call only"

**File**: `C:\Source\Orket\orket\application\workflows\turn_response_parser.py`, lines 148-149

**Behavioral lie**: Line 148 checks `if parsed.get("content") != "": raise ValueError(E_TOOL_MODE_CONTENT_NON_EMPTY)`. This means the protocol requires `"content": ""` in the envelope -- the content field must be present AND must be exactly empty string. This is not a "tool call only" check; it's a "content must be empty string" check. If the model omits the content key entirely, the earlier check at line 144 catches it. But the semantic is surprising: the envelope format requires a meaningless empty string field.

**Severity**: LOW

**Fix**: Document this requirement clearly. This is a design choice, not a bug, but it should be documented.

---

### 22. `coordinator_store` raises FastAPI HTTPException from a non-HTTP service layer

**File**: `C:\Source\Orket\orket\application\services\coordinator_store.py`, lines 7, 52, 106, etc.

**Behavioral lie**: A service-layer component (`InMemoryCoordinatorStore`) imports and raises `fastapi.HTTPException` directly. This couples a domain/application service to the HTTP transport layer. If this store is used outside of a FastAPI request context (e.g., tests, CLI, or background workers), the HTTPException semantics are wrong.

**Severity**: MEDIUM

**Fix**: Raise domain-specific exceptions (e.g., `CardNotFoundError`, `CardConflictError`) and let the API layer translate them to HTTPExceptions.

---

### 23. `_partition_prompt_messages` uses `str.startswith()` with a tuple of markers

**File**: `C:\Source\Orket\orket\application\workflows\prompt_budget_guard.py`, lines 152-183

**Behavioral lie**: Line 176 `content.startswith(protocol_markers)` passes a tuple to `startswith`, which is valid Python. However, the "Issue" message (line 33 of MessageBuilder) starts with `"Issue {issue.id}:"` which doesn't match any marker, so it falls into `task_messages`. The "Execution Context JSON:" message matches `tool_schema_markers`. This partitioning silently classifies all system messages AND protocol-contract messages into the same `protocol_messages` bucket, which means the protocol token budget conflates the system prompt with governance contracts.

**Severity**: LOW

**Fix**: Consider splitting the system message into its own bucket separate from protocol contract messages for more accurate token accounting.

---

### 24. `turn_executor.py` has duplicate explicit method declarations alongside `__getattr__` delegation

**File**: `C:\Source\Orket\orket\application\workflows\turn_executor.py`, lines 155-238

**Behavioral lie**: Methods like `_prepare_messages` (line 155), `_parse_response` (line 169), `_execute_tools` (line 183) are defined as both explicit methods AND in the `__getattr__` delegation table (lines 89-93). The explicit methods shadow the `__getattr__` entries, making the delegation entries for those names dead code. But both paths delegate to the same targets, so the behavior is correct -- it's just confusing maintenance-wise.

**Severity**: LOW

**Fix**: Remove the dead entries from the `__getattr__` delegation table, or remove the explicit methods and rely solely on `__getattr__`.

---

### 25. `InMemoryCommitStore` has no thread safety despite being used by `JsonFileCommitStore` which persists to disk

**File**: `C:\Source\Orket\orket\application\services\memory_commit_buffer.py`, lines 22-135

**Behavioral lie**: The `InMemoryCommitStore` has no locking mechanism. The `JsonFileCommitStore` subclass calls `self._persist()` after every mutation, but concurrent calls could interleave reads and writes, corrupting state. The recovery lease mechanism (lines 88-128) specifically handles concurrent workers, but the store itself is not concurrency-safe.

**Severity**: MEDIUM

**Fix**: Add a lock (`threading.Lock` for sync use, or `asyncio.Lock` if used in async context) to guard all mutations.

---

---

## SUMMARY

| Severity | Count |
|----------|-------|
| CRITICAL | 1 |
| HIGH | 5 |
| MEDIUM | 10 |
| LOW | 9 |
| **Total** | **25** |

**Top 5 findings by impact:**

1. **CRITICAL** - `RuntimeVerifier._run_command` runs config-provided commands with `shell=True` (security, runtime_verifier.py:250)
2. **HIGH** - `_resolve_bool_flag` does not handle explicit-false env vars, allowing org config to override (orchestrator_ops.py:424)
3. **HIGH** - `RuntimeVerifier._default_commands_for_profile` always returns `[]`, making the command pipeline a no-op (runtime_verifier.py:138)
4. **HIGH** - `coordinator_store.py` uses `threading.Lock` in a FastAPI async context (coordinator_store.py:14)
5. **HIGH** - `turn_executor_ops.py` broad except clause swallows programming bugs as operational failures (turn_executor_ops.py:379)


## BEHAVIORAL TRUTH AUDIT: Services, Extensions, Driver, and Utilities

### Finding 1: Swallowed errors in `_log_operator_metric`
- **File**: `C:\Source\Orket\orket\driver_support_conversation.py`, lines 162-167
- **Lie**: The method claims to log an operator metric, but silently swallows `RuntimeError`, `ValueError`, and `OSError` exceptions. If logging is broken, callers never know metrics are being lost.
- **Severity**: LOW
- **Fix**: At minimum, add a stderr fallback or track metric emission failures in a counter.

### Finding 2: Swallowed errors in `_conversation_model_reply`
- **File**: `C:\Source\Orket\orket\driver_support_conversation.py`, lines 106-122
- **Lie**: Catches 5 exception types (RuntimeError, ValueError, TypeError, KeyError, OSError) and returns `None`, making it impossible for callers to distinguish "model said nothing useful" from "model provider crashed". The conversation fallback path (`process_request` line 264) then returns a generic message as if the model had no opinion.
- **Severity**: MEDIUM
- **Fix**: Log the exception before returning None, or propagate a distinct sentinel so the caller can differentiate.

### Finding 3: `adopt_issue` in `_execute_structural_change` is a no-op
- **File**: `C:\Source\Orket\orket\driver_support_resources.py`, lines 85-88
- **Lie**: The `adopt_issue` action claims to move an issue to a target epic (`"Structural Reconciler: Moving issue {issue_id} to Epic {target_epic}."`) but does **nothing** -- it returns a string message without modifying any file, database, or state. It is a pure display-only no-op that deceives the user into thinking work was done.
- **Severity**: HIGH
- **Fix**: Either implement the actual move logic (read source epic, remove issue, append to target epic, write both) or raise `NotImplementedError("adopt_issue not yet implemented")`.

### Finding 4: `_team_template` creates an `integrity_guard` seat without a matching role definition
- **File**: `C:\Source\Orket\orket\driver_support_resources.py`, lines 149-170
- **Lie**: The template at line 169 creates a seat `"integrity_guard"` with `"roles": ["integrity_guard"]`, but the `roles` dict (lines 153-166) only defines `"coder"` and `"code_reviewer"`. The team JSON will reference a role that does not exist in the same file.
- **Severity**: MEDIUM
- **Fix**: Add an `"integrity_guard"` role definition to the `roles` dict, or remove the seat from the template.

### Finding 5: `build_team_agents` factory produces agents with all tools (no role scoping)
- **File**: `C:\Source\Orket\orket\agents\agent_factory.py`, lines 8-35
- **Lie**: The docstring says "Factory to instantiate agents for a specific Team" implying role-based tool scoping, but the `for role_name in seat.roles` loop body is entirely `pass` (line 26). Every agent gets the full `tool_map` (line 31), completely defeating the purpose of roles and seats. The factory returns agents with no role-based restrictions.
- **Severity**: HIGH
- **Fix**: Implement role-based tool filtering inside the loop, or document that this factory is a placeholder.

### Finding 6: `_VRAM_CACHE` is a mutable module-level dict used without any thread safety
- **File**: `C:\Source\Orket\orket\hardware.py`, lines 11-15 and 70-81
- **Lie**: `_cached_vram_metrics` reads and writes to `_VRAM_CACHE` with no lock. If `get_metrics_snapshot()` is called from multiple threads (e.g., via the FastAPI metrics endpoint), this is a data race. The caching mechanism silently provides stale or corrupted data.
- **Severity**: MEDIUM
- **Fix**: Add a `threading.Lock` around reads/writes to `_VRAM_CACHE`.

### Finding 7: `perform_first_run_onboarding` saves `"hardware_profile": "auto-detected"` but never actually detects hardware
- **File**: `C:\Source\Orket\orket\discovery.py`, lines 137-147
- **Lie**: Line 145 saves `{"setup_complete": True, "hardware_profile": "auto-detected"}` to user settings. The string `"auto-detected"` is a literal string value, not the result of any hardware detection. The actual hardware profile from `get_current_profile()` is never stored. The setting is meaningless.
- **Severity**: LOW
- **Fix**: Either call `get_current_profile()` and serialize its values, or remove the misleading `hardware_profile` key.

### Finding 8: `run_startup_reconciliation` swallows ImportError
- **File**: `C:\Source\Orket\orket\discovery.py`, lines 122-134
- **Lie**: Catches `ImportError` among other exceptions (line 131). If `orket.domain.reconciler.StructuralReconciler` does not exist (dead import, missing module), the function silently returns `"failed"` and logs it, but the caller `perform_startup_checks` treats this as a normal result. The system boots in an unreconciled state with no visible alarm.
- **Severity**: MEDIUM
- **Fix**: Either let ImportError propagate (it indicates a broken installation, not a runtime failure) or at minimum emit a WARNING-level log.

### Finding 9: `ExtensionManager.__getattr__` delegation obscures the real API
- **File**: `C:\Source\Orket\orket\extensions\manager.py`, lines 79-112
- **Lie**: The class claims to be a "Coordinator for extension catalog, installation, and workload execution" but delegates ~25 private methods via `__getattr__`. This means: (a) static analysis tools cannot discover the API, (b) any typo in a method name silently falls through to `AttributeError` at runtime, (c) the real interface is invisible. This is a known anti-pattern flagged in the project's own MEMORY.md under "Week 2" fix items.
- **Severity**: MEDIUM
- **Fix**: Replace `__getattr__` delegation with explicit property or method wrappers.

### Finding 10: `DefaultOrchestrationLoopPolicyNode.concurrency_limit` ignores the `organization` parameter
- **File**: `C:\Source\Orket\orket\decision_nodes\builtins.py`, lines 516-517
- **Lie**: The method accepts an `organization` parameter (matching the Protocol contract at `contracts.py` line 368) but ignores it, always returning 3. If an organization config specifies a different concurrency limit, it is silently overridden.
- **Severity**: MEDIUM
- **Fix**: Read concurrency from `organization.process_rules.get("concurrency_limit", 3)` or document the hardcoding.

### Finding 11: `DefaultOrchestrationLoopPolicyNode.max_iterations` ignores the `organization` parameter
- **File**: `C:\Source\Orket\orket\decision_nodes\builtins.py`, lines 519-520
- **Lie**: Same pattern as Finding 10. Always returns 20 regardless of organization config.
- **Severity**: MEDIUM
- **Fix**: Read from organization config or document the hardcoding.

### Finding 12: `DefaultOrchestrationLoopPolicyNode.context_window` ignores the `organization` parameter
- **File**: `C:\Source\Orket\orket\decision_nodes\builtins.py`, lines 522-527
- **Lie**: Accepts `organization` but reads only from the environment variable `ORKET_CONTEXT_WINDOW`. Organization-level config is ignored.
- **Severity**: LOW
- **Fix**: Check organization config first, fall back to env var.

### Finding 13: `_recover_truncated_tool_calls` only recovers `write_file` and `update_issue_status`
- **File**: `C:\Source\Orket\orket\application\services\tool_parser.py`, lines 42-101
- **Lie**: The method name and docstring suggest generic truncated tool call recovery, but lines 58-65 hardcode recovery for only `update_issue_status` and `write_file`. All other tool types are silently skipped (`continue` at line 65). A truncated `read_file` or `create_issue` call is lost without any diagnostic.
- **Severity**: LOW
- **Fix**: Add a fallback for unrecognized tool names that at least emits a diagnostic, or rename/document the limitation.

### Finding 14: `_should_handle_as_conversation` catches everything that is NOT structural
- **File**: `C:\Source\Orket\orket\driver_support_conversation.py`, lines 13-51
- **Lie**: The name implies it detects conversational intent, but the implementation (line 51) returns True for ANY message that does not contain one of the hardcoded structural markers. This means a message like "show me the memory usage of the database" is routed to conversation mode even though it could be an operational query. The function is really `_is_not_structural()`.
- **Severity**: LOW
- **Fix**: Rename to `_is_not_structural_request` for clarity, or add an intermediate "ambiguous" path.

### Finding 15: `OrketDriver.__init__` uses CWD-relative paths
- **File**: `C:\Source\Orket\orket\driver.py`, lines 37-38, 42, 56, 82
- **Lie**: Several paths are constructed relative to CWD: `Path(".")`, `Path("model/organization.json")`, `Path("model")`, `Path("workspace/default")`. If the process CWD changes (or the driver is instantiated from a different working directory), all file operations break silently. This is a known issue listed in MEMORY.md under "Week 3-4: Fix CWD-dependent paths across 8 files".
- **Severity**: HIGH
- **Fix**: Accept a `project_root: Path` parameter and resolve all paths relative to it.

### Finding 16: `ReproducibilityEnforcer.reliable_mode_enabled` defaults to True
- **File**: `C:\Source\Orket\orket\extensions\reproducibility.py`, lines 17-19
- **Lie**: The method reads `ORKET_RELIABLE_MODE` env var with a default of `"true"`. This means reliable mode is ON by default, and `validate_required_materials` / `validate_clean_git_if_required` are called for every extension workload unless explicitly disabled. This is a hidden restriction that could silently block extension execution if materials are missing -- and the default is not documented anywhere in the code.
- **Severity**: LOW
- **Fix**: Document the default behavior clearly, or change the default to `"false"` to match the principle of least surprise.

### Finding 17: `validate_required_materials` uses string prefix check instead of proper path containment
- **File**: `C:\Source\Orket\orket\extensions\reproducibility.py`, lines 21-33
- **Lie**: Line 28 uses `str(target).startswith(str(self.project_root))` for path containment. This is a classic path traversal bypass -- a path like `/project_root_evil/malicious` would pass if project_root is `/project_root`. Should use `target.relative_to(self.project_root)` in a try/except as done correctly elsewhere in the codebase.
- **Severity**: HIGH
- **Fix**: Replace line 28 with `target.relative_to(self.project_root)` inside a try/except ValueError.

### Finding 18: `_DefaultAsyncModelClient.close()` swallows all errors
- **File**: `C:\Source\Orket\orket\decision_nodes\builtins.py`, lines 670-673
- **Lie**: `close()` calls `self.provider.close()` if available, but if the close method raises, it will propagate. However, the `getattr(..., "close", None)` + `callable` pattern means if `close` is a property that raises, it silently returns None. More importantly, if the provider has no `close` method, this is a hidden no-op -- clients may think resources were released when nothing happened.
- **Severity**: LOW
- **Fix**: This is acceptable design for optional cleanup, but add a log when close is not available.

### Finding 19: `DecisionNodeRegistry` claims to be a "plugin registry" but always falls back to defaults
- **File**: `C:\Source\Orket\orket\decision_nodes\registry.py`, lines 38-293
- **Lie**: Every `resolve_*` method (e.g., line 162) uses `.get(name, self._*_nodes["default"])`. If a user registers a custom node under a name but the organization config has a typo in the node name, the registry silently falls back to the default without any warning. The "extensible" claim is undermined by silent fallback behavior.
- **Severity**: MEDIUM
- **Fix**: Log a warning when a configured node name is not found in the registry before falling back to default.

### Finding 20: `_normalize_conversation_model_output` silently extracts JSON response fields
- **File**: `C:\Source\Orket\orket\driver_support_conversation.py`, lines 132-145
- **Lie**: When the model returns JSON despite the system prompt explicitly saying "Do not produce JSON", this function silently extracts the `response` or `reasoning` field. This masks model misbehavior and means the conversation system prompt constraint (line 128: "Do not produce JSON") is not enforced.
- **Severity**: LOW
- **Fix**: Log a diagnostic when JSON is detected in conversation mode output.

### Finding 21: `raw_signature` in canon.py walks dict keys in insertion order, not sorted order
- **File**: `C:\Source\Orket\orket\kernel\v1\canon.py`, lines 67-71 and 118-125
- **Lie**: `_walk_raw` at line 121 iterates `value.items()` without sorting, but `raw_signature` is supposed to produce a deterministic digest. If the same dict is constructed with different insertion order, `raw_signature` returns a different hash. This contradicts the module's purpose (canonical comparison). The `canonicalize` function above (line 43) does sort keys, but `raw_signature` bypasses it.
- **Severity**: HIGH
- **Fix**: Change `_walk_raw` line 121 to `for key, item in sorted(value.items())`.

### Finding 22: `_is_non_local_target` has fragile heuristic for hostname detection
- **File**: `C:\Source\Orket\orket\kernel\v1\nervous_system_policy.py`, lines 36-62
- **Lie**: Line 56 says if `"."` is in the text and there are no slashes/backslashes, it's treated as a non-local target. This means a filename like `"config.json"` would be classified as non-local/exfiltration target, potentially blocking legitimate tool calls with approval requirements. The heuristic is too aggressive.
- **Severity**: MEDIUM
- **Fix**: Add file extension detection (e.g., if it ends with a known extension, treat as local path) or require a more specific pattern for hostname detection.

### Finding 23: `get_eos_sprint` calculates sprints using a fragile hardcoded base date
- **File**: `C:\Source\Orket\orket\utils.py`, lines 31-49
- **Lie**: The sprint calculation is pinned to `datetime(2026, 2, 2)` as "start of Q1 S6". For any date before this base date, `delta_weeks` is negative, producing nonsensical quarter/sprint values (e.g., Q0 S-3). No validation or clamping is performed.
- **Severity**: LOW
- **Fix**: Add a guard for dates before the base date.

### Finding 24: `snapshot_loader.load_from_pr` calls `files_resp.json()` twice
- **File**: `C:\Source\Orket\orket\application\review\snapshot_loader.py`, line 302
- **Lie**: `files_resp.json() if isinstance(files_resp.json(), list) else []` -- calls `.json()` twice. The first call is the isinstance check, the second is the assignment. This is wasteful (double parse) and could theoretically produce different results if the response object is not idempotent (unlikely with httpx, but still a code smell).
- **Severity**: LOW
- **Fix**: `payload = files_resp.json(); files_payload = payload if isinstance(payload, list) else []`

### Finding 25: `DefaultSandboxPolicyNode.generate_compose_file` raises on unsupported tech stack
- **File**: `C:\Source\Orket\orket\decision_nodes\builtins.py`, line 377
- **Lie**: For any tech stack not in the 3 hardcoded options, `ValueError` is raised. Since this is a "policy node" that is supposed to be pluggable, the default implementation's rigid behavior means adding a new tech stack requires replacing the entire node rather than extending it.
- **Severity**: LOW
- **Fix**: Return a minimal generic compose template as fallback, or document that custom stacks require a custom policy node.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0     |
| HIGH     | 5     |
| MEDIUM   | 8     |
| LOW      | 12    |
| **Total** | **25** |

**Top 5 most dangerous findings (address first):**

1. **Finding 3** (`adopt_issue` is a no-op) - Users think issues are moved; nothing happens.
2. **Finding 5** (`build_team_agents` gives all tools to every agent) - Role-based security is completely bypassed.
3. **Finding 15** (CWD-relative paths in OrketDriver) - Silent breakage if CWD differs.
4. **Finding 17** (String prefix path check in ReproducibilityEnforcer) - Path traversal bypass.
5. **Finding 21** (`raw_signature` uses unsorted dict keys) - Non-deterministic digests in a canonicalization module.


# BEHAVIORAL TRUTH AUDIT: Domain Layer & State Machine

## Findings

---

### 1. `system_set_status` bypasses the entire FSM with no guard enforcement

**File:** `C:\Source\Orket\orket\core\domain\workitem_transition.py`, lines 88-119

**Claim:** The `WorkItemTransitionService` is a "profile-agnostic transition boundary for lifecycle mutations" -- implying all transitions are governed.

**Reality:** The `system_set_status` action (line 88) skips the workflow profile's `validate_transition()` entirely, skips the `gate_boundary.pre_transition()` and `post_transition()` hooks, skips dependency checking, and returns `ok=True` for ANY valid `CardStatus` value as long as a non-empty `reason` string is provided. A caller can jump from `READY` straight to `DONE`, from `ARCHIVED` to `IN_PROGRESS`, or any other impossible transition. The FSM is completely bypassed.

**Severity:** CRITICAL -- production correctness bug. Any caller using `system_set_status` can put cards into illegal states, destroying FSM invariants.

**Fix:** Route `system_set_status` through `self.profile.validate_transition()` (or at minimum the `StateMachine.validate_transition()` directly), logging the override reason as an audit trail.

---

### 2. ToolGate hardcodes `CardType.ISSUE` for all state-change validations

**File:** `C:\Source\Orket\orket\core\policies\tool_gate.py`, line 251

**Claim:** ToolGate "validates tool calls against organizational policy before execution" for all card types.

**Reality:** `_validate_state_change()` always passes `CardType.ISSUE` to `StateMachine.validate_transition()`, regardless of the actual card type of the work item being transitioned. An Epic or Rock transition will be validated against the Issue transition table, which has completely different allowed paths. This means Epic/Rock transitions will either be wrongly rejected (if the transition is valid for Epics but not Issues) or wrongly permitted (if an Issue-only transition is attempted on a Rock).

**Severity:** HIGH -- wrong enforcement for non-Issue card types.

**Fix:** Extract the card type from `context` (e.g. `context.get("card_type", "issue")`) and pass the correct `CardType` enum value.

---

### 3. ToolGate skips FSM entirely when `org` is None or `bypass_governance` is set

**File:** `C:\Source\Orket\orket\core\policies\tool_gate.py`, line 247

**Claim:** ToolGate enforces state machine transitions on `update_issue_status`.

**Reality:** The guard is `if self.org and not getattr(self.org, 'bypass_governance', False)`. If no `OrganizationConfig` is provided (which is allowed -- the constructor accepts `Optional[OrganizationConfig]`), the entire state machine validation is silently skipped, and any status transition is permitted. There is also an undocumented `bypass_governance` flag that silently disables all FSM enforcement.

**Severity:** HIGH -- silent governance bypass when org config is absent.

**Fix:** Make FSM validation unconditional (remove the `self.org` guard). If `bypass_governance` must exist, log a warning.

---

### 4. `FailureReporter.generate_report()` accepts `transcript` parameter but never uses it

**File:** `C:\Source\Orket\orket\domain\failure_reporter.py`, line 40

**Claim:** Generates "high-fidelity reports" and accepts a `transcript: List[Any]` parameter.

**Reality:** The `transcript` parameter is accepted but never referenced in the function body. The generated report contains no transcript data. The `PolicyViolationReport` model has no transcript field. The "high-fidelity" report is just the violation string, a type classification, and a generic remedy suggestion.

**Severity:** MEDIUM -- semantic drift. Callers pass transcript data believing it will be included in the report, but it is silently discarded.

**Fix:** Either add a `transcript` field to `PolicyViolationReport` and populate it, or remove the parameter from the signature.

---

### 5. `FailureReporter.generate_report()` ignores the `attempted_action` field

**File:** `C:\Source\Orket\orket\domain\failure_reporter.py`, lines 60-67

**Claim:** `PolicyViolationReport` has an `attempted_action: Optional[Dict[str, Any]]` field (line 24).

**Reality:** The `generate_report()` method never populates `attempted_action`. It is always `None` in every generated report. The field exists on the model but is dead.

**Severity:** LOW -- dead field, misleading schema.

**Fix:** Accept and pass through an `attempted_action` dict, or remove the field from the model.

---

### 6. `BugFixPhase.is_expired()` compares timezone-aware and potentially naive datetimes

**File:** `C:\Source\Orket\orket\domain\bug_fix_phase.py`, line 83

**Claim:** Checks whether the current time has passed the scheduled end.

**Reality:** `datetime.now(UTC)` produces a timezone-aware datetime, but `datetime.fromisoformat(self.scheduled_end)` may produce a timezone-naive datetime if the stored ISO string lacks a `+00:00` suffix (Python's `isoformat()` with UTC produces `+00:00` so this is currently safe, but `fromisoformat` behavior changed between Python 3.10 and 3.11). More critically, the `_set_scheduled_end` model validator (line 57) does `datetime.fromisoformat(self.started_at)` which could fail or produce a naive datetime if `started_at` was populated externally.

**Severity:** MEDIUM -- fragile, depends on internal consistency of ISO string format.

**Fix:** Use `datetime.fromisoformat(self.scheduled_end).replace(tzinfo=UTC)` or normalize all stored timestamps.

---

### 7. `BugFixPhaseManager.start_phase()` double-sets `scheduled_end`, model validator ignored

**File:** `C:\Source\Orket\orket\domain\bug_fix_phase.py`, lines 108-116

**Claim:** The `@model_validator` on line 54 auto-computes `scheduled_end` from `started_at + initial_duration_days`.

**Reality:** `start_phase()` explicitly passes `scheduled_end=` in the constructor (line 115), which means the model validator on line 56 (`if self.scheduled_end is None`) is always False and never executes for phases created through the manager. The explicit `scheduled_end` is computed from `datetime.now(UTC)`, while `started_at` is also computed from `datetime.now(UTC)` via the `default_factory` -- but these are two separate `now()` calls that can differ by microseconds to milliseconds. The model validator exists but is dead code for the primary creation path.

**Severity:** LOW -- the explicit value is close enough, but the model validator is misleading dead code for the main path.

**Fix:** Remove the explicit `scheduled_end` from `start_phase()` and let the model validator compute it, or remove the model validator.

---

### 8. `PortAllocator.release()` never reclaims port numbers

**File:** `C:\Source\Orket\orket\domain\sandbox.py`, lines 148-150

**Claim:** "Release ports when sandbox is deleted."

**Reality:** `release()` removes the sandbox from `allocated_ports` dict, but `next_available_base` is monotonically increasing and never decremented. Released port slots are never reused. After 99 sandboxes, port allocations will exceed the documented ranges (e.g. API ports 8001-8099). The port "release" is a no-op for the purpose of reclamation.

**Severity:** MEDIUM -- port exhaustion after sustained use. The name "release" implies the port becomes available again, but it does not.

**Fix:** Maintain a free-list of released base numbers and pop from it before incrementing `next_available_base`.

---

### 9. `SandboxRegistry` references `PortAllocator` before it is defined

**File:** `C:\Source\Orket\orket\domain\sandbox.py`, line 91

**Claim:** `SandboxRegistry` has a `port_allocator` field.

**Reality:** `SandboxRegistry` is defined at line 85 with `port_allocator: PortAllocator = Field(default_factory=lambda: PortAllocator())`, but `PortAllocator` is defined at line 110. This works at runtime because the lambda defers evaluation, but it would fail if the field used a direct default `PortAllocator()` instead of `default_factory`. This is fragile and relies on Pydantic's lazy evaluation through lambda.

**Severity:** LOW -- works by accident, brittle to refactoring.

**Fix:** Move `PortAllocator` above `SandboxRegistry` in the file.

---

### 10. `StructuralReconciler` hardcodes `workspace=Path("workspace/default")` for all log events

**File:** `C:\Source\Orket\orket\domain\reconciler.py`, lines 21, 41, 59, 91, 125, 137

**Claim:** Logs events with workspace context.

**Reality:** Every `log_event()` call hardcodes `workspace=Path("workspace/default")` regardless of the actual workspace being used. The reconciler's `root_path` (which IS the workspace) is available but never passed to `log_event`. All reconciler log events will be written to a wrong/nonexistent workspace path.

**Severity:** HIGH -- logs are silently misdirected or lost.

**Fix:** Pass `self.root_path.parent` or accept a `workspace` parameter and use it consistently.

---

### 11. `StructuralReconciler.reconcile_all()` silently drops data on `or` fallback for issues

**File:** `C:\Source\Orket\orket\domain\reconciler.py`, line 55

**Claim:** Scans epics for linked issues.

**Reality:** Line 55: `for issue in data.get("issues", []) or data.get("stories", [])`. Due to Python's `or` semantics, if `data.get("issues", [])` returns an empty list `[]` (which is falsy), it falls through to `data.get("stories", [])`. This means if an epic has an empty `"issues": []` field AND a populated `"stories"` field, the stories will be scanned. But if `"issues"` has any content, `"stories"` is never checked. The intent appears to be to check BOTH, but the code only checks one or the other.

**Severity:** MEDIUM -- silent data loss if both `issues` and `stories` fields are present.

**Fix:** Use `for issue in (data.get("issues", []) + data.get("stories", []))`.

---

### 12. `EventStream` is defined but never imported or used anywhere

**File:** `C:\Source\Orket\orket\events.py`

**Claim:** "A session-wide event stream. The UI will subscribe to this."

**Reality:** No file in the codebase imports from `orket.events`. The `EventStream` class is completely dead code. There is no UI subscription mechanism.

**Severity:** MEDIUM -- dead code with a misleading docstring promising UI integration that doesn't exist.

**Fix:** Delete the file, or add a deprecation notice.

---

### 13. `ExecutionResult` is defined but never used outside its own file

**File:** `C:\Source\Orket\orket\domain\execution.py`, lines 25-32

**Claim:** Tracks execution session results.

**Reality:** `ExecutionResult` is not imported or used anywhere else in the codebase. `ExecutionTurn` IS used (by ToolGate), but `ExecutionResult` is dead code.

**Severity:** LOW -- dead code.

**Fix:** Remove `ExecutionResult` or mark as planned.

---

### 14. `CriticalPathEngine` shim delegates to core but `calculate_weight` has incompatible `visited` parameter

**File:** `C:\Source\Orket\orket\domain\critical_path.py`, line 20

**Claim:** "Delegates to core logic."

**Reality:** The shim's `calculate_weight` signature uses `visited=None` (default `None`), and the core's `calculate_weight` uses `visited: Set[str] | None = None`. These are compatible. However, the shim's `build_dependency_graph` signature declares `issues: List[Dict]` while the core accepts `List[Dict[str, Any]]`. The shim silently narrows the type. More importantly, the `get_priority_queue` shim passes `epic.issues` (a list of Pydantic models) but the core function uses `issue.get("id")` which only works on dicts, not Pydantic models. The core handles both with `isinstance(issue, dict)` checks, so this works but the shim's docstring "Maintains compatibility with EpicConfig" is misleading -- the core itself handles both formats.

**Severity:** LOW -- works correctly but the shim layer adds no value and is misleading.

**Fix:** Remove the shim; have callers import from core directly.

---

### 15. `_apply_limits` in verification runner silently fails on Windows

**File:** `C:\Source\Orket\orket\domain\verification_runner.py` (embedded in RUNNER_CODE string), lines 25-34

**Claim:** "Applies CPU and memory resource limits to the verification subprocess."

**Reality:** The `resource` module does not exist on Windows. The `except (ImportError, OSError, ValueError, AttributeError): pass` on line 33 silently swallows the `ImportError`, making the "security sandbox" a no-op on Windows. The subprocess runs with unlimited CPU and memory. Given this is a Windows-primary project (per the environment), resource limits NEVER apply.

**Severity:** HIGH -- security control is silently disabled on the primary deployment platform.

**Fix:** Document that resource limits require Linux/container mode. On Windows, force `ORKET_VERIFY_EXECUTION_MODE=container` or log a warning.

---

### 16. `StateMachine.validate_transition()` role parameter accepts `str` but callers can pass empty list

**File:** `C:\Source\Orket\orket\core\domain\state_machine.py`, lines 88-91

**Claim:** Enforces role-based guards (lines 103-118).

**Reality:** If `roles` is passed as an empty list `[]`, then `role_list` becomes `[]`, and the guard checks on lines 103 and 114 will always fail (since `"integrity_guard" not in []` is always True). This means an empty role list will be BLOCKED from transitioning to DONE or guard states. This is arguably correct behavior (no roles = no permissions), but the default parameter is `roles: Union[str, List[str]] = "system"` -- the default is the string `"system"`, which becomes `["system"]`. So the "normal" path without explicit roles uses `"system"` which also doesn't have `integrity_guard`. The only way to complete an Issue is with an explicit `integrity_guard` role, which is correct by design. No lie here.

**Severity:** N/A -- working as intended.

---

### 17. `WorkItemTransitionService` dependency check allows DONE with unresolved dependencies

**File:** `C:\Source\Orket\orket\core\domain\workitem_transition.py`, line 131

**Claim:** Checks for unresolved dependencies before allowing transitions.

**Reality:** The exclusion set is `{CardStatus.DONE, CardStatus.CANCELED, CardStatus.ARCHIVED, CardStatus.GUARD_APPROVED}`. This means a card can be transitioned to DONE even when it has unresolved dependencies. The comment/logic implies this is intentional (you can force-close things), but it undermines the purpose of dependency tracking. A card with unresolved dependencies can reach DONE, making the dependency system advisory-only with no enforcement.

**Severity:** MEDIUM -- semantic drift. Dependency checking claims to prevent transitions but explicitly allows the most important one (DONE).

**Fix:** If dependencies must block DONE, remove it from the exclusion set. If advisory-only is intentional, document it clearly.

---

### 18. `GuardReviewPayload.rationale` defaults to empty string, allowing empty reviews

**File:** `C:\Source\Orket\orket\core\domain\guard_review.py`, line 9

**Claim:** Represents a guard review payload with rationale.

**Reality:** `rationale: str = ""` allows an empty string, meaning a guard can approve or reject with no explanation. This contradicts the purpose of a review requiring rationale. Combined with `violations: List[str] = Field(default_factory=list)`, a completely empty payload is valid.

**Severity:** MEDIUM -- a guard review with empty rationale and no violations is semantically meaningless but structurally valid.

**Fix:** Add `Field(min_length=1)` to `rationale`, or validate that at least rationale OR violations is non-empty.

---

### 19. `SandboxVerifier` silently skips scenarios with no `endpoint` in input_data

**File:** `C:\Source\Orket\orket\domain\sandbox_verifier.py`, lines 25-26

**Claim:** "Runs verification scenarios against a live sandbox API."

**Reality:** If `scenario.input_data.get("endpoint")` is falsy, the scenario is silently `continue`d with no log, no fail marking, and not counted in either `passed` or `failed`. The `total_scenarios` in the result will include it, but `passed + failed` won't sum to `total_scenarios`. The scenario's status remains whatever its default is -- it's neither pass nor fail.

**Severity:** HIGH -- silent data loss. Misconfigured scenarios disappear from results without any indication.

**Fix:** Mark scenarios without endpoints as `fail` with an error message, or at minimum log a warning.

---

### 20. `board.py` hardcodes `Path("model")` as the config root

**File:** `C:\Source\Orket\orket\board.py`, line 42

**Claim:** Builds the board hierarchy.

**Reality:** `ConfigLoader(Path("model"), department)` uses a relative path, making the function CWD-dependent. If the process working directory is not the repo root, this will fail or load wrong data silently.

**Severity:** MEDIUM -- CWD-dependent behavior, a known systemic issue across 8+ files per the MEMORY.md notes.

**Fix:** Accept a `root_path` parameter or resolve against a configured workspace root.

---

### 21. `reconciler.py` uses `data.get("issues", []) or data.get("stories", [])` -- issues never added to `linked_issues` set

**File:** `C:\Source\Orket\orket\domain\reconciler.py`, line 56

**Claim:** Tracks linked issue identities using `id`, `name`, or `summary`.

**Reality:** `issue.get("id") or issue.get("name") or issue.get("summary")` -- if an issue has an `"id"` key that is an empty string `""`, it's falsy, so it falls through to `"name"`. If both `id` and `name` are empty strings, it uses `summary`. But more importantly, `linked_issues.add()` receives only ONE identifier per issue. If the orphan detection later checks by filename stem (which it does in `_adopt_issues` at line 123), and the filename stem doesn't match whichever of id/name/summary was stored, the issue will be incorrectly flagged as orphaned and adopted into unplanned_support.

**Severity:** MEDIUM -- identity mismatch between how issues are tracked (by one of id/name/summary) and how they're checked (by filename stem).

**Fix:** Track all three identifiers in the set, or normalize to a single canonical identifier.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 1     |
| HIGH     | 4     |
| MEDIUM   | 8     |
| LOW      | 4     |
| **Total**| **17** |

**Top 3 most dangerous findings:**

1. **CRITICAL (#1):** `system_set_status` bypasses the FSM entirely -- any card can be forced to any state, destroying all state machine guarantees.
2. **HIGH (#2):** ToolGate hardcodes `CardType.ISSUE`, so Epic/Rock transitions are validated against the wrong transition table.
3. **HIGH (#15):** Verification runner resource limits are a silent no-op on Windows (the primary platform), so verification subprocesses run unconstrained.
4. **HIGH (#19):** `SandboxVerifier` silently drops scenarios missing an endpoint -- `passed + failed != total_scenarios` with no warning.

# BEHAVIORAL TRUTH AUDIT: API Layer, Adapters, and Webhooks

## FINDINGS

### 1. CRITICAL: `clear_logs` endpoint always returns `{"ok": True}` even on failure
- **File**: `C:\Source\Orket\orket\interfaces\routers\system.py`, lines 47-62
- **Lie**: The endpoint catches `PermissionError`, `FileNotFoundError`, `OSError` and then falls through to `return {"ok": True}`. The caller believes logs were cleared when they were not.
- **Severity**: MEDIUM
- **Fix**: Return `{"ok": False, "warning": "clear_logs_skipped"}` in the except block, or at minimum include a `"skipped": True` field.

### 2. CRITICAL: `coordinator_api.py` uses a hardcoded module-level singleton store with demo data
- **File**: `C:\Source\Orket\orket\interfaces\coordinator_api.py`, lines 38-52
- **Lie**: `store = InMemoryCoordinatorStore()` is initialized at import time with a hardcoded demo card `{"task": "demo"}`. This singleton persists across the process and is shared by all callers. Any import of this module initializes a global store with test data in production.
- **Severity**: HIGH
- **Fix**: Remove the hardcoded `store.reset()` call. Accept store as a parameter or lazy-initialize without demo data.

### 3. CRITICAL: `auto_merge` silently succeeds when merge actually fails
- **File**: `C:\Source\Orket\orket\adapters\vcs\gitea_webhook_handlers.py`, lines 52-74
- **Lie**: `handle_pr_review` returns `{"status": "success", "message": "PR #{pr_number} approved and merged"}` BEFORE `auto_merge` is even awaited. Actually, `auto_merge` is called first but if the HTTP status is not 200 (lines 67-73), the failure is only logged -- the parent `handle_pr_review` has already committed to returning "success". The merge response is discarded; the caller is told the PR was merged when it may not have been.
- **Severity**: CRITICAL
- **Fix**: Check `auto_merge` return value and return an error status if the merge API call fails.

### 4. CRITICAL: `escalate_to_architect` and `auto_reject` swallow HTTP errors
- **File**: `C:\Source\Orket\orket\adapters\vcs\gitea_webhook_handlers.py`, lines 76-112
- **Lie**: Both methods call `self.handler.client.post(...)` but never check the response status. If the Gitea API rejects the comment or close request, the webhook handler reports success anyway.
- **Severity**: HIGH
- **Fix**: Check response status codes and raise or log with appropriate error propagation.

### 5. HIGH: `handle_pr_opened` creates an OrchestrationEngine per webhook event with no lifecycle management
- **File**: `C:\Source\Orket\orket\adapters\vcs\gitea_webhook_handlers.py`, lines 121-145
- **Lie**: Each PR opened event creates `OrchestrationEngine(self.handler.workspace)` (line 135), fires `engine.run_card()` as a fire-and-forget task (line 137), and never closes the engine. The engine object is garbage-collected while its task may still be running.
- **Severity**: HIGH
- **Fix**: Store the engine reference and ensure cleanup, or use the handler's shared engine.

### 6. HIGH: `GiteaHTTPClient` creates a new `httpx.AsyncClient` per request
- **File**: `C:\Source\Orket\orket\adapters\storage\gitea_http_client.py`, lines 42-43
- **Lie**: Despite `GiteaWebhookHandler.__init__` creating a shared `self.client` (in `gitea_webhook_handler.py:41`), the `GiteaHTTPClient.request_response` method creates a brand new `httpx.AsyncClient` for every request via `async with httpx.AsyncClient(...)`. No connection pooling occurs despite the class being designed as a "client."
- **Severity**: HIGH
- **Fix**: Accept and reuse a shared `httpx.AsyncClient` instance instead of creating one per call.

### 7. HIGH: `GiteaStateAdapter.__getattr__` delegation AND explicit methods coexist -- `__getattr__` is dead code
- **File**: `C:\Source\Orket\orket\adapters\storage\gitea_state_adapter.py`, lines 60-79 vs lines 85-195
- **Lie**: The class defines `__getattr__` to delegate methods like `_request_response`, `acquire_lease`, `transition_state`, etc. But ALL of these methods are also defined explicitly as regular methods on the class (lines 85-195). Since Python resolves regular methods before `__getattr__`, the entire `__getattr__` block is dead code that never executes. It claims to provide delegation but provides nothing.
- **Severity**: MEDIUM
- **Fix**: Delete the `__getattr__` method entirely.

### 8. HIGH: `sessions.py` `runs_root` parameter allows arbitrary path traversal
- **File**: `C:\Source\Orket\orket\interfaces\routers\sessions.py`, lines 243-264
- **Lie**: The `campaign_protocol_replays` endpoint accepts a `runs_root` query parameter and resolves it as `Path(str(runs_root)).resolve()` with no validation that it stays within the workspace. An attacker can pass `runs_root=/etc` or any absolute path.
- **Severity**: CRITICAL
- **Fix**: Validate `runs_root` is relative to workspace root using `is_relative_to()`, or remove the parameter.

### 9. HIGH: `sessions.py` `sqlite_db_path` parameter allows arbitrary file read
- **File**: `C:\Source\Orket\orket\interfaces\routers\sessions.py`, lines 267-286 and 289-309
- **Lie**: Both `compare_protocol_and_sqlite_run_ledgers` and `campaign_protocol_ledger_parity` accept a `sqlite_db_path` query parameter that is resolved as an arbitrary filesystem path with no boundary check. Any SQLite file on disk could be opened and queried.
- **Severity**: CRITICAL
- **Fix**: Validate `sqlite_db_path` is within the workspace boundary.

### 10. HIGH: `sessions.py` `begin_interaction_turn` uses unsanitized `req.workspace` for file path
- **File**: `C:\Source\Orket\orket\interfaces\routers\sessions.py`, line 105
- **Lie**: `workspace = Path(req.workspace).resolve()` is set from user input with no path validation. This workspace path is passed to `extension_manager.run_workload()`, potentially allowing workload execution in arbitrary directories.
- **Severity**: HIGH
- **Fix**: Validate workspace is within allowed boundaries.

### 11. MEDIUM: `AsyncSessionRepository._ensure_initialized` has a race condition
- **File**: `C:\Source\Orket\orket\adapters\storage\async_repositories.py`, lines 24-41
- **Lie**: `_ensure_initialized` checks `self._initialized` outside the lock (line 26-27), then inside `get_session` (line 44) calls it without acquiring the lock. Multiple concurrent calls to `get_session` can race through initialization.
- **Severity**: MEDIUM
- **Fix**: Use double-checked locking pattern consistently (lock, check, init) in all public methods, or use the lock in `_ensure_initialized`.

### 12. MEDIUM: `AsyncCardRepository.__getattr__` delegation hides method signatures
- **File**: `C:\Source\Orket\orket\adapters\storage\async_card_repository.py`, lines 35-52
- **Lie**: Methods like `archive_card`, `add_transaction`, etc. are accessible only through `__getattr__`. IDEs, type checkers, and documentation tools cannot discover these methods. The class `implements CardRepository` but half its interface is invisible.
- **Severity**: MEDIUM
- **Fix**: Replace `__getattr__` with explicit method definitions or properties.

### 13. MEDIUM: `nominate_card` is a hidden no-op
- **File**: `C:\Source\Orket\orket\adapters\tools\families\governance.py`, lines 17-22
- **Lie**: The method claims to "nominate" a card but only calls `log_event` and returns `{"ok": True, "message": "Nomination recorded."}`. No state is actually changed. No card is actually nominated anywhere. The caller believes a nomination occurred.
- **Severity**: MEDIUM
- **Fix**: Either implement actual nomination logic or rename to `log_nomination` and document that it only logs.

### 14. MEDIUM: `refinement_proposal` is a hidden no-op
- **File**: `C:\Source\Orket\orket\adapters\tools\families\governance.py`, lines 42-46
- **Lie**: Same pattern as `nominate_card`. Only logs, changes no state, returns success.
- **Severity**: MEDIUM
- **Fix**: Implement or rename to `log_refinement_proposal`.

### 15. MEDIUM: `clear_context` is a no-op
- **File**: `C:\Source\Orket\orket\adapters\llm\local_model_provider.py`, lines 391-393
- **Lie**: The method `clear_context` has a docstring-like comment claiming "Chat-completion calls are stateless unless explicit sessions are used" and then does nothing (`pass`). But when LMStudio session mode is "context" or "fixed", calls ARE stateful via session_id. The method should clear that session state but doesn't.
- **Severity**: MEDIUM
- **Fix**: When lmstudio_session_mode is "context" or "fixed", send an appropriate reset/clear to the backend, or document this limitation.

### 16. MEDIUM: `_ApiRuntimeNodeProxy.__setattr__` modifies the real node
- **File**: `C:\Source\Orket\orket\interfaces\api.py`, lines 62-68
- **Lie**: The proxy's `__setattr__` delegates to `setattr(_get_api_runtime_node(), name, value)`, which means any attribute set on the proxy mutates the real cached singleton via `@lru_cache`. This is dangerous and unintuitive -- assignments that look local have global side effects.
- **Severity**: LOW
- **Fix**: Override `__setattr__` to raise `AttributeError` or use `object.__setattr__` for internal state.

### 17. MEDIUM: `api.py` `_read_log_records` does blocking file I/O in async endpoints
- **File**: `C:\Source\Orket\orket\interfaces\api.py`, lines 1392-1406, called from lines 933 and 1312
- **Lie**: `_collect_replay_turns` (line 925) calls `_read_log_records` directly (line 933) which does blocking `path.read_text()`. This is called from `_derive_handoff_edges` (line 1233/1312) which is called inside `asyncio.to_thread` from `_build_execution_graph`. However, `_validate_session_path` (line 1307) raises `HTTPException` which should not be raised inside a thread.
- **Severity**: MEDIUM
- **Fix**: Move `_validate_session_path` outside the `asyncio.to_thread` call, or handle the path validation before entering the thread.

### 18. MEDIUM: `validate_signature` returns `False` when no secret is configured, but logs it as "Authentication disabled"
- **File**: `C:\Source\Orket\orket\webhook_server.py`, lines 136-154
- **Lie**: The log message says "Authentication disabled" but the function returns `False` (reject). The behavior is actually correct (reject-by-default) but the log message misleads operators into thinking auth is bypassed when it's actually enforced. The log level is "error" which is appropriate, but the message text is wrong.
- **Severity**: LOW
- **Fix**: Change log message to "GITEA_WEBHOOK_SECRET not set. All webhooks will be rejected."

### 19. MEDIUM: `event_broadcaster` swallows non-disconnect errors
- **File**: `C:\Source\Orket\orket\interfaces\api.py`, lines 1493-1501
- **Lie**: The except clause catches `RuntimeError` and `ValueError` alongside `WebSocketDisconnect`. For `RuntimeError`/`ValueError`, if `should_remove_websocket` returns `False`, the error is silently discarded. The websocket remains connected but the event is lost for that client.
- **Severity**: LOW
- **Fix**: Log non-disconnect errors before continuing.

### 20. MEDIUM: `GiteaHTTPClient.request_json` calls `self.adapter._request_response_with_retry` but `request_response` does NOT retry
- **File**: `C:\Source\Orket\orket\adapters\storage\gitea_http_client.py`, lines 74-92 vs 28-72
- **Lie**: `request_json` (line 83) calls `self.adapter._request_response_with_retry` for retries, but `request_response` (line 28) does a single attempt. The two methods have inconsistent retry behavior. The naming suggests `request_response` is the base and `request_response_with_retry` wraps it, which is correct, but the delegation path through `self.adapter._request_response_with_retry` is confusing because `adapter` has both methods via `__getattr__` and explicit definitions.
- **Severity**: LOW
- **Fix**: Clarify the call chain. Make `request_json` call `self.request_response_with_retry` directly instead of going through the adapter proxy.

### 21. HIGH: `create_requirements_issue` passes strings as label values instead of label IDs
- **File**: `C:\Source\Orket\orket\adapters\vcs\gitea_webhook_handlers.py`, lines 164-187
- **Lie**: Line 186 sends `"labels": ["requirements-review", "auto-rejected"]` to the Gitea API. Gitea's issue creation endpoint expects label IDs (integers), not label names. This will silently fail to apply labels (Gitea ignores invalid label fields) or return a 422, but the method never checks the response.
- **Severity**: MEDIUM
- **Fix**: Look up label IDs by name first, or check the response status code.

### 22. MEDIUM: `SandboxDeploymentHandler.trigger_sandbox_deployment` swallows all deployment errors
- **File**: `C:\Source\Orket\orket\adapters\vcs\gitea_webhook_handlers.py`, lines 196-225
- **Lie**: All exceptions from `create_sandbox` are caught (line 220), logged, and discarded. The caller (`handle_pr_merged`) returns `{"status": "success", "message": "sandbox deployment triggered"}` regardless of whether deployment actually succeeded.
- **Severity**: MEDIUM
- **Fix**: Propagate the error or return a status indicating deployment failure.

### 23. MEDIUM: `AsyncExecutorService.run_coroutine_blocking` creates a new event loop per call when already in an async context
- **File**: `C:\Source\Orket\orket\adapters\storage\async_executor_service.py`, lines 19-24
- **Lie**: When called from within a running event loop, it submits `asyncio.run(coro)` to a single-threaded `ThreadPoolExecutor`. Each call creates and destroys a full event loop. This is extremely slow and defeats the purpose of async IO. The `max_workers=1` means concurrent calls from async code will queue and serialize.
- **Severity**: HIGH
- **Fix**: Use `asyncio.run_coroutine_threadsafe` on the existing loop, or restructure callers to be properly async.

### 24. LOW: `FileSystemTools.read_file` catches `FileNotFoundError` twice
- **File**: `C:\Source\Orket\orket\adapters\tools\families\filesystem.py`, lines 39-42
- **Lie**: Line 39 catches `FileNotFoundError` specifically, then line 41 catches it again in the broad tuple. The first handler returns `{"ok": False, "error": "File not found"}` (generic message), shadowing the second handler that would return the actual exception string.
- **Severity**: LOW
- **Fix**: Remove the first `except FileNotFoundError` block since it's shadowed by the second.

### 25. LOW: `FileSystemTools.list_directory` has the same double-catch
- **File**: `C:\Source\Orket\orket\adapters\tools\families\filesystem.py`, lines 61-64
- **Lie**: Same pattern as finding 24.
- **Severity**: LOW
- **Fix**: Remove the first `except FileNotFoundError` block.

### 26. MEDIUM: `WebhookDatabase` opens and closes a new `aiosqlite` connection for EVERY operation
- **File**: `C:\Source\Orket\orket\adapters\vcs\webhook_db.py`, lines 103-144 (and all other methods)
- **Lie**: Despite the class docstring claiming it's a "Data Access Layer" with "non-blocking review cycle tracking," every single method opens a new connection via `async with aiosqlite.connect(self.db_path)`, does its work, and closes it. For `add_failure_reason` (line 146), it calls `get_pr_cycle_count` first (opening and closing connection #1), then opens connection #2 for the insert. No connection reuse.
- **Severity**: MEDIUM
- **Fix**: Maintain a persistent connection or connection pool.

### 27. MEDIUM: `api.py` `_collect_replay_turns` does blocking I/O from sync context
- **File**: `C:\Source\Orket\orket\interfaces\api.py`, line 933
- **Lie**: `_collect_replay_turns` calls `_read_log_records(path)` synchronously (blocking `path.read_text()`). It IS called via `asyncio.to_thread` from `list_run_replay_turns` (line 1022), which is correct. But `_derive_handoff_edges` (line 1305-1356) also calls `_read_log_records` and `_validate_session_path`. `_validate_session_path` raises `HTTPException`, which is a FastAPI-specific exception that should only be raised in the request context, not inside a thread worker.
- **Severity**: MEDIUM
- **Fix**: Validate session path before entering the thread.

### 28. LOW: `CardMigrations.ensure_initialized` has no lock
- **File**: `C:\Source\Orket\orket\adapters\storage\card_migrations.py`, lines 12-77
- **Lie**: The `initialized` flag is checked and set without any locking. However, this is called from `AsyncCardRepository._execute` which holds `self._lock`, so the race is mitigated at a higher level. Still, the class itself is not safe to use independently.
- **Severity**: LOW
- **Fix**: Document that `CardMigrations.ensure_initialized` must be called under an external lock, or add its own lock.

### 29. LOW: `api.py` `_EngineProxy.__getattr__` masks engine initialization errors
- **File**: `C:\Source\Orket\orket\interfaces\api.py`, lines 71-86
- **Lie**: `_get_engine()` lazily creates the engine. If the factory raises, the exception propagates but `self._engine` remains `None`. Next call retries. But `__getattr__` provides no typing info, so any `AttributeError` from the real engine is indistinguishable from "attribute doesn't exist on proxy."
- **Severity**: LOW
- **Fix**: Catch `AttributeError` in `__getattr__` and re-raise with context.

### 30. HIGH: `api.py` `halt_session` never validates session_id exists before halting
- **File**: `C:\Source\Orket\orket\interfaces\api.py`, lines 1107-1115
- **Lie**: The endpoint calls `engine.halt_session(session_id)` and returns `{"ok": True}` without checking if the session exists. If `halt_session` silently no-ops on unknown session IDs, the API returns success for non-existent sessions.
- **Severity**: MEDIUM
- **Fix**: Check session existence first, return 404 if not found.

---

## SUMMARY BY SEVERITY

| Severity | Count |
|----------|-------|
| CRITICAL | 3 |
| HIGH | 8 |
| MEDIUM | 15 |
| LOW | 6 |
| **Total** | **32** |

## TOP 5 MOST DANGEROUS FINDINGS

1. **Finding #8**: `runs_root` query parameter allows arbitrary path traversal (CRITICAL)
2. **Finding #9**: `sqlite_db_path` query parameter allows arbitrary file access (CRITICAL)
3. **Finding #3**: `auto_merge` reports success when merge fails (CRITICAL)
4. **Finding #6**: `GiteaHTTPClient` creates new HTTP client per request, no connection pooling (HIGH)
5. **Finding #10**: Unsanitized `req.workspace` allows workload execution in arbitrary directories (HIGH)