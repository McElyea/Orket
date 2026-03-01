# Resize Requirements: God Class Decomposition

Date: 2026-03-01
Type: structural decomposition / single responsibility enforcement
Baseline: v0.4.5, 1177/1189 tests passing (99.1%), hygiene metrics clean
Reference: docs/internal/ClaudeReview2.md (2026-02-28 audit)

## Objective

Decompose oversized classes into focused, single-responsibility components. No class should exceed 300 lines. No function should exceed 80 lines. Preserve all existing behavior and public API contracts.

## Targets

| Class | File | Current Lines | Target |
|---|---|---|---|
| TurnExecutor | application/workflows/turn_executor.py | 2323 | 5-7 classes, each <300 lines |
| Orchestrator | application/workflows/orchestrator.py | 1896 | 4-6 classes, each <300 lines |
| ExtensionManager | extensions/manager.py | 822 | 3-4 classes, each <300 lines |
| GiteaStateAdapter | adapters/storage/gitea_state_adapter.py | 512 | 2-3 classes, each <300 lines |
| GiteaWebhookHandler | adapters/vcs/gitea_webhook_handler.py | 386 | 3-4 classes, each <200 lines |
| AsyncCardRepository | adapters/storage/async_card_repository.py | 370 | 2 classes, each <200 lines |
| VerificationEngine | domain/verification.py | 295 | 2-3 classes, each <150 lines |
| OrchestrationEngine | orchestration/engine.py | 283 | 2 classes, each <200 lines |
| OrketDriver | driver.py | 231 | Clarify mixin boundaries |

## In Scope

1. Extracting cohesive method groups into dedicated classes.
2. Creating thin coordinator classes that compose the extracted classes.
3. Updating import sites (production and test) to reference new locations.
4. Re-exporting from original modules for backwards compatibility during transition.
5. Moving extracted classes to appropriate package locations.

## Out of Scope

1. Changing business logic or behavior.
2. Changing public API contracts (HTTP endpoints, CLI commands).
3. Adding new features.
4. Changing domain models (schema.py, state_machine.py).
5. Refactoring modules already at healthy size (<200 lines).
6. Async/sync migration (separate project in docs/projects/refactor/).

## Functional Requirements

### FR-1: TurnExecutor Decomposition (Priority 1)

The 2323-line TurnExecutor must be split into focused classes. The `execute_turn()` public method remains on TurnExecutor as the coordinator. See TURN-EXECUTOR-MAP.md for full method inventory.

Target classes:
- **TurnExecutor** (<250 lines) -- Coordinator. Owns `execute_turn()` and `_validate_preconditions()`. Composes all extracted classes.
- **MessageBuilder** (~210 lines) -- `_prepare_messages()` and path resolution helpers.
- **ResponseParser** (~120 lines) -- `_parse_response()`, `_non_json_residue()`, `_extract_guard_review_payload()`.
- **ToolDispatcher** (~300 lines) -- `_execute_tools()`, skill binding resolution, permission checks, runtime limit validation.
- **ContractValidator** (~600 lines) -- All `_meets_*()` contract methods, `_collect_contract_violations()`, scope diagnostics.
- **CorrectivePromptBuilder** (~120 lines) -- `_build_corrective_instruction()`, rule hints, failure messages.
- **TurnArtifactWriter** (~250 lines) -- Memory traces, checkpoints, tool replay/persist, artifact writing.

Constraints:
- `TurnResult` dataclass and exception classes remain in turn_executor.py.
- Only `orchestrator.py` imports `TurnExecutor` in production code (7 test files also import).
- Instance state is minimal (workspace, state, tool_gate, middleware) -- safe to pass as constructor args to extracted classes.

### FR-2: Orchestrator Decomposition (Priority 1)

The 1896-line Orchestrator must be split. The `execute_epic()` public method remains on Orchestrator as the coordinator. See ORCHESTRATOR-MAP.md for full method inventory.

Target classes:
- **Orchestrator** (<300 lines) -- Coordinator. Owns `execute_epic()`, `_trigger_sandbox()`, `_save_checkpoint()`. Composes all extracted classes.
- **OrchestratorConfig** (~200 lines) -- All 11 `_resolve_*()` methods, 5 feature flag methods, small project team policy (5 methods).
- **IssueTurnRunner** (~500 lines) -- `_execute_issue_turn()` and its helper methods (guard review, dispatch, pending gates).
- **TurnContextBuilder** (~230 lines) -- `_build_turn_context()`, `_build_dependency_context()`, `_history_context()`.
- **FailureHandler** (~120 lines) -- `_handle_failure()`, `_normalize_governance_violation_message()`, `_is_issue_idesign_enabled()`.
- **DependencyGraphManager** (~100 lines) -- `_propagate_dependency_blocks()`, `_maybe_schedule_team_replan()`.

