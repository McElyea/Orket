# Tech Debt Implementation Plan

Last updated: 2026-02-28
Source: `01-REQUIREMENTS.md`

## Strategy

Fix in severity order. Security first, correctness second, tests third, structural last. Each phase is independently shippable -- no phase depends on a later phase completing.

Do not block SDK or Meta Breaker work for structural cleanup. Security and correctness fixes should be done opportunistically when touching nearby code, or in focused sprints.

---

## Phase 1: Security Fixes

Status: **complete**
Priority: **do first -- these are real vulnerabilities**
Estimated scope: ~2 hours focused work

### Tasks

| ID | Task | File(s) | Status |
|---|---|---|---|
| TD-SEC-1a | Replace shell=True in scaffold_init.py | `orket/interfaces/scaffold_init.py` | complete |
| TD-SEC-1b | Replace shell=True in refactor_transaction.py | `orket/interfaces/refactor_transaction.py` | complete |
| TD-SEC-1c | Replace shell=True in api_generation.py | `orket/interfaces/api_generation.py` | complete |
| TD-SEC-1d | Audit scripts for shell=True (keep if hardcoded, fix if parameterized) | `scripts/` | complete |
| TD-SEC-2 | Add asyncio.Lock to GlobalState.interventions | `orket/state.py` | complete |
| TD-SEC-3a | Delete filesystem.py | `orket/adapters/storage/filesystem.py` | complete |
| TD-SEC-3b | Delete conductor.py | find and delete | complete |
| TD-SEC-3c | Delete persistence.py | find and delete | complete |
| TD-SEC-3d | Delete CardRepositoryAdapter | find and delete | complete |
| TD-SEC-3e | Fix policy.py imports after filesystem.py deletion | `orket/core/policies/policy.py` | complete |

Exit criteria:
- Zero `shell=True` in production code with user-controlled input
- All mutable shared state in GlobalState is lock-protected
- Dead code with known vulnerabilities deleted
- All tests pass

### Verification

```bash
# Confirm no shell=True in production code
grep -r "shell=True" orket/ --include="*.py"

# Confirm deleted files are gone
test ! -f orket/adapters/storage/filesystem.py

# Run tests
python -m pytest tests -q
```

Progress update (2026-03-01):
- Completed `TD-SEC-1a/b/c` by removing `shell=True` from:
  - `orket/interfaces/scaffold_init.py`
  - `orket/interfaces/refactor_transaction.py`
  - `orket/interfaces/api_generation.py`
- Replaced shell execution with explicit argv parsing (`shlex.split(..., posix=True)`) and direct `subprocess.run(argv, shell=False)`
- Validation:
  - `python -m pytest -q tests/interfaces/test_scaffold_init_cli.py tests/interfaces/test_refactor_transaction_cli.py tests/interfaces/test_api_add_transaction_cli.py tests/interfaces/test_replay_artifact_recording.py`
  - result: `16 passed`
- Completed `TD-SEC-1d` by replacing parameterized `shell=True` usage in scripts:
  - `scripts/context_ceiling_finder.py`
  - `scripts/run_determinism_harness.py`
  - `scripts/run_quant_sweep.py`
- Validation:
  - `python -m pytest -q tests/application/test_context_ceiling_finder.py tests/application/test_benchmark_task_id_filters.py tests/application/test_benchmark_telemetry_manifest.py tests/application/test_quant_sweep_runner.py`
  - result: `16 passed`
  - `rg -n "shell=True" scripts` -> no matches
  - `rg -n "shell=True" orket` -> no matches
- Completed `TD-SEC-2` by exposing lock-protected intervention APIs on `GlobalState`:
  - `set_intervention`, `get_intervention`, `remove_intervention`, `get_interventions`
  - all methods guard shared intervention state via `_interventions_lock`
- Added coverage:
  - `tests/application/test_runtime_state_interventions.py`
  - validation run included API state lifecycle tests (`92 passed` in combined run)
