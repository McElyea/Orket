# Dependency Graph Snapshot

Generated: `2026-09-17T06:09:26.663161+00:00`

Generated from the canonical dependency policy; do not edit this view by hand.
This is conservative static import evidence, not a runtime call graph or a core-purity proof.

Collection: `True`. Policy verdict: `False`.
Files: 993; import sites: 3155; forbidden pairs: 58; analysis errors: 10; authority cycles: 1.

## Module classification

| Prefix | Layer |
|---|---|
| `orket.__init__` | `application` |
| `orket.adapters` | `adapters` |
| `orket.agents` | `application` |
| `orket.application` | `application` |
| `orket.board` | `application` |
| `orket.capabilities` | `adapters` |
| `orket.cli` | `interfaces` |
| `orket.core` | `core` |
| `orket.decision_nodes` | `decision_nodes` |
| `orket.discovery` | `application` |
| `orket.domain` | `core` |
| `orket.driver` | `application` |
| `orket.driver_support_cli` | `interfaces` |
| `orket.driver_support_conversation` | `application` |
| `orket.driver_support_resources` | `application` |
| `orket.events` | `application` |
| `orket.exceptions` | `core` |
| `orket.extensions` | `application` |
| `orket.hardware` | `adapters` |
| `orket.infrastructure` | `adapters` |
| `orket.interfaces` | `interfaces` |
| `orket.kernel` | `application` |
| `orket.logging` | `adapters` |
| `orket.marshaller` | `application` |
| `orket.naming` | `core` |
| `orket.orchestration` | `application` |
| `orket.organization_loop` | `application` |
| `orket.platform` | `application` |
| `orket.policy` | `application` |
| `orket.preview` | `adapters` |
| `orket.project_paths` | `adapters` |
| `orket.quickstart` | `interfaces` |
| `orket.reforger` | `application` |
| `orket.repositories` | `adapters` |
| `orket.rulesim` | `application` |
| `orket.runtime` | `application` |
| `orket.runtime_paths` | `adapters` |
| `orket.schema` | `core` |
| `orket.services` | `application` |
| `orket.session` | `application` |
| `orket.settings` | `application` |
| `orket.state` | `application` |
| `orket.streaming` | `adapters` |
| `orket.time_utils` | `adapters` |
| `orket.tool_families` | `adapters` |
| `orket.tool_runtime` | `adapters` |
| `orket.tool_strategy` | `adapters` |
| `orket.tools` | `adapters` |
| `orket.utils` | `adapters` |
| `orket.vendors` | `adapters` |
| `orket.webhook_server` | `interfaces` |
| `orket.workloads` | `application` |

## Allowed layer edges

| Source | Target |
|---|---|
| `adapters` | `adapters` |
| `application` | `application` |
| `core` | `core` |
| `decision_nodes` | `decision_nodes` |
| `interfaces` | `interfaces` |
| `interfaces` | `application` |
| `application` | `core` |
| `application` | `adapters` |
| `application` | `decision_nodes` |
| `adapters` | `core` |
| `decision_nodes` | `core` |

Decision-node core targets: `orket.core.cards_runtime_contract`, `orket.exceptions`, `orket.schema`

Side-effect-free adapter targets: none declared

## Observed layer edges

| Source | Target | Import sites |
|---|---|---:|
| `adapters` | `adapters` | 234 |
| `adapters` | `application` | 23 |
| `adapters` | `core` | 131 |
| `adapters` | `decision_nodes` | 1 |
| `application` | `adapters` | 296 |
| `application` | `application` | 1510 |
| `application` | `core` | 663 |
| `application` | `decision_nodes` | 8 |
| `application` | `interfaces` | 5 |
| `core` | `core` | 134 |
| `decision_nodes` | `adapters` | 3 |
| `decision_nodes` | `application` | 3 |
| `decision_nodes` | `core` | 4 |
| `decision_nodes` | `decision_nodes` | 7 |
| `interfaces` | `adapters` | 16 |
| `interfaces` | `application` | 74 |
| `interfaces` | `core` | 8 |
| `interfaces` | `interfaces` | 35 |

## Exceptions

Consumed: 0; unused: 0; redundant: 0.

Exact exception metadata, all import sites, source hashes, analysis errors and authority cycles are in the JSON snapshot.
An exported graph does not establish a passing verdict. Unresolved routes and forbidden edges remain failures.
