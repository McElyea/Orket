# Dependency Graph Snapshot

Generated: `2026-09-21T19:12:16.661667+00:00`

Generated from the canonical dependency policy; do not edit this view by hand.
This is conservative static import evidence, not a runtime call graph or a core-purity proof.

Collection: `True`. Policy verdict: `True`.
Files: 1112; import sites: 3564; forbidden pairs: 0; analysis errors: 0; authority cycles: 0.

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

Decision-node core targets: `orket.core.cards_runtime_contract`, `orket.core.contracts.decision_inputs`, `orket.core.contracts.model_selection`, `orket.exceptions`, `orket.schema`

Side-effect-free adapter targets: none declared

## Observed layer edges

| Source | Target | Import sites |
|---|---|---:|
| `adapters` | `adapters` | 234 |
| `adapters` | `core` | 139 |
| `application` | `adapters` | 412 |
| `application` | `application` | 1725 |
| `application` | `core` | 757 |
| `application` | `decision_nodes` | 4 |
| `core` | `core` | 142 |
| `decision_nodes` | `core` | 6 |
| `decision_nodes` | `decision_nodes` | 2 |
| `interfaces` | `application` | 98 |
| `interfaces` | `interfaces` | 45 |

## Bounded dynamic routes

These routes have an inspected syntactic proof; they are not analysis-error waivers.

| Source | Line | Kind | Proven boundary |
|---|---:|---|---|
| `orket/adapters/execution/extension_modules.py` | 102 | `external_module_cache_read` | Plain absolute name outside `orket` via `orket.adapters.execution.extension_modules._external_module_name` |
| `orket/adapters/execution/extension_modules.py` | 110 | `external_module_import` | Plain absolute name outside `orket` via `orket.adapters.execution.extension_modules._external_module_name` |
| `orket/extensions/agent_workload_subprocess.py` | 118 | `importer_interception` | `builtins.__import__` via `orket.extensions.sdk_workload_subprocess._guarded_import` |
| `orket/extensions/agent_workload_subprocess.py` | 119 | `importer_interception` | `importlib.import_module` via `orket.extensions.sdk_workload_subprocess._guarded_import_module` |
| `orket/extensions/sdk_workload_subprocess.py` | 131 | `importer_interception` | `builtins.__import__` via `orket.extensions.sdk_workload_subprocess._guarded_import` |
| `orket/extensions/sdk_workload_subprocess.py` | 132 | `importer_interception` | `importlib.import_module` via `orket.extensions.sdk_workload_subprocess._guarded_import_module` |

## Exceptions

Consumed: 0; unused: 0; redundant: 0.

Exact exception metadata, all import sites, source hashes, analysis errors and authority cycles are in the JSON snapshot.
An exported graph does not establish a passing verdict. Unresolved routes and forbidden edges remain failures.
