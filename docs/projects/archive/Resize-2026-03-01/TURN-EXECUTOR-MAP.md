# TurnExecutor Decomposition Map

Source: `orket/application/workflows/turn_executor.py`
Size: 2323 lines, 47 methods, 3 public classes
Production importers: orchestrator.py
Test importers: 7 test files

## Instance State

```
self.state: StateMachine                    # Used only by _validate_preconditions
self.tool_gate: ToolGate                    # Used only by _execute_tools
self.workspace: Path                        # Used by all artifact/observability methods
self.middleware: TurnLifecycleInterceptors  # Used by execute_turn and _execute_tools
```

## Public API (preserve as-is)

- `TurnExecutor(state, tool_gate, workspace, middleware)` -- constructor
- `TurnExecutor.execute_turn(issue, role, model_client, toolbox, context, system_prompt)` -- main entry
- `TurnResult` dataclass with factory methods: `succeeded()`, `failed()`, `governance_violation()`
- `ToolValidationError`, `ModelTimeoutError` exception classes

## Complete Method Inventory

### Group A: Coordinator (stays on TurnExecutor)
| Lines | Method | Calls |
|---|---|---|
| 106-493 | `execute_turn()` | All groups |
| 495-533 | `_validate_preconditions()` | self.state |

### Group B: Message Preparation -> MessageBuilder
| Lines | Method | Notes |
|---|---|---|
| 535-742 | `_prepare_messages()` | Uses path resolution helpers |
| 744-778 | `_runtime_tokens_payload()` | Static, no deps |

### Group C: Response Parsing -> ResponseParser
| Lines | Method | Notes |
|---|---|---|
| 780-852 | `_parse_response()` | Uses _non_json_residue |
| 1979-2024 | `_non_json_residue()` | Also used by scope diagnostics |
| 2026-2057 | `_extract_guard_review_payload()` | JSON extraction |

### Group D: Tool Execution -> ToolDispatcher
| Lines | Method | Notes |
|---|---|---|
| 854-1104 | `_execute_tools()` | Uses tool_gate, middleware |
| 1106-1113 | `_resolve_skill_tool_binding()` | Skill lookup |
| 1115-1128 | `_missing_required_permissions()` | Permission check |
| 1130-1138 | `_permission_values()` | Permission extraction |
| 1140-1156 | `_runtime_limit_violations()` | Limit validation |
| 1158-1165 | `_as_positive_float()` | Float parsing |

### Group E: Contract Validation -> ContractValidator
| Lines | Method | Notes |
|---|---|---|
| 1167-1251 | `_collect_contract_violations()` | Aggregator, calls all _meets_* |
| 1490-1514 | `_progress_contract_diagnostics()` | Diagnostic helper |
| 1516-1572 | `_meets_progress_contract()` | Tool + status check |
| 1574-1583 | `_meets_write_path_contract()` | Write path check |
| 1585-1622 | `_meets_guard_rejection_payload_contract()` | Guard JSON check |
| 1624-1633 | `_meets_read_path_contract()` | Read path check |
| 1635-1711 | `_meets_architecture_decision_contract()` | Architecture JSON check |
| 1713-1757 | `_parse_architecture_decision_payload()` | Architecture parsing |
| 1759-1922 | `_hallucination_scope_diagnostics()` | Scope constraint check |
| 1924-1954 | `_security_scope_diagnostics()` | Path hardening check |
| 1956-1977 | `_consistency_scope_diagnostics()` | JSON purity check |

### Group F: Path Resolution (shared utility, used by Groups B, E, G)
| Lines | Method | Notes |
|---|---|---|
| 1442-1444 | `_required_read_paths()` | Context extraction |
| 1446-1448 | `_missing_required_read_paths()` | Context extraction |
| 1450-1467 | `_partition_required_read_paths()` | Path splitting |
| 1469-1474 | `_required_write_paths()` | Context extraction |
| 1476-1481 | `_observed_read_paths()` | Tool call extraction |
| 1483-1488 | `_observed_write_paths()` | Tool call extraction |

### Group G: Corrective Prompting -> CorrectivePromptBuilder
| Lines | Method | Notes |
|---|---|---|
| 1253-1375 | `_build_corrective_instruction()` | Uses path helpers |
| 1377-1401 | `_rule_specific_fix_hints()` | Rule lookup |
| 1403-1423 | `_hint_for_rule_id()` | Hint text |
| 1425-1440 | `_deterministic_failure_message()` | Reason mapping |