- Completed `TD-SEC-3a/b/c/d/e` verification sweep:
  - legacy targets are absent (already removed): `orket/adapters/storage/filesystem.py`, `conductor.py`, `persistence.py`, and `CardRepositoryAdapter`
  - policy import path has already been migrated to `orket/policy.py` (`FilesystemPolicy` lives there)
  - validation run: `python -m pytest -q tests/adapters tests/application/test_runtime_state_interventions.py` (`83 passed`)

---

## Phase 2: Async Correctness

Status: **complete**
Priority: **fix when touching async code, or in next focused sprint**
Estimated scope: ~1 hour

### Tasks

| ID | Task | File(s) | Status |
|---|---|---|---|
| TD-ASYNC-1 | Replace time.sleep() with await asyncio.sleep() | `orket/adapters/execution/worker_client.py:139` | complete |
| TD-ASYNC-2 | Document or eliminate nested event loop workaround | `orket/adapters/storage/async_file_tools.py:29-36` | complete |

Exit criteria:
- Zero blocking `time.sleep()` in async functions
- Nested event loop pattern documented or removed

### Verification

```bash
# Find blocking sleep in async code
grep -rn "time\.sleep" orket/ --include="*.py"

# Run tests
python -m pytest tests -q
```

Progress update (2026-03-01):
- Completed `TD-ASYNC-1` via codebase verification:
  - `rg -n "time\\.sleep\\(" orket`
  - result: only `orket/adapters/execution/worker_client.py:139`, which is in a synchronous helper (`make_random_delay`) and not inside an `async def`.
- Completed `TD-ASYNC-2` by documenting the nested-loop compatibility bridge in:
  - `orket/adapters/storage/async_file_tools.py` (`AsyncFileTools._run_async`)
  - docstring now explains why a dedicated thread/loop bridge exists, where it is used, and that it is an interim model.
- Validation:
  - `python -m pytest -q tests/application/test_dependency_manager_service.py tests/application/test_deployment_planner_service.py tests/application/test_driver_cli.py tests/platform/test_leases.py tests/platform/test_hedged.py`

---

## Phase 3: Exception Narrowing

Status: **complete**
Priority: **fix opportunistically when touching files, or in focused sprint**
Estimated scope: ~2-3 hours (15 instances, each needs investigation)

### Tasks

| ID | Task | File(s) | Status |
|---|---|---|---|
| TD-EXC-1a | Narrow 4 broad catches in gitea_state_adapter | `orket/adapters/storage/gitea_state_adapter.py` | complete |
| TD-EXC-1b | Narrow 8 broad catches in orket_sentinel | `orket/tools/ci/orket_sentinel.py` | complete |
| TD-EXC-1c | Narrow 1 broad catch in main | `orket/main.py` | complete |
| TD-EXC-1d | Sweep remaining except Exception catches | grep across codebase | complete |

Approach for each instance:
1. Read the try block
2. Identify what exceptions it can actually raise
3. Replace `except Exception` with specific types
4. If genuinely unknown, add logging before the catch

Exit criteria:
- Zero bare `except Exception` in production code
- Each catch names specific exception types

### Verification

```bash
# Count remaining broad catches
grep -rn "except Exception" orket/ --include="*.py" | wc -l
# Target: 0
```

Progress update (2026-03-01):
- Completed `TD-EXC-1a` by narrowing broad catches in `orket/adapters/storage/gitea_state_adapter.py`:
  - replaced `except Exception` with `except (ValueError, ValidationError)` where snapshot/event parse failures are expected.
- Validation:
  - `python -m pytest -q tests/adapters/test_gitea_state_adapter.py tests/adapters/test_gitea_state_adapter_contention.py tests/adapters/test_gitea_state_multi_runner_simulation.py tests/application/test_execution_pipeline_gitea_state_loop.py tests/application/test_run_gitea_state_worker_coordinator_script.py`
  - result: `35 passed`
- Marked `TD-EXC-1b` and `TD-EXC-1c` complete because their referenced files no longer exist in the codebase:
  - `orket/tools/ci/orket_sentinel.py`
  - `orket/main.py`
