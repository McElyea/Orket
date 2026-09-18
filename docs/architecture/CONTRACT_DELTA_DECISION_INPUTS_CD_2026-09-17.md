# Application-owned strategy composition

## Summary
- Change title: captured decision inputs and application-owned executable bindings.
- Owner: Orket Core.
- Date: 2026-09-17.
- Affected contracts: registry imports/settings, tool selection, model-client construction,
  loop limits and organization loading.

## Delta
- Current behavior before this change: registry/loop nodes read ambient settings;
  tool strategies receive ToolBox and return arbitrary executable bindings; model-client
  nodes construct providers; loader strategy mutates organization objects.
- New behavior: registry lives under application services and copies selection settings.
  Application composition captures environment and user settings once. Tool strategies
  receive frozen `ToolSelectionInput` and return a tuple of known names. Application
  rejects callable/mapping, unknown-name and duplicate outputs before dispatch and
  binds the selected names to its canonical implementations.
- `ModelClientFactory` owns provider/client construction over a copied environment;
  `ModelClientOptions` captures temperature/timeout before turn preparation awaits.
  The orchestrator also captures auditor-model fallback and loop inputs at construction.
- Loop strategy consumes frozen `LoopPolicyInputs`. ConfigLoader captures environment
  before its first read and applies organization overrides itself; its old mutation
  callback is retired. Path recommendations remain a strategy seam. Observations and
  inventory workers retain ownership through interruption; the sync bridge remains debt.
- Why now: four retained adverse controls demonstrate selection drift and inappropriate
  effect authority. These changes remove those seams while preserving application effects.

## Migration Plan
1. Compatibility window: immediate internal-boundary migration, no forwarding modules.
2. Import `DecisionNodeRegistry` and `build_decision_node_registry` from
   `orket.application.services.decision_node_registry`. The constructor consumes explicit
   settings; the builder captures runtime settings. Later environment changes require
   a new composition. Existing unknown strategy names retain their default fallback.
3. Replace tool `compose(toolbox)` with `select_tools(inputs) -> tuple[str, ...]`;
   executable tool registration belongs in trusted application composition. Do not put
   callbacks in the returned values. This is contract enforcement, not Python sandboxing.
4. Remove `ModelClientPolicyNode`, its builtin and registry slot. Nonempty
   `ORKET_MODEL_CLIENT_NODE` settings and organization `model_client_node` keys are
   rejected explicitly. Trusted application embeddings may supply their own factory
   through the orchestrator's `model_clients` seam. Update former `model_client_node`
   field access. Tool composition moved from the adapter module into application services.
5. Import `ToolBox` and `get_tool_map` from `orket.application.services.toolbox`;
   import tool families directly from `orket.adapters.tools.families`. The retired
   `orket.tools` module has no forwarding shim. ToolBox coordinates application effects;
   its actual relocation fixes the dependency boundary without a layer reclassification.
   The policy now admits the new pure `decision_inputs` value contract explicitly;
   allowed layer directions and exception policy are unchanged.
6. Update custom loop policies to consume explicit limit values. Remove loader
   `apply_organization_overrides`; application configuration owns name/vision overrides.
7. Validation gates: adverse controls, focused real file/HTTP behavior, broad source,
   installed Windows/Linux Python 3.11/3.12 parity, actual llama.cpp regression, changed
   Python Ruff, graph observation and docs/release checks. Exact results live in the
   canonical architectural-truth plan; pending gates must not be inferred as passed.

## Rollback Plan
1. Trigger: observed regression of tool dispatch, configuration or provider lifecycle.
2. Revert this contract and its implementation/tests together on an isolated candidate.
3. No durable store migration. Preserve evidence; do not restore retired effect authority
   silently or reinterpret retained failures as success.

## Versioning Decision
- Version bump type: patch under the existing pre-1.0 migration policy.
- Effective version/date: 0.6.10 / 2026-09-17.
- Downstream impact: internal embeddings and custom strategy implementations must migrate.
- Status: corrected selected source and all four fresh installed gates pass;
  actual llama.cpp regression and application-factory inference pass. See the plan
  for retained failures, exact counts, hashes and claim limits.
- Claim ceiling: this does not make all strategies immutable, eliminate ambient prompt
  policy reads, repair settings bootstrap/sync loader bridges, or prove OS containment.
  Those remain C/D work. Full lane acceptance and historical failure diagnoses remain open.
