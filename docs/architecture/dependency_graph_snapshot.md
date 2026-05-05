# Dependency Graph Snapshot

Generated: `2026-05-03T19:57:03.376967+00:00`
Module count: `767`
Files scanned: `767`
Policy: `model\core\contracts\dependency_direction_policy.json` (`1.0.0`)

## Layer Edges

| Source | Target | Count |
|---|---|---:|
| `application` | `application` | 257 |
| `application` | `core` | 224 |
| `runtime` | `runtime` | 203 |
| `platform` | `platform` | 90 |
| `application` | `platform` | 83 |
| `adapters` | `adapters` | 55 |
| `application` | `adapters` | 47 |
| `application` | `runtime` | 40 |
| `runtime` | `platform` | 39 |
| `core` | `core` | 37 |
| `adapters` | `platform` | 26 |
| `interfaces` | `application` | 26 |
| `runtime` | `application` | 26 |
| `interfaces` | `interfaces` | 24 |
| `interfaces` | `platform` | 24 |
| `adapters` | `core` | 23 |
| `orchestration` | `application` | 17 |
| `runtime` | `adapters` | 17 |
| `adapters` | `runtime` | 14 |
| `core` | `platform` | 13 |
| `domain` | `core` | 13 |
| `runtime` | `core` | 11 |
| `services` | `application` | 11 |
| `interfaces` | `adapters` | 10 |
| `orchestration` | `platform` | 10 |
| `platform` | `adapters` | 10 |
| `kernel` | `kernel` | 9 |
| `platform` | `core` | 9 |
| `services` | `adapters` | 9 |
| `platform` | `runtime` | 8 |
| `services` | `core` | 8 |
| `agents` | `platform` | 7 |
| `decision_nodes` | `decision_nodes` | 7 |
| `decision_nodes` | `platform` | 6 |
| `interfaces` | `runtime` | 6 |
| `application` | `services` | 5 |
| `interfaces` | `core` | 5 |
| `orchestration` | `adapters` | 5 |
| `orchestration` | `runtime` | 5 |
| `runtime` | `orchestration` | 5 |
| `vendors` | `vendors` | 5 |
| `application` | `orchestration` | 4 |
| `orchestration` | `orchestration` | 4 |
| `platform` | `services` | 4 |
| `vendors` | `platform` | 4 |
| `agents` | `application` | 3 |
| `agents` | `core` | 3 |
| `interfaces` | `legacy` | 3 |
| `orchestration` | `core` | 3 |
| `platform` | `application` | 3 |
| `platform` | `orchestration` | 3 |
| `runtime` | `decision_nodes` | 3 |
| `services` | `platform` | 3 |
| `agents` | `agents` | 2 |
| `application` | `decision_nodes` | 2 |
| `application` | `kernel` | 2 |
| `core` | `services` | 2 |
| `decision_nodes` | `adapters` | 2 |
| `decision_nodes` | `core` | 2 |
| `interfaces` | `orchestration` | 2 |
| `runtime` | `interfaces` | 2 |
| `services` | `runtime` | 2 |
| `vendors` | `adapters` | 2 |
| `adapters` | `orchestration` | 1 |
| `adapters` | `services` | 1 |
| `agents` | `adapters` | 1 |
| `agents` | `runtime` | 1 |
| `domain` | `platform` | 1 |
| `interfaces` | `decision_nodes` | 1 |
| `interfaces` | `kernel` | 1 |
| `orchestration` | `decision_nodes` | 1 |
| `orchestration` | `kernel` | 1 |
| `platform` | `agents` | 1 |
| `platform` | `decision_nodes` | 1 |
| `platform` | `legacy` | 1 |
| `runtime` | `services` | 1 |
| `services` | `decision_nodes` | 1 |
| `services` | `services` | 1 |
| `vendors` | `runtime` | 1 |

## Forbidden Edge Hits

| Source | Target | Count |
|---|---|---:|
| _none_ | _none_ | 0 |

## Legacy Edge Budget

- Actual legacy edges: `4`
- Budget max: `10`
- Exceeded: `False`

## Top Module Edges (Top 50)

