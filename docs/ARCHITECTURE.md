# Orket Runtime Architecture

This document describes the current folder architecture, dependency direction rules, and decision-node override wiring used in the runtime.

## 1. Folder Architecture

`orket/` is organized by stable runtime layers plus volatile decision seams:

1. `orket/domain/`
- Core business vocabulary and mechanical rules.
- Examples: state transitions, verification behavior, failure reporting.

2. `orket/infrastructure/`
- External adapters and persistence mechanisms.
- Examples: async SQLite repositories, async file I/O.

3. `orket/services/`
- Application services that coordinate domain + infrastructure.
- Examples: `ToolGate`, `PromptCompiler`, sandbox orchestration.

4. `orket/orchestration/`
- Stable orchestration flow and execution lifecycle.
- Owns loop structure, retries, checkpointing, and session execution.

5. `orket/decision_nodes/`
- Volatile behavior seams behind contracts.
- Current built-in node families:
  - planner
  - router
  - prompt strategy
  - evaluator
  - tool strategy

6. `orket/interfaces/`
- System edges (HTTP/API, CLI).
- Framework-specific integration only.

7. `orket/tools.py`
- Tool families (`FileSystemTools`, `CardManagementTools`, etc.).
- Uses:
  - stable invocation runtime seam (`ToolRuntimeExecutor`)
  - volatile mapping seam (`ToolStrategyNode`)

## 2. Dependency Direction Rules

Dependencies must point inward to stable contracts.

Allowed direction:
1. `interfaces -> orchestration/services/decision_nodes`
2. `orchestration -> domain/services/infrastructure/decision_nodes`
3. `services -> domain/infrastructure`
4. `decision_nodes -> decision_nodes.contracts + domain vocabulary`
5. `infrastructure -> domain vocabulary + standard libs + external libraries`

Disallowed direction:
1. `domain -> orchestration`
2. `domain -> interfaces`
3. `domain -> framework/runtime glue`
4. `decision_nodes -> interfaces`
5. `infrastructure -> services/orchestration/interfaces/decision_nodes`

Rule of thumb:
1. Stable layers own workflow mechanics.
2. Decision nodes own change-prone choices.
3. Swapping a decision node must not require changing the orchestration loop shape.

## 3. Decision Node Overrides

Node selection resolves from organization process rules and can be locally overridden by environment variables where implemented.

### Organization process rules example

```json
{
  "process_rules": {
    "planner_node": "default",
    "router_node": "default",
    "prompt_strategy_node": "default",
    "evaluator_node": "default",
    "tool_strategy_node": "default"
  }
}
```

### Tool strategy environment override

`ToolStrategyNode` can be overridden via:

1. `process_rules.tool_strategy_node`
2. `ORKET_TOOL_STRATEGY_NODE` (wins over `process_rules`)

Example:

```powershell
$env:ORKET_TOOL_STRATEGY_NODE="default"
python -m pytest tests/test_toolbox_refactor.py -q
```

### Runtime behavior

1. `DecisionNodeRegistry.resolve_tool_strategy()` selects the node.
2. `ToolBox` composes tool map through the selected node.
3. `ToolRuntimeExecutor` performs invocation mechanics (sync/async call handling + error normalization).

This keeps orchestration and tool execution stable while allowing targeted volatility in strategy selection.
