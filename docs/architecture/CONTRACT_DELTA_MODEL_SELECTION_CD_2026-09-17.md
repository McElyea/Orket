# Explicit model-selection inputs

## Summary
- Change title: immutable model recommendations with application-owned preparation.
- Owner: Orket Core.
- Date: 2026-09-17.
- Affected contracts: prompt strategy, model selection, compliance observations,
  orchestration preparation, API model assignments, driver and preview selection.

## Delta
- Before: the builtin prompt strategy invokes a mutable `ModelSelector` object.
  Selection reads ambient environment, borrows caller settings/organization and
  reads score files synchronously. A hidden last-decision field supplies telemetry.
- Target: application captures environment, organization rules and caller settings
  before awaiting preparation. Default preference/settings reads and configured
  score-file reads have owned asynchronous lifetimes. Each prepared selection
  retains immutable values and explicit score-source observation/provenance.
- Prompt strategies receive a frozen value input and return a nonempty model name.
  They receive no selector, organization, asset object or file-reading capability.
  Application applies compliance policy and returns an immutable decision together
  with the model, rather than reading mutable last-call state from a strategy.
- Preserve default precedence: explicit override, asset override, environment,
  user preference, organization role/default, canonical provider model default.
  Explicit operator override remains highest priority and bypasses compliance
  demotion. Default role aliases and dialect mappings retain their current meaning.
- Existing blocked-model and minimum-score demotion remain advisory model-selection
  policy, not workload/provider admission. Unknown scores retain `score_missing`.
  Unavailable or invalid configured score reports must be explicitly represented
  and logged, not silently treated as an observed empty report or verified compliance.
  Inline scores remain available when the optional report cannot be observed.
- Score bytes are read once per preparation, with a digest of those same bytes;
  there is no path-keyed mutable cache. A new preparation observes later file changes.
  Caller cancellation retains any admitted settings/read worker until it settles.

## Migration Plan
1. Retire the effectful `ModelSelector` and last-decision API without a forwarding
   shim. Keep unrelated model inventory behavior separate.
2. Replace `select_model(role, asset_config, override)` with selection over the frozen
   input. Remove the builtin's selector constructor argument and signature probing.
3. Orchestration, API assignment queries and preview await application preparation.
   The driver bootstrap uses an explicit synchronous boundary outside the event
   loop; API construction of that synchronous bootstrap must retain its worker.
4. Move `orket.preview.PreviewBuilder` to
   `orket.application.services.preview_service.PreviewBuilder`, without a forwarding
   module. Preview file/config/prompt workers retain their lifetimes; API callers
   await host construction. API chat drivers close their provider transport after
   each invocation, including failures and interrupted construction.
5. Preserve public assignment response fields and report any optional score-source
   observation limitation explicitly. Keep chosen-model telemetry tied to its
   returned decision, including custom strategy recommendations.
6. Validate mutation isolation, real score-file changes/failures, worker cancellation,
   responsiveness, selection precedence, application/API/driver/preview composition,
   installed package parity and actual llama.cpp behavior before accepting the change.

## Scope and limitations
- Canonical default settings readers run on owned workers, preserving existing
  runtime settings context and legacy migration. This does not eliminate their
  process-global path/cache authority or make two default files an atomic snapshot.
- Nonfinite score values are unobserved, not `score_ok`. Invalid report rows yield
  `partial` plus a count; valid rows and inline scores remain available.
- A configured report is prepared once even if a later explicit override makes its
  advisory scores irrelevant. Missing/read/parse failures remain disclosed and do
  not override explicit model selection.
- Custom Python strategies are not an OS containment boundary. The frozen input
  removes supplied selector/file capabilities; unrelated ambient prompt-policy,
  planner/router and loader settings boundaries remain C/D work.
- Source controls include actual local files, ASGI and controlled TCP HTTP;
  controlled HTTP is not model inference. Separate installed/native and actual
  llama.cpp observations are bound in the canonical remediation plan.

## Rollback Plan
1. Trigger: observed regression in model assignment or provider preparation.
2. Revert contracts, callers and proof together on an isolated candidate.
3. Preserve all failed and passing observations; no durable store migration.

## Versioning Decision
- Version bump type: patch under the pre-1.0 internal migration policy.
- Effective version/date: 0.6.11 / 2026-09-17.
- Downstream impact: internal embeddings and custom prompt strategies must migrate.
- Status: scoped local checkpoint; 1,853 source/four-cell installed cases and actual llama.cpp proof pass.
- Claim ceiling: no whole-strategy purity, complete prompt-policy migration,
  OS containment, capability admission, release readiness or whole-lane acceptance.
