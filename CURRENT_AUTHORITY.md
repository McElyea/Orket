# Current authority

Last updated: 2026-10-07

<!-- Generated from docs/architecture/current_authority.json; do not edit this view. -->

This bounded index routes to canonical owners and contracts. It does not redefine their authority.
Command checks compare documented argv and source entrypoints; they do not execute the commands.
All listed proof is unavailable or historical. Current runtime acceptance is not established.

Validate: `python scripts/governance/check_current_authority.py`.

## Canonical commands

| Surface | Current scope | Source |
| --- | --- | --- |
| API server | python server.py | [docs/CONTRIBUTOR.md](<docs/CONTRIBUTOR.md>) |
| Named card | orket runtime --card &lt;card_id&gt; | [docs/CONTRIBUTOR.md](<docs/CONTRIBUTOR.md>) |
| Dependency direction | python scripts/governance/check_dependency_direction.py | [docs/CONTRIBUTOR.md](<docs/CONTRIBUTOR.md>) |
| Project docs hygiene | python scripts/governance/check_docs_project_hygiene.py | [docs/CONTRIBUTOR.md](<docs/CONTRIBUTOR.md>) |
| SDK and core development install; candidate path in docs/guides/MACOS_LOCAL_INSTALL.md and native proof procedure in docs/guides/MACOS_ACCEPTANCE_RUNBOOK.md remain subject to Mac acceptance | python -m pip install -e "./orket_extension_sdk[testing]" -e ".[dev]" | [README.md](<README.md>) |
| Default tests | python -m pytest -q | [docs/CONTRIBUTOR.md](<docs/CONTRIBUTOR.md>) |
| Quality coverage | pytest tests/ --cov=orket --cov-config=pyproject.toml --cov-fail-under=89 | [docs/CONTRIBUTOR.md](<docs/CONTRIBUTOR.md>) |
| Canonical Ruff | ruff check orket tests | [.gitea/workflows/quality.yml](<.gitea/workflows/quality.yml>) |
| Default runtime; project setup, diagnostics and prepared local-agent example documented alongside it | orket runtime | [docs/CONTRIBUTOR.md](<docs/CONTRIBUTOR.md>) |
| Strict taxonomy | python scripts/governance/enforce_test_taxonomy.py --strict | [docs/CONTRIBUTOR.md](<docs/CONTRIBUTOR.md>) |

## Execution ownership

