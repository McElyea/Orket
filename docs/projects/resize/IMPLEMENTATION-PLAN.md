# Resize Implementation Plan: God Class Decomposition

Date: 2026-03-01
Execution mode: incremental, one extraction per PR, lowest risk first
Reference maps: TURN-EXECUTOR-MAP.md, ORCHESTRATOR-MAP.md, EXTENSION-MANAGER-MAP.md

## Guiding Principles

1. **Extract, don't rewrite.** Move methods verbatim. Refactoring happens later.
2. **Re-export from original module.** No import site changes until all extractions complete.
3. **One group per PR.** Each extraction is independently mergeable and revertable.
4. **Tests must stay green.** Run full suite after each extraction.
5. **Mutable state stays on coordinator.** Extracted classes receive references, not copies.

---

## Phase 1: TurnExecutor Decomposition (Priority 1)

TurnExecutor is 2323 lines with 47 methods. Target: 7 extracted classes + slim coordinator.

### Step 1.1: Extract PathResolver
- **Source**: turn_executor.py lines 1442-1488 (6 methods, ~50 lines)
- **Target**: `orket/application/workflows/turn_path_resolver.py`
- **Class**: `PathResolver` -- static/classmethod utility, no instance state
- **Risk**: Low. Pure functions, no side effects.
- **Validation**: `python -m pytest tests/application/test_turn_executor_* -v`

### Step 1.2: Extract TurnArtifactWriter
- **Source**: turn_executor.py lines 2059-2392 (11 methods, ~250 lines)
- **Target**: `orket/application/workflows/turn_artifact_writer.py`
- **Class**: `TurnArtifactWriter(workspace: Path)` -- file I/O, hashing, replay cache
- **Risk**: Low. Self-contained writes, no external deps.
- **Validation**: `python -m pytest tests/application/test_memory_trace_emission.py -v`

### Step 1.3: Extract ResponseParser
- **Source**: turn_executor.py lines 780-852, 1979-2057 (3 methods, ~120 lines)
- **Target**: `orket/application/workflows/turn_response_parser.py`
- **Class**: `ResponseParser` -- stateless parsing
- **Note**: `_non_json_residue()` is also called by ContractValidator. Make it a public method.
- **Risk**: Low. Pure parsing functions.
- **Validation**: `python -m pytest tests/application/test_turn_executor_* -v`

### Step 1.4: Extract ContractValidator
- **Source**: turn_executor.py lines 1167-1977 (11 methods, ~600 lines)
- **Target**: `orket/application/workflows/turn_contract_validator.py`
- **Class**: `ContractValidator` -- depends on PathResolver and ResponseParser
- **Constructor**: `ContractValidator(path_resolver: PathResolver, response_parser: ResponseParser)`
- **Risk**: Medium. Largest extraction. Many internal method calls.
- **Validation**: `python -m pytest tests/application/test_turn_executor_* -v`

### Step 1.5: Extract CorrectivePromptBuilder
- **Source**: turn_executor.py lines 1253-1440 (4 methods, ~120 lines)
- **Target**: `orket/application/workflows/turn_corrective_prompt.py`
- **Class**: `CorrectivePromptBuilder` -- depends on PathResolver
- **Risk**: Low. Isolated string building.
- **Validation**: `python -m pytest tests/application/test_turn_executor_* -v`

### Step 1.6: Extract ToolDispatcher
- **Source**: turn_executor.py lines 854-1165 (6 methods, ~300 lines)
- **Target**: `orket/application/workflows/turn_tool_dispatcher.py`
- **Class**: `ToolDispatcher(tool_gate: ToolGate, middleware: TurnLifecycleInterceptors, artifact_writer: TurnArtifactWriter)`
- **Risk**: Medium. Uses tool_gate, middleware, replay cache.
- **Validation**: `python -m pytest tests/application/test_turn_executor_* -v`