| Source Module | Target Module | Count |
|---|---|---:|
| `orket.runtime.config.provider_runtime_target` | `orket.runtime.provider_runtime_inventory` | 10 |
| `orket.application.services.runtime_policy` | `orket.runtime.determinism_controls` | 8 |
| `orket.runtime.config.config_loader` | `orket.schema` | 4 |
| `orket.discovery` | `orket.hardware` | 3 |
| `orket.preview` | `orket.schema` | 3 |
| `orket.runtime.evidence.run_evidence_graph_projection_support` | `orket.application.services.kernel_action_control_plane_resource_lifecycle` | 3 |
| `orket.runtime.evidence.run_evidence_graph_projection_support` | `orket.application.services.turn_tool_control_plane_resource_lifecycle` | 3 |
| `orket.core.domain.control_plane_reservations` | `orket.core.contracts.control_plane_models` | 3 |
| `orket.driver` | `orket.schema` | 2 |
| `orket.decision_nodes.api_runtime_strategy_node` | `orket.board` | 2 |
| `orket.decision_nodes.builtins` | `orket.core.cards_runtime_contract` | 2 |
| `orket.services.sandbox_orchestrator` | `orket.core.domain.sandbox_lifecycle` | 2 |
| `orket.vendors.local` | `orket.schema` | 2 |
| `orket.vendors.local` | `orket.adapters.storage.async_card_repository` | 2 |
| `orket.workloads.rulesim_v0` | `orket.rulesim.workload` | 2 |
| `orket.runtime.evidence.run_evidence_graph_projection_support` | `orket.application.services.orchestrator_issue_control_plane_support` | 2 |
| `orket.interfaces.routers.sessions` | `orket.marshaller.cli` | 2 |
| `orket.core.domain.control_plane_effect_journal` | `orket.core.contracts.control_plane_effect_journal_models` | 2 |
| `orket.core.domain.control_plane_final_truth` | `orket.core.contracts.control_plane_models` | 2 |
| `orket.core.domain.control_plane_leases` | `orket.core.contracts.control_plane_models` | 2 |
| `orket.core.domain.control_plane_recovery` | `orket.core.contracts.control_plane_models` | 2 |
| `orket.application.review.run_service` | `orket.application.review.models` | 2 |
| `orket.application.services.control_plane_target_resource_refs` | `orket.application.services.orchestrator_issue_control_plane_support` | 2 |
| `orket.application.services.sandbox_lifecycle_reconciliation_service` | `orket.application.services.sandbox_control_plane_checkpoint_service` | 2 |
| `orket.application.workflows.orchestrator_ops` | `orket.exceptions` | 2 |
| `orket.application.workflows.orchestrator_ops` | `orket.settings` | 2 |
| `orket.application.workflows.orchestrator_ops` | `orket.core.domain.sandbox` | 2 |
| `orket.application.workflows.turn_contract_rules` | `orket.application.services.tool_parser` | 2 |
| `orket.application.workflows.turn_executor_model_flow` | `orket.application.workflows.turn_executor_runtime` | 2 |
| `orket.adapters.vcs.webhook_db` | `orket.core.domain.bug_fix_phase` | 2 |
| `orket.adapters.tools.families.cards` | `orket.adapters.storage.async_card_repository` | 2 |
| `orket.adapters.tools.families.governance` | `orket.logging` | 2 |
| `orket.board` | `orket.exceptions` | 1 |
| `orket.board` | `orket.runtime` | 1 |
| `orket.board` | `orket.schema` | 1 |
| `orket.board` | `orket.core.domain.reconciler` | 1 |
| `orket.discovery` | `orket.adapters.storage.async_file_tools` | 1 |
| `orket.discovery` | `orket.logging` | 1 |
| `orket.discovery` | `orket.runtime` | 1 |
| `orket.discovery` | `orket.project_paths` | 1 |
| `orket.discovery` | `orket.schema` | 1 |
| `orket.discovery` | `orket.settings` | 1 |
| `orket.discovery` | `orket.core.domain.reconciler` | 1 |
| `orket.driver` | `orket.adapters.llm.local_model_provider` | 1 |
| `orket.driver` | `orket.adapters.storage.async_file_tools` | 1 |
| `orket.driver` | `orket.adapters.tools.families.reforger_tools` | 1 |
| `orket.driver` | `orket.driver_support_cli` | 1 |
| `orket.driver` | `orket.driver_support_conversation` | 1 |
| `orket.driver` | `orket.driver_support_resources` | 1 |
| `orket.driver` | `orket.exceptions` | 1 |

## Notes
- This is a structural import snapshot; it is not a runtime call graph.
- Use with architecture boundary tests to enforce dependency direction.