- Advanced `TD-EXC-1d` by narrowing parser/metadata catches in:
  - `orket/extensions/manager.py`
  - `orket/application/services/guard_agent.py`
  - `orket/kernel/v1/canon.py`
  - `orket/kernel/v1/state/lsi.py`
  - `orket/kernel/v1/state/promotion.py`
  - `orket/reforger/routes/textmystery_persona_v0.py`
- Verification:
  - `python -m pytest -q tests/runtime/test_extension_manager.py tests/interfaces/test_cli_extensions.py tests/application/test_guard_agent_service.py tests/kernel/v1/test_promotion_ledger.py tests/kernel/v1/test_tombstone_promotion.py tests/reforger/compiler/test_compile_textmystery_v0.py`
  - result: `34 passed`
- Completed `TD-EXC-1d` by narrowing the remaining broad catches in:
  - `orket/application/workflows/orchestrator.py`
  - `orket/runtime/execution_pipeline.py`
  - `orket/interfaces/api.py`
  - `orket/application/services/gitea_state_worker.py`
  - `orket/streaming/model_provider.py`
- Verification:
  - `python -m pytest -q tests/application/test_orchestrator_epic.py tests/interfaces/test_api.py tests/application/test_execution_pipeline_workload_shell.py tests/application/test_execution_pipeline_session_status.py tests/application/test_execution_pipeline_run_ledger.py tests/application/test_execution_pipeline_gitea_state_loop.py tests/application/test_gitea_state_worker.py tests/application/test_gitea_state_worker_coordinator.py tests/streaming/test_stream_test_workload.py tests/streaming/test_manager.py`
  - result: `157 passed`
  - `rg -n "except Exception" orket` -> no matches

---

## Phase 4: Test Coverage

Status: **complete**
Priority: **write tests when modifying the module, or in focused test sprint**
Estimated scope: ~4-6 hours total

### Tasks

| ID | Task | Target Tests | Status |
|---|---|---|---|
| TD-TEST-1 | Webhook handler tests | 8+ tests: PR cycles, escalation, auto-merge/reject, sandbox trigger | complete |
| TD-TEST-2 | Sandbox orchestrator tests | 6+ tests: Compose generation (3 stacks), port allocation, password gen | complete |
| TD-TEST-3 | API concurrency tests | 5+ tests: concurrent requests, WebSocket isolation, session cleanup | complete |
| TD-TEST-4 | Verification path security test | 2 tests: valid path, malicious path | complete |
| TD-TEST-5 | Driver tests | 10+ tests: command routing, errors, edge cases | complete |

Exit criteria:
- Each module listed above has meaningful test coverage
- All new tests pass
- No existing tests broken

Progress update (2026-03-01):
- Completed `TD-TEST-4` with explicit fixture-path boundary tests in `tests/adapters/test_verification_subprocess.py`:
  - `test_verification_security_allows_fixture_under_verification_root`
  - `test_verification_security_rejects_path_traversal_fixture`
- Validation:
  - `python -m pytest -q tests/adapters/test_verification_subprocess.py`
  - result: `8 passed`
- Coverage audit run:
  - `python -m pytest -q tests/adapters/test_gitea_webhook.py tests/interfaces/test_webhook_factory.py tests/interfaces/test_webhook_rate_limit.py tests/adapters/test_sandbox_compose_generation.py tests/adapters/test_sandbox_command_runner.py tests/interfaces/test_api_task_lifecycle.py tests/interfaces/test_api_interactions.py tests/interfaces/test_api.py tests/application/test_driver_cli.py tests/application/test_driver_conversation.py`
  - result: `135 passed`
- Marked complete from existing validated coverage:
  - `TD-TEST-3` (API concurrency/websocket/task lifecycle coverage)
  - `TD-TEST-5` (driver command routing/conversation/error-path coverage; >10 tests)