### Step 1.7: Extract MessageBuilder
- **Source**: turn_executor.py lines 535-778 (2 methods, ~210 lines)
- **Target**: `orkat/application/workflows/turn_message_builder.py`
- **Class**: `MessageBuilder` -- depends on PathResolver
- **Risk**: Low. Prompt construction.
- **Validation**: `python -m pytest tests/application/test_turn_executor_context.py -v`

### Step 1.8: Slim TurnExecutor Coordinator
- Reduce turn_executor.py to: `__init__`, `execute_turn()`, `_validate_preconditions()`, state transition helpers, TurnResult, exceptions.
- Compose all extracted classes in `__init__`.
- Add re-exports: `from .turn_path_resolver import PathResolver` etc.
- **Target size**: <250 lines.
- **Validation**: Full test suite.

---

## Phase 2: Orchestrator Decomposition (Priority 1)

Orchestrator is 1896 lines with 37 methods. Target: 5 extracted classes + slim coordinator.

### Step 2.1: Extract OrchestratorConfig
- **Source**: orchestrator.py -- 11 `_resolve_*()` methods + 5 `_is_*_disabled()` methods + 5 small project policy methods (21 methods, ~200 lines)
- **Target**: `orket/application/workflows/orchestrator_config.py`
- **Class**: `OrchestratorConfig(org, loader)` -- pure lookups, no async
- **Risk**: Low. All methods are simple env/config lookups.
- **Validation**: `python -m pytest tests/application/test_orchestrator_* tests/application/test_state_backend_mode.py -v`

### Step 2.2: Extract TurnContextBuilder
- **Source**: orchestrator.py -- `_build_turn_context()`, `_build_dependency_context()`, `_history_context()` (3 methods, ~230 lines)
- **Target**: `orket/application/workflows/turn_context_builder.py`
- **Class**: `TurnContextBuilder(config: OrchestratorConfig, async_cards, loader, workspace)`
- **Risk**: Low. Read-only context assembly.
- **Validation**: `python -m pytest tests/application/test_orchestrator_context_window.py -v`

### Step 2.3: Extract FailureHandler
- **Source**: orchestrator.py -- `_handle_failure()`, `_is_issue_idesign_enabled()`, `_normalize_governance_violation_message()` (3 methods, ~120 lines)
- **Target**: `orket/application/workflows/failure_handler.py`
- **Class**: `FailureHandler(evaluator_node, workspace)`
- **Risk**: Low. Isolated failure logic.
- **Validation**: `python -m pytest tests/application/test_orchestrator_epic.py -v`

### Step 2.4: Extract DependencyGraphManager
- **Source**: orchestrator.py -- `_propagate_dependency_blocks()`, `_maybe_schedule_team_replan()` (2 methods, ~100 lines)
- **Target**: `orket/application/workflows/dependency_graph_manager.py`
- **Class**: `DependencyGraphManager(async_cards, planner_node)`
- **Risk**: Low. DAG propagation logic.
- **Validation**: `python -m pytest tests/application/test_orchestrator_epic.py -v`

### Step 2.5: Extract IssueTurnRunner
- **Source**: orchestrator.py -- `_execute_issue_turn()` and helpers (guard, dispatch, gates, transitions) (~500 lines)
- **Target**: `orket/application/workflows/issue_turn_runner.py`
- **Class**: `IssueTurnRunner(config, context_builder, failure_handler, ...)`
- **Risk**: High. Largest extraction, many dependencies. Most complex method (481 lines).
- **Sub-task**: Break `_execute_issue_turn()` into smaller methods during extraction.
- **Validation**: Full test suite.

### Step 2.6: Slim Orchestrator Coordinator
- Reduce orchestrator.py to: `__init__`, `execute_epic()`, `verify_issue()`, `_trigger_sandbox()`, `_save_checkpoint()`.
- Compose all extracted classes in `__init__`.
- Add re-exports.
- **Target size**: <300 lines.
- **Validation**: Full test suite.

---