| Surface | Current scope | Source |
| --- | --- | --- |
| Card execution and completion | executor: [orket/application/workflows/orchestrator.py#Orchestrator](<orket/application/workflows/orchestrator.py#Orchestrator>); authorization: [orket/application/services/cards_epic_control_plane_service.py#CardsEpicControlPlaneService](<orket/application/services/cards_epic_control_plane_service.py#CardsEpicControlPlaneService>); effect: [orket/adapters/storage/async_card_repository.py#AsyncCardRepository](<orket/adapters/storage/async_card_repository.py#AsyncCardRepository>); terminal: [orket/application/services/card_completion_service.py#CardCompletionService](<orket/application/services/card_completion_service.py#CardCompletionService>); Declared acceptance and current governed start-path contracts bound completion; artifact review uses its declared inputs. Prepared challenge checks require explicit retained acceptance; storage success alone does not prove the requested workload. | [docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md](<docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md>) |
| Governed turn tools | executor: [orket/application/workflows/turn_tool_dispatcher.py#ToolDispatcher](<orket/application/workflows/turn_tool_dispatcher.py#ToolDispatcher>); authorization: [orket/application/services/tool_gate_service.py#ToolGate](<orket/application/services/tool_gate_service.py#ToolGate>); effect: [orket/application/services/toolbox.py#ToolBox](<orket/application/services/toolbox.py#ToolBox>); terminal: [orket/application/services/turn_tool_control_plane_service.py#TurnToolControlPlaneService](<orket/application/services/turn_tool_control_plane_service.py#TurnToolControlPlaneService>); Each tool retains its admitted contract, including exact serialized UTF-8 file writes; model completion statements are not effect or terminal authority. | [docs/specs/TOOL_EXECUTION_GATE_V1.md](<docs/specs/TOOL_EXECUTION_GATE_V1.md>) |

## Canonical indexes

| Surface | Current scope | Source |
| --- | --- | --- |
| Normative architecture | architecture | [docs/ARCHITECTURE.md](<docs/ARCHITECTURE.md>) |
| Canonical contract and document index | contracts_index | [docs/README.md](<docs/README.md>) |
| Executable dependency policy | dependency_policy | [model/core/contracts/dependency_direction_policy.json](<model/core/contracts/dependency_direction_policy.json>) |
| Durable paths and retained stores | durable_paths | [docs/ARCHITECTURE.md](<docs/ARCHITECTURE.md>) |
| Transitional exception obligations | exception_register | [docs/projects/architectural-truth/ARCHITECTURE_EXCEPTION_REGISTER.json](<docs/projects/architectural-truth/ARCHITECTURE_EXCEPTION_REGISTER.json>) |
| Canonical script owners, current benchmark inputs and output locations | script_outputs | [scripts/README.md](<scripts/README.md>) |
| Active execution plans and project index; Mac acceptance remains outstanding | active_plan | [docs/ROADMAP.md](<docs/ROADMAP.md>) |
| Security and trust boundary | security | [docs/SECURITY.md](<docs/SECURITY.md>) |
| Governed start-path authority | start_paths | [docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md](<docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md>) |
| Contributor workflow | workflow | [docs/CONTRIBUTOR.md](<docs/CONTRIBUTOR.md>) |

## Active contracts

| Surface | Current scope | Source |
| --- | --- | --- |
| API construction and lifetime | Captured factory inputs, lifespan acquisition and owned schema/route preparation before readiness, required authentication/interaction owners, installed WebSocket transport, peer-disconnect settlement, target existence preflight, retained background failures, request admission and cleanup. Run views disclose retained repair and conformance warnings without rewriting evidence or completion. Hardware views preserve unknown unified-memory GPU observations; online is not Metal or model-fit proof. | [docs/specs/API_RUNTIME_LIFECYCLE.md](<docs/specs/API_RUNTIME_LIFECYCLE.md>) |
| Logging preparation and settlement | Explicit native preparation, operation-local bindings, captured required producers, process-owned writer and bounded optional publication/frontier. | [docs/specs/LOG_WRITE_SETTLEMENT.md](<docs/specs/LOG_WRITE_SETTLEMENT.md>) |
| Quality checker and coverage contract | Actual pytest markers, native checker limits and unchanged 89-percent coverage floor. | [docs/specs/QUALITY_CHECKER_CONTRACT.md](<docs/specs/QUALITY_CHECKER_CONTRACT.md>) |
| Runtime project roots | Invocation project selection and package-owned immutable assets. | [docs/specs/RUNTIME_PROJECT_ROOTS.md](<docs/specs/RUNTIME_PROJECT_ROOTS.md>) |
| Runtime result and lifecycle | Application results, owned runtime/model-stream lifetimes with typed provider errors, async fixture support execution and bounded demo/marshaller native publication. Synchronous fixture classes are retired in 0.7.1. | [docs/specs/RUNTIME_EXECUTION_RESULT_CONTRACT.md](<docs/specs/RUNTIME_EXECUTION_RESULT_CONTRACT.md>) |
| Trusted workload process lifetime | Trusted extension process lifetime; not hostile-code containment. | [docs/specs/SDK_WORKLOAD_PROCESS_LIFETIME.md](<docs/specs/SDK_WORKLOAD_PROCESS_LIFETIME.md>) |
| Settings and preference inputs | Bound configuration, persistence and migration. Setup persists runtime organization model defaults and project provider dotenv values; explicit dotenv bootstrap retains environment precedence and once-per-process semantics. | [docs/specs/SETTINGS_INPUT_OWNERSHIP.md](<docs/specs/SETTINGS_INPUT_OWNERSHIP.md>) |
| Runtime store binding | Durable store locations bind once; historical migration stays explicit. | [docs/specs/RUNTIME_STORE_BINDING.md](<docs/specs/RUNTIME_STORE_BINDING.md>) |
| Control-plane terminal authority | Verified terminal publication and explicit uncertainty. | [docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md](<docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md>) |

## Compatibility

| Surface | Current scope | Source |
| --- | --- | --- |
| Source wrapper and hidden rock alias | Deprecated python main.py and hidden --rock remain supported through 0.7.x. Removal requires a separate accepted contract delta and continued installed-root proof; no removal version is assigned. (condition-bound; no calendar expiry assigned) | [docs/projects/architectural-truth/ARCHITECTURE_EXCEPTION_REGISTER.json](<docs/projects/architectural-truth/ARCHITECTURE_EXCEPTION_REGISTER.json>) |
| Replay diagnostics alias | All supported callers use replay_turn_diagnostics() and the compatibility window is explicitly closed. (condition-bound; no calendar expiry assigned) | [docs/projects/architectural-truth/ARCHITECTURE_EXCEPTION_REGISTER.json](<docs/projects/architectural-truth/ARCHITECTURE_EXCEPTION_REGISTER.json>) |
| Flat runtime module aliases; removal version unassigned | The old flat \`orket.runtime.&lt;module&gt;\` imports remain one-release compatibility aliases. (condition-bound; no calendar expiry assigned) | [docs/ARCHITECTURE.md](<docs/ARCHITECTURE.md>) |
| Latest verification support artifact | All supported consumers use the canonical verification index and per-record artifacts. (condition-bound; no calendar expiry assigned) | [docs/projects/architectural-truth/ARCHITECTURE_EXCEPTION_REGISTER.json](<docs/projects/architectural-truth/ARCHITECTURE_EXCEPTION_REGISTER.json>) |

## Claim ceilings

| Surface | Current scope | Source |
| --- | --- | --- |
| Capability expansion remains proposed | proposed: Broader objective families, hostile-code containment and performance/cost claims require their own accepted gates. | [docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md](<docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md>) |
| Evidence graph projections | support_only: Projection and rendering do not acquire executor, approval, effect or terminal authority; canonical view tokens remain in the graph contract. | [docs/specs/RUN_EVIDENCE_GRAPH_V1.md](<docs/specs/RUN_EVIDENCE_GRAPH_V1.md>) |
| Trusted Python extensions | trusted_only: Process lifetime supervision does not establish OS containment of hostile extension code. | [docs/specs/SDK_WORKLOAD_PROCESS_LIFETIME.md](<docs/specs/SDK_WORKLOAD_PROCESS_LIFETIME.md>) |

## Proof availability

| Surface | Current scope | Source |
| --- | --- | --- |
| Current execution acceptance | unavailable; observed none; This index does not ingest portable runtime receipts. Source binding and marker classification are structural; recorded scoped results remain in the plan. | [docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md](<docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md>) |
| Installed, platform, provider and hosted acceptance | unavailable; observed none; No current installed, cross-platform, actual provider or hosted Quality proof is granted by this index. | [docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md](<docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md>) |

## Retained history

[Exact pre-cutover authority snapshot](<docs/architecture/history/CURRENT_AUTHORITY_PRE_MANIFEST_2026-09-28.md>). Historical statements are retained evidence, not current acceptance.