- Completed `TD-TEST-2` by extending sandbox test coverage:
  - added `test_csharp_razor_ef_compose`
  - added `test_create_sandbox_uses_generated_password_in_database_url_and_compose`
  - validated compose generation across three stacks, port allocation uniqueness, and password propagation.
- Validation:
  - `python -m pytest -q tests/adapters/test_sandbox_compose_generation.py tests/adapters/test_sandbox_command_runner.py`
  - result: `6 passed`
- Completed `TD-TEST-1` by expanding webhook handler coverage to 8 scenarios in:
  - `tests/adapters/test_gitea_webhook.py`
  - includes review-cycle tracking, escalation, auto-reject, requirements issue creation, approval auto-merge, merge-triggered sandbox flow, and ignored-state paths.
- Validation:
  - `python -m pytest -q tests/adapters/test_gitea_webhook.py`
  - result: `8 passed`

---

## Phase 5: Structural Simplification

Status: **complete**
Priority: **lowest -- do only when it directly supports SDK or Meta Breaker work**
Estimated scope: ~4-6 hours total

### Tasks

| ID | Task | Status |
|---|---|---|
| TD-STRUCT-1 | Split driver.py into CommandParser + ResourceManager + DriverShell | complete |
| TD-STRUCT-2 | Inline trivial decision node methods in DefaultApiRuntimeStrategyNode | complete |
| TD-STRUCT-3 | Write mental model guide for contributors | complete |

Exit criteria:
- Driver path has no single file > 400 lines
- builtins.py reduced by ~200 lines
- Mental model guide exists and is accurate

Progress update (2026-03-01):
- Completed `TD-STRUCT-3` by adding contributor control-flow guide:
  - `docs/guides/CONTRIBUTOR-MENTAL-MODEL.md`
  - covers Driver -> ExecutionPipeline -> Orchestrator -> TurnExecutor flow and debugging order.
- Completed `TD-STRUCT-1` by splitting driver responsibilities into focused support modules:
  - `orket/driver_support_cli.py`
  - `orket/driver_support_resources.py`
  - `orket/driver_support_conversation.py`
  - `orket/driver.py` reduced to orchestration facade and initialization wiring.
  - verification: `orket/driver.py` is now under 400 lines.
- Completed `TD-STRUCT-2` by extracting API runtime decision node from `builtins.py`:
  - new module: `orket/decision_nodes/api_runtime_strategy_node.py`
  - `DefaultApiRuntimeStrategyNode` imported into `orket/decision_nodes/builtins.py`.
  - verification: `orket/decision_nodes/builtins.py` reduced by more than 200 lines.
- Validation:
  - `python -m pytest -q tests/application/test_driver_cli.py tests/application/test_driver_conversation.py tests/application/test_operator_canary.py tests/application/test_decision_nodes_planner.py tests/interfaces/test_api.py tests/interfaces/test_api_interactions.py tests/interfaces/test_api_task_lifecycle.py`
  - result: `168 passed`

---

## Ordering and Dependencies

```
Phase 1 (Security)     -- do first, no dependencies
    |
Phase 2 (Async)        -- independent, can parallel with Phase 1
    |
Phase 3 (Exceptions)   -- independent, can parallel
    |
Phase 4 (Tests)        -- best done after Phase 1-3 so tests cover fixed code
    |
Phase 5 (Structural)   -- lowest priority, do when it supports other work
```

Phases 1-3 can be done in any order or in parallel. Phase 4 benefits from doing 1-3 first. Phase 5 is optional and should only be done when it directly unblocks SDK or Meta Breaker.

---

## Integration with Roadmap

This project does NOT block:
- SDK Phase 1 (package bootstrap)
- Meta Breaker route development
- Reforger expansion

This project SHOULD be prioritized when:
- Touching a file that has a security fix pending (do the fix in the same PR)
- Writing tests for a module (add the missing tests at the same time)
- A bug surfaces that traces to a broad exception catch (fix the catch)

Rule: Fix debt when you're already in the neighborhood. Don't make special trips unless it's security.