## Phase 3: ExtensionManager Decomposition (Priority 2)

ExtensionManager is 822 lines with 31 methods. Target: 4 extracted classes + slim coordinator.

### Step 3.1: Extract ExtensionCatalog
- **Source**: manager.py -- catalog load/save, entry point discovery, record serialization (6 methods, ~120 lines)
- **Target**: `orket/extensions/catalog.py`
- **Class**: `ExtensionCatalog(catalog_path: Path)`
- **Risk**: Low. Pure I/O.
- **Validation**: `python -m pytest tests/runtime/test_extension_manager.py -v`

### Step 3.2: Extract ManifestParser
- **Source**: manager.py -- manifest detection, legacy/SDK parsing (4 methods, ~120 lines)
- **Target**: `orket/extensions/manifest_parser.py`
- **Class**: `ManifestParser` -- stateless parsing
- **Risk**: Low. Pure parsing.
- **Validation**: `python -m pytest tests/runtime/test_extension_manager.py -v`

### Step 3.3: Extract ReproducibilityEnforcer
- **Source**: manager.py -- reliable mode, git validation, materials check (3 methods, ~60 lines)
- **Target**: `orket/extensions/reproducibility.py`
- **Class**: `ReproducibilityEnforcer(project_root: Path)`
- **Risk**: Low. Isolated validation.
- **Validation**: `python -m pytest tests/runtime/test_extension_manager.py -v`

### Step 3.4: Extract WorkloadExecutor
- **Source**: manager.py -- execution, loading, artifacts, provenance, validators (14 methods, ~300 lines)
- **Target**: `orket/extensions/workload_executor.py`
- **Class**: `WorkloadExecutor(project_root, install_root, reproducibility: ReproducibilityEnforcer)`
- **Risk**: Medium. Largest piece, SDK dependency.
- **Validation**: `python -m pytest tests/runtime/test_extension_manager.py tests/application/test_run_meta_breaker_workload.py -v`

### Step 3.5: Slim ExtensionManager Coordinator
- Reduce manager.py to: `__init__`, `list_extensions()`, `install_from_repo()`, `run_workload()`, `resolve_workload()`.
- Compose all extracted classes.
- Add re-exports.
- **Target size**: <200 lines.
- **Validation**: Full test suite.

---

## Phase 4: Secondary Decompositions (Priority 3)

These are smaller and can be done independently.

### Step 4.1: GiteaWebhookHandler -> Dispatcher + Handlers
- **Source**: adapters/vcs/gitea_webhook_handler.py (386 lines)
- **Targets**:
  - `gitea_webhook_handler.py` -- GiteaWebhookDispatcher (<100 lines)
  - `handlers/pr_review_handler.py` -- PRReviewHandler (~150 lines)
  - `handlers/pr_lifecycle_handler.py` -- PRLifecycleHandler (~100 lines)
  - `handlers/sandbox_handler.py` -- SandboxDeploymentHandler (~80 lines)
- **Risk**: Medium. Shared httpx.AsyncClient lifecycle.

### Step 4.2: GiteaStateAdapter -> Client + Transitioner + LeaseManager
- **Source**: adapters/storage/gitea_state_adapter.py (512 lines)
- **Targets**:
  - `gitea_http_client.py` -- GiteaHTTPClient (~130 lines)
  - `gitea_lease_manager.py` -- GiteaLeaseManager (~130 lines)
  - `gitea_state_transitioner.py` -- GiteaStateTransitioner (~120 lines)
  - `gitea_state_adapter.py` -- GiteaStateAdapter coordinator (<150 lines)
- **Risk**: Medium. ETag CAS and retry logic tightly coupled.

### Step 4.3: VerificationEngine -> FixtureVerifier + SandboxVerifier
- **Source**: domain/verification.py (295 lines)
- **Targets**:
  - `verification.py` -- VerificationEngine coordinator (<80 lines)
  - `fixture_verifier.py` -- FixtureVerifier (~150 lines)
  - `sandbox_verifier.py` -- SandboxVerifier (~80 lines)
  - `verification_runner.py` -- Extract _RUNNER_CODE to importable module
