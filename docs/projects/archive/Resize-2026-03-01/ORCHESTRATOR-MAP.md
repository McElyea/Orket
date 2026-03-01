# Orchestrator Decomposition Map

Source: `orket/application/workflows/orchestrator.py`
Size: 1896 lines (1953 with imports), 37 methods
Production importers: decision_nodes/builtins.py
Test importers: 4 test files

## Instance State (17 variables)

```
# Core
self.workspace: Path
self.config_root: Path
self.db_path: Path
self.org                              # Organization config

# Repositories
self.async_cards                      # CardRepository
self.snapshots                        # SnapshotRepository
self.pending_gates                    # AsyncPendingGateRepository
self.memory                           # MemoryStore
self.notes                            # NoteStore

# Services
self.loader                           # ConfigLoader
self.sandbox_orchestrator              # SandboxOrchestrator

# Decision Nodes
self.decision_nodes                    # DecisionNodeRegistry
self.planner_node                      # Resolved planner
self.router_node                       # Resolved router
self.evaluator_node                    # Resolved evaluator
self.loop_policy_node                  # Resolved loop policy
self.context_window                    # Resolved context calculator
self.model_client_node                 # Resolved model client

# Mutable shared state
self.transcript: list                  # Turn history
self._sandbox_locks: defaultdict       # Per-rock async locks
self._sandbox_failed_rocks: set        # Failed sandbox set
self._team_replan_counts: defaultdict  # Replan attempt counter
```

## Public API (preserve as-is)

- `Orchestrator(workspace, async_cards, snapshots, org, config_root, db_path, loader, sandbox_orchestrator, pending_gates, decision_nodes)` -- constructor
- `Orchestrator.execute_epic(epic, team, env, active_build)` -- main entry
- `Orchestrator.verify_issue(issue, epic, env)` -- verification entry

## Complete Method Inventory

### Group A: Configuration Resolution -> OrchestratorConfig
| Lines | Method | Notes |
|---|---|---|
| 107 | `_resolve_architecture_mode()` | Env/org lookup |
| 115 | `_resolve_frontend_framework_mode()` | Env/org lookup |
| 123 | `_resolve_architecture_pattern()` | Derived from arch mode |
| 129 | `_resolve_project_surface_profile()` | Env/org lookup |
| 137 | `_resolve_small_project_builder_variant()` | Env/org lookup |
| 145 | `_resolve_workflow_profile()` | Env/org lookup |
| 364 | `_resolve_prompt_resolver_mode()` | Env/org lookup |
| 374 | `_resolve_prompt_selection_policy()` | Env/org lookup |
| 384 | `_resolve_prompt_selection_strict()` | Env/org lookup |
| 402 | `_resolve_prompt_version_exact()` | Env/org lookup |
| 410 | `_resolve_verification_scope_limits()` | Env/org lookup |

### Group B: Feature Flags -> OrchestratorConfig
| Lines | Method | Notes |
|---|---|---|
| 304 | `_is_sandbox_disabled()` | Env/org check |
| 316 | `_is_scaffolder_disabled()` | Env/org check |
| 328 | `_is_dependency_manager_disabled()` | Env/org check |
| 340 | `_is_runtime_verifier_disabled()` | Env/org check |
| 352 | `_is_deployment_planner_disabled()` | Env/org check |

### Group C: Small Project Team Policy -> OrchestratorConfig
| Lines | Method | Notes |
|---|---|---|
| 211 | `_small_project_issue_threshold()` | Threshold lookup |
| 220 | `_should_auto_inject_small_project_reviewer()` | Policy check |
| 235 | `_small_project_reviewer_seat_name()` | Name lookup |
| 248 | `_auto_inject_small_project_reviewer_seat()` | Team mutation |
| 265 | `_resolve_small_project_team_policy()` | Composite policy |

### Group D: Epic Execution (stays on Orchestrator coordinator)
| Lines | Method | Notes |
|---|---|---|
| 513-796 | `execute_epic()` | Main loop: scaffold -> deps -> deploy -> parallel issues |
| 480-511 | `_trigger_sandbox()` | Lock-protected sandbox deploy |
| 1827-1839 | `_save_checkpoint()` | Snapshot persistence |

### Group E: Dependency & DAG -> DependencyGraphManager
| Lines | Method | Notes |
|---|---|---|
| 817-942 | `_propagate_dependency_blocks()` | Downstream blocking |
| 848-942 | `_maybe_schedule_team_replan()` | Replan trigger |