Constraints:
- 17 instance variables set in `__init__`. Extracted classes receive relevant subset via constructor.
- 5 files import Orchestrator (1 production: decision_nodes/builtins.py, 4 tests).
- `_sandbox_locks`, `_sandbox_failed_rocks`, `_team_replan_counts` are mutable shared state that must stay on coordinator or be passed by reference.

### FR-3: ExtensionManager Decomposition (Priority 2)

The 822-line ExtensionManager must be split. See EXTENSION-MANAGER-MAP.md for full method inventory.

Target classes:
- **ExtensionManager** (<200 lines) -- Coordinator. Owns `run_workload()`, `install_from_repo()`, `list_extensions()`.
- **ExtensionCatalog** (~120 lines) -- Catalog loading/saving, entry point discovery, record serialization.
- **ManifestParser** (~120 lines) -- Manifest detection, legacy/SDK parsing, record building.
- **WorkloadExecutor** (~250 lines) -- Legacy and SDK workload execution, artifact management, provenance building.
- **ReproducibilityEnforcer** (~60 lines) -- Reliable mode, git validation, required materials.

Constraints:
- 18 files import ExtensionManager (2 production, 5 tests, 6 scripts, rest docs).
- Inner class `_WorkloadRegistry` stays as-is (already small).
- SDK dependency (`orket_extension_sdk`) only used in WorkloadExecutor and ManifestParser.

### FR-4: Secondary Class Decomposition (Priority 3)

**GiteaWebhookHandler** (386 lines):
- **GiteaWebhookDispatcher** (<100 lines) -- Routes events to handlers.
- **PRReviewHandler** (~150 lines) -- `_handle_pr_review()`, `_auto_merge()`, `_escalate_to_architect()`, `_auto_reject()`.
- **PRLifecycleHandler** (~100 lines) -- `_handle_pr_opened()`, `_handle_pr_merged()`, `_create_requirements_issue()`.
- **SandboxDeploymentHandler** (~80 lines) -- `_trigger_sandbox_deployment()`, `_add_sandbox_comment()`.

**GiteaStateAdapter** (512 lines):
- **GiteaHTTPClient** (~130 lines) -- `_request_response()`, `_request_json()`, retry logic, error classification.
- **GiteaLeaseManager** (~130 lines) -- `acquire_lease()`, `renew_lease()`.
- **GiteaStateTransitioner** (~120 lines) -- `transition_state()`, `release_or_fail()`, `_validate_transition()`.
- **GiteaStateAdapter** (<150 lines) -- Coordinator with `fetch_ready_cards()`, `append_event()`, queries.

**VerificationEngine** (295 lines):
- **FixtureVerifier** (~150 lines) -- `verify()` with subprocess runner.
- **SandboxVerifier** (~80 lines) -- `verify_sandbox()` with HTTP testing.
- **SubprocessRunner** -- Extract the 87-line `_RUNNER_CODE` string to a standalone Python module.

**AsyncCardRepository** (370 lines):
- Extract `_ensure_initialized()` (61 lines) to `CardMigrations` class.
- Extract lock+connect+query pattern to `_execute()` helper (reduces 20x duplication).

**OrchestrationEngine** (283 lines):
- Extract 7 kernel gateway passthrough methods to `KernelGatewayProxy`.
- Extract config validation to `OrchestrationConfig`.

## Quality Requirements

1. No regression in currently passing tests (1177 minimum).
2. All extracted classes must be importable from their original module path (re-exports for backwards compatibility).
3. No class in modified files exceeds 300 lines after decomposition.
4. No function in modified files exceeds 80 lines after decomposition.
5. Each extracted class must have at least one direct unit test.
6. No new global mutable state introduced.
7. No new dependencies between packages introduced.

## Verification Requirements

1. Run full test suite: `python -m pytest tests/ -v --tb=short`
2. Run architecture guards: `python -m pytest tests/platform/ -v`
3. Verify size constraints:
   ```
   python -c "import ast, os; [print(f'{p}:{n.lineno} {n.name} ({n.end_lineno-n.lineno}L)') for r,d,fs in os.walk('orket') for f in fs if f.endswith('.py') for p in [os.path.join(r,f)] for tree in [ast.parse(open(p).read())] for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and n.end_lineno-n.lineno>300]"
   ```
4. Verify import compatibility: `python -c "from orket.application.workflows.turn_executor import TurnExecutor, TurnResult"`
5. Verify no circular imports: `python -c "import orket.application.workflows.orchestrator"`

## Acceptance Criteria

1. TurnExecutor is under 250 lines; all 7 extracted classes exist and are tested.
2. Orchestrator is under 300 lines; all 6 extracted classes exist and are tested.
3. ExtensionManager is under 200 lines; all 4 extracted classes exist and are tested.
4. No class in the project exceeds 300 lines (verified by AST scan).
5. All 1177+ currently passing tests still pass.
6. Re-exports preserve backwards compatibility for all import sites.
7. ClaudeReview2 findings for "god classes over 100 lines" reduced by at least 10 entries.