- **Risk**: Low. Two verification modes share no code.

### Step 4.4: AsyncCardRepository -> Extract Migrations + Query Helper
- **Source**: adapters/storage/async_card_repository.py (370 lines)
- **Targets**:
  - Extract `_ensure_initialized()` (61 lines) to `card_migrations.py`
  - Extract `_execute(query, params)` helper to reduce 20x lock+connect duplication
  - **Does NOT split into multiple repository classes** -- CRUD stays together.
- **Risk**: Low. Internal refactoring only.

### Step 4.5: OrchestrationEngine -> Extract KernelGatewayProxy
- **Source**: orchestration/engine.py (283 lines)
- **Targets**:
  - Extract 7 `kernel_*()` passthrough methods to `kernel_gateway_proxy.py`
  - Extract config validation to `orchestration_config.py`
  - Slim engine to <150 lines.
- **Risk**: Low. Pure delegation.

---

## Work Slicing Summary

| PR | Step | Target | Risk | New Classes |
|---|---|---|---|---|
| A | 1.1-1.3 | TurnExecutor low-risk extractions | Low | PathResolver, TurnArtifactWriter, ResponseParser |
| B | 1.4-1.5 | TurnExecutor medium extractions | Medium | ContractValidator, CorrectivePromptBuilder |
| C | 1.6-1.8 | TurnExecutor completion | Medium | ToolDispatcher, MessageBuilder, slim coordinator |
| D | 2.1-2.2 | Orchestrator config + context | Low | OrchestratorConfig, TurnContextBuilder |
| E | 2.3-2.4 | Orchestrator failure + DAG | Low | FailureHandler, DependencyGraphManager |
| F | 2.5-2.6 | Orchestrator completion | High | IssueTurnRunner, slim coordinator |
| G | 3.1-3.5 | ExtensionManager full decomposition | Medium | 4 classes + slim coordinator |
| H | 4.1 | GiteaWebhookHandler | Medium | 3 handler classes + dispatcher |
| I | 4.2 | GiteaStateAdapter | Medium | 3 classes + coordinator |
| J | 4.3-4.5 | Verification + CardRepo + Engine | Low | 3 classes + helpers |

## Rollback Strategy

1. Each PR is independently revertable via `git revert`.
2. Re-exports in original modules mean no downstream breakage during transition.
3. If any extraction destabilizes tests, revert that PR only. Other PRs remain independent.
4. Phase 1 (TurnExecutor) and Phase 2 (Orchestrator) are independent of each other. Either can proceed without the other.
5. Phase 4 is independent of Phases 1-3.

## Verification After Each PR

```bash
# Quick check (per-PR)
python -m pytest tests/application/ -v --tb=short

# Full check (after each phase)
python -m pytest tests/ -v --tb=short

# Size constraint check (after all phases)
python -c "
import ast, os
for r,d,fs in os.walk('orket'):
    for f in fs:
        if f.endswith('.py'):
            p = os.path.join(r,f)
            tree = ast.parse(open(p).read())
            for n in ast.walk(tree):
                if isinstance(n, ast.ClassDef) and n.end_lineno - n.lineno > 300:
                    print(f'FAIL: {p}:{n.lineno} {n.name} ({n.end_lineno-n.lineno}L)')
"
```

## Success Metrics

1. TurnExecutor: 2323 lines -> 7 files, largest <300 lines.
2. Orchestrator: 1896 lines -> 6 files, largest <300 lines.
3. ExtensionManager: 822 lines -> 5 files, largest <300 lines.
4. Secondary targets: all under 200 lines.
5. Total new classes: ~25.
6. Test suite: 1177+ passing (no regressions).
7. ClaudeReview2 "god classes over 100 lines" list reduced by 10+ entries.
