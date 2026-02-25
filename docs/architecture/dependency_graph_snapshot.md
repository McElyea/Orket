# Dependency Graph Snapshot

Generated: `2026-02-24T19:28:36.687539+00:00`
Module count: `157`
Files scanned: `157`
Policy: `model\core\contracts\dependency_direction_policy.json` (`1.0.0`)

## Layer Edges

| Source | Target | Count |
|---|---|---:|
| `application` | `application` | 18 |
| `adapters` | `adapters` | 16 |
| `application` | `platform` | 16 |
| `application` | `core` | 14 |
| `interfaces` | `platform` | 12 |
| `platform` | `platform` | 12 |
| `adapters` | `platform` | 10 |
| `orchestration` | `platform` | 9 |
| `kernel` | `kernel` | 7 |
| `adapters` | `core` | 6 |
| `domain` | `platform` | 6 |
| `application` | `domain` | 5 |
| `core` | `platform` | 4 |
| `decision_nodes` | `decision_nodes` | 4 |
| `interfaces` | `application` | 4 |
| `runtime` | `runtime` | 4 |
| `vendors` | `vendors` | 4 |
| `application` | `orchestration` | 3 |
| `domain` | `core` | 3 |
| `orchestration` | `application` | 3 |
| `platform` | `adapters` | 3 |
| `platform` | `core` | 3 |
| `platform` | `legacy` | 3 |
| `adapters` | `domain` | 2 |
| `application` | `adapters` | 2 |
| `application` | `decision_nodes` | 2 |
| `core` | `services` | 2 |
| `interfaces` | `core` | 2 |
| `interfaces` | `orchestration` | 2 |
| `orchestration` | `adapters` | 2 |
| `orchestration` | `legacy` | 2 |
| `runtime` | `interfaces` | 2 |
| `services` | `adapters` | 2 |
| `adapters` | `orchestration` | 1 |
| `adapters` | `services` | 1 |
| `application` | `kernel` | 1 |
| `application` | `services` | 1 |
| `core` | `core` | 1 |
| `core` | `domain` | 1 |
| `decision_nodes` | `platform` | 1 |
| `domain` | `domain` | 1 |
| `interfaces` | `adapters` | 1 |
| `interfaces` | `decision_nodes` | 1 |
| `legacy` | `runtime` | 1 |
| `orchestration` | `core` | 1 |
| `orchestration` | `decision_nodes` | 1 |
| `orchestration` | `domain` | 1 |
| `platform` | `orchestration` | 1 |
| `runtime` | `core` | 1 |
| `runtime` | `orchestration` | 1 |
| `runtime` | `platform` | 1 |
| `services` | `core` | 1 |
| `services` | `domain` | 1 |
| `vendors` | `platform` | 1 |

## Forbidden Edge Hits

| Source | Target | Count |
|---|---|---:|
| _none_ | _none_ | 0 |

## Legacy Edge Budget

- Actual legacy edges: `6`
- Budget max: `10`
- Exceeded: `False`

## Top Module Edges (Top 50)

| Source Module | Target Module | Count |
|---|---|---:|
| `orket.driver` | `orket.orket` | 2 |
| `orket.driver` | `orket.schema` | 2 |
| `orket.orchestration.engine` | `orket.orket` | 2 |
| `orket.application.workflows.orchestrator` | `orket.orchestration.models` | 2 |
| `orket.application.workflows.orchestrator` | `orket.exceptions` | 2 |
| `orket.application.workflows.orchestrator` | `orket.domain.sandbox` | 2 |
| `orket.application.workflows.turn_executor` | `orket.schema` | 2 |
| `orket.application.workflows.turn_executor` | `orket.application.services.tool_parser` | 2 |
| `orket.board` | `orket.orket` | 1 |
| `orket.board` | `orket.schema` | 1 |
| `orket.board` | `orket.exceptions` | 1 |
| `orket.driver` | `orket.adapters.storage.async_file_tools` | 1 |
| `orket.driver` | `orket.adapters.llm.local_model_provider` | 1 |
| `orket.driver` | `orket.logging` | 1 |
| `orket.driver` | `orket.exceptions` | 1 |
| `orket.driver` | `orket.orchestration.models` | 1 |
| `orket.logging` | `orket.time_utils` | 1 |
| `orket.logging` | `orket.naming` | 1 |
| `orket.orket` | `orket.runtime` | 1 |
| `orket.repositories` | `orket.core.contracts.repositories` | 1 |
| `orket.schema` | `orket.core.types` | 1 |
| `orket.schema` | `orket.core.bottlenecks` | 1 |
| `orket.settings` | `orket.adapters.storage.async_file_tools` | 1 |
| `orket.settings` | `orket.runtime_paths` | 1 |
| `orket.utils` | `orket.time_utils` | 1 |
| `orket.utils` | `orket.naming` | 1 |
| `orket.utils` | `orket.logging` | 1 |
| `orket.webhook_server` | `orket.adapters.vcs.gitea_webhook_handler` | 1 |
| `orket.webhook_server` | `orket.logging` | 1 |
| `orket.cli.setup_wizard` | `orket.schema` | 1 |
| `orket.cli.setup_wizard` | `orket.settings` | 1 |
| `orket.decision_nodes.registry` | `orket.decision_nodes.builtins` | 1 |
| `orket.decision_nodes.registry` | `orket.decision_nodes.contracts` | 1 |
| `orket.decision_nodes.registry` | `orket.settings` | 1 |
| `orket.decision_nodes.__init__` | `orket.decision_nodes.contracts` | 1 |
| `orket.decision_nodes.__init__` | `orket.decision_nodes.registry` | 1 |
| `orket.domain.bug_fix_phase` | `orket.logging` | 1 |
| `orket.domain.critical_path` | `orket.schema` | 1 |
| `orket.domain.critical_path` | `orket.core.critical_path` | 1 |
| `orket.domain.failure_reporter` | `orket.logging` | 1 |
| `orket.domain.failure_reporter` | `orket.domain.verification` | 1 |
| `orket.domain.records` | `orket.core.domain.records` | 1 |
| `orket.domain.state_machine` | `orket.core.domain.state_machine` | 1 |
| `orket.domain.state_machine` | `orket.schema` | 1 |
| `orket.domain.verification` | `orket.schema` | 1 |
| `orket.domain.verification` | `orket.logging` | 1 |
| `orket.interfaces.api` | `orket.logging` | 1 |
| `orket.interfaces.api` | `orket.state` | 1 |
| `orket.interfaces.api` | `orket.hardware` | 1 |
| `orket.interfaces.api` | `orket.decision_nodes.registry` | 1 |

## Notes
- This is a structural import snapshot; it is not a runtime call graph.
- Use with architecture boundary tests to enforce dependency direction.