### Group F: Issue Turn Execution -> IssueTurnRunner
| Lines | Method | Notes |
|---|---|---|
| 944-1426 | `_execute_issue_turn()` | Single issue turn: verify -> route -> dispatch -> handle |
| 163-209 | `_request_issue_transition()` | State machine transition |
| 1808-1826 | `_dispatch_turn()` | TurnExecutor delegation |
| 1443-1500 | `_create_pending_gate_request()` | Tool approval request |
| 1478-1500 | `_create_pending_tool_approval_request()` | Structured approval |

### Group G: Verification -> stays with Orchestrator or extracted
| Lines | Method | Notes |
|---|---|---|
| 438-478 | `verify_issue()` | Fixture + sandbox verification |

### Group H: Context Building -> TurnContextBuilder
| Lines | Method | Notes |
|---|---|---|
| 1502-1730 | `_build_turn_context()` | Full context dict assembly |
| 1731-1806 | `_build_dependency_context()` | Dependency graph info |
| 435-436 | `_history_context()` | Turn history |

### Group I: Guard & Governance -> IssueTurnRunner (sub-methods)
| Lines | Method | Notes |
|---|---|---|
| 1427-1441 | `_validate_guard_rejection_payload()` | Guard data validation |
| 1760-1798 | `_extract_guard_review_payload()` | JSON extraction |
| 1799-1826 | `_resolve_guard_event()` | Status -> event mapping |
| 1943-1947 | `_is_issue_idesign_enabled()` | iDesign flag |
| 1949-1953 | `_normalize_governance_violation_message()` | Error normalization |

### Group J: Failure Handling -> FailureHandler
| Lines | Method | Notes |
|---|---|---|
| 1841-1941 | `_handle_failure()` | Report + evaluate + act |

## Dependency Graph

```
execute_epic()
  |-- OrchestratorConfig._resolve_*()          [Group A/B/C]
  |-- _trigger_sandbox()                        [Coordinator]
  |-- IssueTurnRunner._execute_issue_turn()    [Group F]
  |   |-- OrchestratorConfig._resolve_*()
  |   |-- TurnContextBuilder._build_turn_context() [Group H]
  |   |   |-- TurnContextBuilder._build_dependency_context()
  |   |   |-- TurnContextBuilder._history_context()
  |   |-- IssueTurnRunner._dispatch_turn()
  |   |-- IssueTurnRunner._request_issue_transition()
  |   |-- IssueTurnRunner._create_pending_gate_request()
  |   |-- IssueTurnRunner._extract_guard_review_payload()
  |   |-- IssueTurnRunner._resolve_guard_event()
  |   |-- IssueTurnRunner._validate_guard_rejection_payload()
  |   |-- verify_issue()                       [Group G]
  |   |-- FailureHandler._handle_failure()     [Group J]
  |-- DependencyGraphManager._propagate_dependency_blocks() [Group E]
  |-- DependencyGraphManager._maybe_schedule_team_replan()
  |-- _save_checkpoint()                        [Coordinator]
```

## Cross-Group Dependencies

| Consumer | Provider | Shared Resource |
|---|---|---|
| IssueTurnRunner | OrchestratorConfig | All _resolve_*() methods |
| IssueTurnRunner | TurnContextBuilder | _build_turn_context() |
| IssueTurnRunner | FailureHandler | _handle_failure() |
| execute_epic | OrchestratorConfig | Feature flags, team policy |
| execute_epic | DependencyGraphManager | Block propagation |
| TurnContextBuilder | OrchestratorConfig | _resolve_prompt_*() methods |

## Target File Layout

```
orket/application/workflows/
  orchestrator.py              # Orchestrator coordinator (<300 lines)
  orchestrator_config.py       # OrchestratorConfig (~200 lines)
  issue_turn_runner.py         # IssueTurnRunner (~500 lines)
  turn_context_builder.py      # TurnContextBuilder (~230 lines)
  failure_handler.py           # FailureHandler (~120 lines)
  dependency_graph_manager.py  # DependencyGraphManager (~100 lines)
```

## Migration Strategy

1. Extract OrchestratorConfig first (pure lookups, no async, no side effects).
2. Extract TurnContextBuilder (reads only, no mutations).
3. Extract FailureHandler (isolated failure logic).
4. Extract DependencyGraphManager (isolated DAG logic).
5. Extract IssueTurnRunner (largest piece, depends on Config + Context + Failure).
6. Slim Orchestrator to coordinator.
7. Add re-exports in orchestrator.py for backwards compatibility.

## Shared State Handling

The mutable state (`_sandbox_locks`, `_sandbox_failed_rocks`, `_team_replan_counts`, `transcript`) stays on the Orchestrator coordinator. Extracted classes receive references to what they need:
- IssueTurnRunner receives `transcript` (to append) and state references
- DependencyGraphManager receives `_team_replan_counts`
- OrchestratorConfig receives `org` (read-only)
