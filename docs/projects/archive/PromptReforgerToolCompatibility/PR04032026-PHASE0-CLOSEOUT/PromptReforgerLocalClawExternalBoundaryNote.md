# Prompt Reforger / LocalClaw External Boundary Note

Owner: Orket Core
Status: Archived supporting draft
Last updated: 2026-04-03

## Status Note

This project-local boundary note is archived with the completed Phase 0 `PromptReforgerToolCompatibility` lane.

The canonical Orket-side service contract now lives at [docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md](docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md).

This note does not override the active spec or implementation plan.

## Purpose

This note defines the authority boundary between:

- Prompt Reforger as a generic bounded adaptation service hosted by Orket, and
- LocalClaw as an external harness and BFF consumer that evaluates specific OpenClaw tools.

This note exists to prevent authority drift between:

- generic service-host concerns owned by Orket,
- and external harness/orchestration concerns owned by LocalClaw.

## Proposed Future Architecture

The proposed future architecture is:

- **Prompt Reforger** would be a generic bounded adaptation service exposed by Orket.
- **Orket** would remain extension agnostic and would expose Prompt Reforger through a generic service surface.
- **LocalClaw** would be an external harness and BFF that evaluates local model runtimes against specific OpenClaw tool surfaces.
- **OpenClaw** would provide or anchor the tool surfaces that LocalClaw attacks through LocalClaw-owned bridged canonical tool contracts.

The proposed primary relationship is:

> LocalClaw may invoke Prompt Reforger as a bounded external service while LocalClaw retains ownership of tool attacks, bridge contracts, eval slices, orchestration, and matrix truth.

## Authority Split

### Prompt Reforger authority

If promoted, Prompt Reforger would be authoritative for:

- prompt-surface adaptation rules,
- prompt-facing compatibility-bundle generation derived from canonical tool and validator authority surfaces,
- helper-model boundary rules,
- micro-variation discipline,
- service acceptance and rejection rules,
- runtime-setting boundary for the service,
- requalification requirements for a produced compatibility bundle,
- generic service-surface semantics for Prompt Reforger.

If promoted, Prompt Reforger would **not** be authoritative for:

- LocalClaw BFF workflow policy,
- LocalClaw tool-harness workflow policy,
- LocalClaw matrix publication,
- LocalClaw bridge ownership,
- consumer-specific result composition,
- canonical tool contracts,
- canonical schemas,
- canonical validator behavior,
- enforcement authority.

### LocalClaw authority

If promoted, LocalClaw would be authoritative for:

- tool-first evaluation across model candidates,
- one-tool or narrow-tool-family attack workflow,
- bridge-first execution for OpenClaw tools,
- deterministic validator use inside the harness,
- fixed eval-slice comparison across model candidates,
- compatibility matrix publication,
- separation of prompt defects from bridge defects,
- separation of BFF defects from service defects,
- per-tool verdict recording,
- user-facing orchestration and presentation policy.

If promoted, LocalClaw would **not** be authoritative for:

- redefining Prompt Reforger service boundaries,
- expanding Prompt Reforger into provider-tuning,
- changing Prompt Reforger compatibility-bundle rules unilaterally,
- replacing bounded adaptation with ungoverned prompt experimentation,
- turning Orket into a LocalClaw-specific host.

## Controlled Dependency Direction

The proposed dependency direction is:

- OpenClaw tool surface -> LocalClaw bridged canonical tool contract
- LocalClaw BFF/harness -> owns tool attack orchestration and invokes generic service calls
- Orket generic service surface -> hosts Prompt Reforger
- Prompt Reforger -> returns bounded adaptation results to the consumer

The inverse direction is not authoritative.

In particular:

- Prompt Reforger does not define LocalClaw's matrix/reporting authority.
- Prompt Reforger does not own LocalClaw bridge contracts.
- LocalClaw does not redefine Prompt Reforger's service boundary.
- LocalClaw does not convert Orket into an app-specific orchestration host.

## Shared Truth Surfaces

The two documents are expected to agree on the following shared truths:

1. compatibility is not a vague model-quality claim;
2. compatibility is evaluated against a specific bridged tool surface and eval slice;
3. bridge contracts matter and must be frozen for meaningful comparison;
4. deterministic validators decide success, not model self-report;
5. unsupported outcomes are valid and must be recorded truthfully;
6. bounded micro-variation is preferred over broad rewrite by default;
7. Prompt Reforger remains subordinate to canonical tool/schema/validator authority.

## Shared Result Vocabulary

The service and harness may share the result vocabulary:

- `certified`
- `certified_with_limits`
- `unsupported`

That shared vocabulary does not merge authority.

Prompt Reforger owns service-result authority.

LocalClaw owns harness-verdict authority.

LocalClaw may adopt a Prompt Reforger result by reference only for the same exercised tuple and must record whether its verdict is `service_adopted` or `harness_derived`.

## Distinct Artifacts

The expected primary artifacts are:

### Prompt Reforger artifacts

- service-run records
- candidate mutation records
- adaptation scorecards
- qualifying compatibility bundles
- known boundaries
- requalification triggers

### LocalClaw artifacts

- tool-attack run records
- bridge contracts
- fixed eval slices
- deterministic validator results
- compatibility matrix
- per-tool verdicts across model candidates
- BFF orchestration records

A LocalClaw matrix entry may reference a Prompt Reforger compatibility bundle, but the matrix is not itself a Prompt Reforger artifact.

## Anti-drift Rules

The following anti-drift rules are proposed for future promotion:

1. Prompt Reforger must remain a bounded generic adaptation service, not a general evaluation harness.
2. LocalClaw must remain an external tool-first harness, not a vague prompt-tuning workspace inside Orket.
3. OpenClaw tool attacks must evaluate bridged canonical tool surfaces rather than raw external complexity wherever possible.
4. If a bridge defect is the main reason a tool attack fails, that failure must not be misreported as only a prompt defect.
5. If a BFF defect is the main reason a LocalClaw run fails, that failure must not be misreported as a Prompt Reforger defect.
6. If a Prompt Reforger run succeeds only under the observed runtime conditions, LocalClaw must not generalize that success beyond the exercised conditions.
7. If either the bridge contract, the service contract, or the runtime changes materially, prior compatibility results must be treated as requiring re-evaluation.
8. Repo documentation must not collapse generic service authority and external harness authority back into one vague story.

## Reading Order

For Orket-side service-boundary questions, read first:

1. `docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md`

For LocalClaw-side harness questions, read first:

1. `LocalClawExternalHarnessRequirements.md`

For implementation sequencing, read:

1. `Phase0ImplementationPlan.md`

If the project-local drafts appear to conflict during active lane planning, treat this note as the proposed split of authority for later design work. Active canonical authority still controls:

- Prompt Reforger would control generic adaptation-service truth.
- LocalClaw would control external harness and matrix truth.

## Proposed Decision Set

The following decisions are proposed by this note for future promotion:

1. Prompt Reforger and LocalClaw remain separate authority surfaces.
2. Prompt Reforger is a generic Orket service surface.
3. LocalClaw is an external harness and BFF consumer of that service.
4. LocalClaw may invoke Prompt Reforger, but that does not merge their authority.
5. Cross-model conclusions must be downstream summaries of tool-level harness results rather than the primary authority in Prompt Reforger.
6. Repo documentation must not collapse these two surfaces back into one vague story.