### Group H: State Transitions (small, stays on coordinator or moves to ToolDispatcher)
| Lines | Method | Notes |
|---|---|---|
| 2237-2244 | `_state_delta_from_tool_calls()` | Status extraction |
| 2246-2284 | `_synthesize_required_status_tool_call()` | Auto-inject status |

### Group I: Artifact Writing -> TurnArtifactWriter
| Lines | Method | Notes |
|---|---|---|
| 2059-2061 | `_message_hash()` | SHA256 |
| 2063-2066 | `_memory_trace_enabled()` | Config check |
| 2068-2070 | `_hash_payload()` | SHA256 |
| 2072-2095 | `_append_memory_event()` | Trace buffer |
| 2097-2216 | `_emit_memory_traces()` | Write traces |
| 2218-2235 | `_write_turn_artifact()` | File write |
| 2286-2318 | `_write_turn_checkpoint()` | Checkpoint write |
| 2320-2322 | `_tool_replay_key()` | Hash key |
| 2324-2343 | `_tool_result_path()` | Path compute |
| 2345-2371 | `_load_replay_tool_result()` | Cache load |
| 2373-2392 | `_persist_tool_result()` | Cache write |

## Dependency Graph

```
execute_turn()
  |-- _validate_preconditions()          [Coordinator]
  |-- MessageBuilder._prepare_messages() [Group B]
  |-- ResponseParser._parse_response()   [Group C]
  |-- ContractValidator._collect_contract_violations() [Group E]
  |   |-- PathResolver (all 6 methods)   [Group F]
  |   |-- ResponseParser._non_json_residue()
  |   |-- ResponseParser._extract_guard_review_payload()
  |-- CorrectivePromptBuilder._build_corrective_instruction() [Group G]
  |   |-- PathResolver._required_read/write_paths()
  |-- ToolDispatcher._execute_tools()    [Group D]
  |   |-- TurnArtifactWriter._load_replay_tool_result()
  |   |-- TurnArtifactWriter._persist_tool_result()
  |-- _state_delta_from_tool_calls()     [Group H]
  |-- _synthesize_required_status_tool_call() [Group H]
  |-- TurnArtifactWriter._emit_memory_traces() [Group I]
  |-- TurnArtifactWriter._write_turn_checkpoint() [Group I]
  |-- MessageBuilder._runtime_tokens_payload() [Group B]
```

## Cross-Group Dependencies

| Consumer | Provider | Shared Method |
|---|---|---|
| ContractValidator | ResponseParser | `_non_json_residue()`, `_extract_guard_review_payload()` |
| ContractValidator | PathResolver | All 6 path methods |
| CorrectivePromptBuilder | PathResolver | `_required_read_paths()`, `_required_write_paths()` |
| MessageBuilder | PathResolver | `_required_read_paths()`, `_missing_required_read_paths()`, `_required_write_paths()` |
| ToolDispatcher | TurnArtifactWriter | `_load_replay_tool_result()`, `_persist_tool_result()` |

## Target File Layout

```
orket/application/workflows/
  turn_executor.py          # TurnExecutor coordinator + TurnResult + exceptions (<250 lines)
  turn_message_builder.py   # MessageBuilder (~210 lines)
  turn_response_parser.py   # ResponseParser (~120 lines)
  turn_tool_dispatcher.py   # ToolDispatcher (~300 lines)
  turn_contract_validator.py # ContractValidator (~600 lines)
  turn_corrective_prompt.py # CorrectivePromptBuilder (~120 lines)
  turn_artifact_writer.py   # TurnArtifactWriter (~250 lines)
  turn_path_resolver.py     # PathResolver (~50 lines, shared utility)
```

## Migration Strategy

1. Extract PathResolver first (no external deps, used by 3 groups).
2. Extract TurnArtifactWriter (self-contained, only writes files).
3. Extract ResponseParser (only internal helper deps).
4. Extract ContractValidator (depends on PathResolver + ResponseParser).
5. Extract CorrectivePromptBuilder (depends on PathResolver).
6. Extract ToolDispatcher (depends on TurnArtifactWriter for replay).
7. Extract MessageBuilder (depends on PathResolver).
8. Slim TurnExecutor to coordinator that composes all extracted classes.
9. Add re-exports in turn_executor.py for backwards compatibility.
