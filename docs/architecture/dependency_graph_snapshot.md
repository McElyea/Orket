# Dependency Graph Snapshot

Generated: `2026-02-13T04:29:05.815004+00:00`
Module count: `106`

## Layer Edges

| Source | Target | Count |
|---|---|---:|
| `root` | `root` | 60 |
| `orchestration` | `root` | 22 |
| `decision_nodes` | `root` | 12 |
| `root` | `infrastructure` | 10 |
| `domain` | `root` | 9 |
| `runtime` | `root` | 9 |
| `agents` | `root` | 8 |
| `services` | `domain` | 8 |
| `interfaces` | `root` | 7 |
| `root` | `core` | 7 |
| `orchestration` | `domain` | 6 |
| `decision_nodes` | `decision_nodes` | 5 |
| `orchestration` | `core` | 5 |
| `orchestration` | `infrastructure` | 5 |
| `vendors` | `vendors` | 5 |
| `core` | `root` | 4 |
| `infrastructure` | `core` | 4 |
| `orchestration` | `orchestration` | 4 |
| `services` | `root` | 4 |
| `vendors` | `root` | 4 |
| `domain` | `core` | 3 |
| `orchestration` | `decision_nodes` | 3 |
| `orchestration` | `services` | 3 |
| `runtime` | `infrastructure` | 3 |
| `runtime` | `runtime` | 3 |
| `agents` | `services` | 2 |
| `core` | `services` | 2 |
| `decision_nodes` | `orchestration` | 2 |
| `decision_nodes` | `services` | 2 |
| `infrastructure` | `root` | 2 |
| `root` | `domain` | 2 |
| `root` | `orchestration` | 2 |
| `runtime` | `decision_nodes` | 2 |
| `services` | `infrastructure` | 2 |
| `services` | `services` | 2 |
| `vendors` | `infrastructure` | 2 |
| `agents` | `agents` | 1 |
| `agents` | `domain` | 1 |
| `core` | `core` | 1 |
| `core` | `domain` | 1 |
| `decision_nodes` | `domain` | 1 |
| `decision_nodes` | `infrastructure` | 1 |
| `domain` | `domain` | 1 |
| `domain` | `infrastructure` | 1 |
| `interfaces` | `decision_nodes` | 1 |
| `interfaces` | `orchestration` | 1 |
| `root` | `agents` | 1 |
| `root` | `decision_nodes` | 1 |
| `root` | `runtime` | 1 |
| `root` | `services` | 1 |
| `runtime` | `orchestration` | 1 |
| `services` | `core` | 1 |
| `services` | `decision_nodes` | 1 |
| `services` | `orchestration` | 1 |

## Top Module Edges (Top 50)

| Source Module | Target Module | Count |
|---|---|---:|
| `orket.services.sandbox_orchestrator` | `orket.domain.verification` | 4 |
| `orket.discovery` | `orket.hardware` | 3 |
| `orket.preview` | `orket.schema` | 3 |
| `orket.driver` | `orket.orket` | 2 |
| `orket.driver` | `orket.schema` | 2 |
| `orket.orchestration.engine` | `orket.orket` | 2 |
| `orket.orchestration.orchestrator` | `orket.orchestration.models` | 2 |
| `orket.orchestration.orchestrator` | `orket.exceptions` | 2 |
| `orket.orchestration.orchestrator` | `orket.domain.sandbox` | 2 |
| `orket.orchestration.turn_executor` | `orket.schema` | 2 |
| `orket.runtime.config_loader` | `orket.schema` | 2 |
| `orket.tool_families.cards` | `orket.infrastructure.async_card_repository` | 2 |
| `orket.tool_families.governance` | `orket.logging` | 2 |
| `orket.vendors.local` | `orket.schema` | 2 |
| `orket.vendors.local` | `orket.infrastructure.async_card_repository` | 2 |
| `orket.board` | `orket.orket` | 1 |
| `orket.board` | `orket.schema` | 1 |
| `orket.board` | `orket.exceptions` | 1 |
| `orket.discovery` | `orket.infrastructure.async_file_tools` | 1 |
| `orket.discovery` | `orket.orket` | 1 |
| `orket.discovery` | `orket.schema` | 1 |
| `orket.discovery` | `orket.logging` | 1 |
| `orket.discovery` | `orket.settings` | 1 |
| `orket.discovery` | `orket.domain.reconciler` | 1 |
| `orket.driver` | `orket.infrastructure.async_file_tools` | 1 |
| `orket.driver` | `orket.llm` | 1 |
| `orket.driver` | `orket.logging` | 1 |
| `orket.driver` | `orket.exceptions` | 1 |
| `orket.driver` | `orket.orchestration.models` | 1 |
| `orket.llm` | `orket.exceptions` | 1 |
| `orket.llm` | `orket.logging` | 1 |
| `orket.logging` | `orket.time_utils` | 1 |
| `orket.logging` | `orket.naming` | 1 |
| `orket.organization_loop` | `orket.infrastructure.async_file_tools` | 1 |
| `orket.organization_loop` | `orket.orket` | 1 |
| `orket.organization_loop` | `orket.schema` | 1 |
| `orket.organization_loop` | `orket.domain.critical_path` | 1 |
| `orket.organization_loop` | `orket.logging` | 1 |
| `orket.orket` | `orket.runtime` | 1 |
| `orket.preview` | `orket.infrastructure.async_file_tools` | 1 |
| `orket.preview` | `orket.orket` | 1 |
| `orket.preview` | `orket.agents.agent` | 1 |
| `orket.preview` | `orket.utils` | 1 |
| `orket.preview` | `orket.exceptions` | 1 |
| `orket.preview` | `orket.logging` | 1 |
| `orket.preview` | `orket.orchestration.models` | 1 |
| `orket.preview` | `orket.llm` | 1 |
| `orket.repositories` | `orket.core.contracts.repositories` | 1 |
| `orket.schema` | `orket.core.types` | 1 |
| `orket.schema` | `orket.core.bottlenecks` | 1 |

## Notes
- This is a structural import snapshot; it is not a runtime call graph.
- Use with architecture boundary tests to enforce dependency direction.
