# LocalClaw External Harness Requirements

Owner: LocalClaw
Status: Archived supporting draft
Last updated: 2026-04-03

## Status Note

This document is a project-local external harness draft archived with the completed `PromptReforgerToolCompatibility` Phase 0 lane.

It is not canonical authority for Orket internals. Where this document conflicts with Orket's active canonical authority, Orket's active canonical authority controls the Orket side of the boundary.

This document governs the LocalClaw-side harness and BFF behavior only. It does not override the active Orket spec or implementation plan.

## 1. Purpose

This document defines the LocalClaw external tool-compatibility harness.

The purpose of this harness is to determine, for a specific OpenClaw tool or narrow tool family, which local model runtimes can use that tool correctly, under what known limits, while optionally invoking Prompt Reforger through Orket's generic service surface as a bounded adaptation service.

This harness exists to attack specific tools, not to produce vague global model rankings.

## 2. Scope

This document applies when all of the following are true:

- LocalClaw is operating as an external consumer of Orket,
- the target surface is an OpenClaw tool or narrow OpenClaw tool family,
- LocalClaw owns the bridged canonical tool contract for that attack,
- the execution runtime is a local model runtime,
- the outcome is intended to be measured, compared, and recorded.

This document does not authorize:

- treating Orket as application-specific orchestration,
- raw external API exposure as the default model-facing tool contract,
- narrative compatibility claims without deterministic validation,
- one-off happy-path success as compatibility proof,
- broad model-quality claims without tool-level evidence.

## 3. System Definition

The LocalClaw external harness is:

> A BFF-owned external harness that evaluates specific local model runtimes against specific OpenClaw tool surfaces through bridged canonical contracts, may invoke Prompt Reforger through Orket's generic service surface for bounded prompt/control adaptation, and records per-tool compatibility outcomes as evidence-backed results.

## 4. Core Thesis

LocalClaw must evaluate compatibility per tool, not primarily per model.

The primary unit of truth is:

- one target model runtime,
- one OpenClaw tool or narrow tool family,
- one bridge contract,
- one eval slice,
- one measured result.

Global model conclusions, if produced at all, must be downstream summaries of tool-level results rather than the primary authority surface.

## 5. BFF Boundary Thesis

The LocalClaw BFF owns application-facing orchestration for LocalClaw.

That includes:

- external request handling,
- user-facing workflow policy,
- bridge selection,
- Prompt Reforger invocation sequencing,
- result composition and presentation,
- matrix/report publication.

Orket does not own those concerns.

## 6. Normative Definitions

### 6.1 OpenClaw tool surface

The specific tool call or narrow tool family under evaluation.

### 6.2 Bridged tool contract

The model-facing canonical contract that narrows the OpenClaw or downstream external semantics into stable fields, stable errors, and stable expected outcomes.

### 6.3 Tool attack

A bounded evaluation effort focused on one OpenClaw tool surface or narrow tool family for one target model runtime.

A tool attack may include baseline execution, bounded Prompt Reforger invocation, retest, and final classification.

### 6.4 Model candidate

A local model runtime selected for evaluation against a specific tool surface.

### 6.5 Harness run

A single recorded evaluation of one model candidate against one OpenClaw tool surface under one bridge contract and one eval slice.

### 6.6 Compatibility matrix

The recorded cross-product of tool-level results across model candidates.

### 6.7 Tool-level verdict

One of:

- `certified`
- `certified_with_limits`
- `unsupported`

### 6.8 BFF orchestration record

The LocalClaw-side record of which bridge, eval slice, Prompt Reforger service mode, and result composition path were used for a given tool attack.

## 7. Protected Properties

The harness defined by this document protects the following properties:

1. **Tool-level truth**
   - compatibility claims must stay attached to the exact tool or narrow tool family evaluated.

2. **Bridge-level truth**
   - compatibility claims must stay attached to the exact bridge contract used by the harness.

3. **Runtime-specific truth**
   - results must stay attached to the specific local model runtime actually exercised.

4. **BFF-owned orchestration truth**
   - app-specific orchestration remains LocalClaw-owned rather than silently pushed into Orket.

5. **Measured comparability**
   - results must be comparable across models only when the eval slice and bridge contract are materially the same.

6. **Deterministic validation authority**
   - compatibility must be decided by validators and measured outcomes, not model self-report.

7. **Fail-closed reporting**
   - unsupported tool/model pairings must be recorded as such rather than glossed over.

## 8. Core Requirements

### R1. External-consumer boundary

LocalClaw must consume Prompt Reforger as an external Orket service.

LocalClaw must not require Orket to become LocalClaw-specific in order to perform tool attacks.

### R2. BFF authority

The LocalClaw BFF must remain authoritative for:

- tool-attack orchestration,
- bridge selection and ownership,
- eval-slice selection and ownership,
- Prompt Reforger invocation sequencing,
- compatibility matrix publication,
- user-facing result composition.

### R3. Bridge-first execution

Every harness run must execute through a bridged tool contract.

If a stable bridge does not exist, the harness must record that the bridge is incomplete or absent.

### R4. Canonical identity binding

Every harness run must bind to:

- one model candidate,
- one OpenClaw tool surface,
- one bridge contract,
- one eval slice.

A result from one tuple must not be reused as authority for a materially different tuple without re-evaluation.

### R5. Baseline first

Each tool attack must begin with a baseline run before any Prompt Reforger adaptation is attempted.

### R6. Deterministic validator requirement

Every harness run must use deterministic validators sufficient to assess:

- correct tool selection,
- valid argument shape,
- accepted invocation,
- normalized result correctness,
- task outcome correctness,
- silent wrong-success detection when applicable.

### R7. Fixed eval slice

Each tool attack must run against a fixed eval slice sufficient to test both happy-path and non-happy-path behavior.

At minimum, the eval slice should include, where relevant:

- happy path,
- near-miss path,
- malformed argument path,
- ambiguous-input path,
- unsupported-operation path,
- repair path,
- refusal or no-call path.

### R8. Prompt Reforger integration

LocalClaw may use Prompt Reforger to attempt bounded prompt/control adaptation for a tool attack.

When Prompt Reforger is used, the harness must record:

- the Prompt Reforger service request or stable reference,
- baseline bundle or baseline prompt/control surface,
- candidate results,
- winning compatibility bundle reference if any,
- final reason for selection or rejection.

### R9. Micro-variation bias

When adaptation is attempted, the harness should prefer measured micro-variation rather than broad prompt reform.

Broad prompt reform is permitted only when the service boundary in the Prompt Reforger requirements allows escalation.

### R10. Tool-level failure taxonomy

The harness must classify observed failures into stable categories sufficient to compare models and guide adaptation.

At minimum, the taxonomy should support:

- wrong tool selection,
- missing tool call,
- malformed arguments,
- hallucinated arguments,
- sequencing failure,
- bridge misunderstanding,
- repair-loop failure,
- silent wrong-success.

Failure categories used for comparison or certification must map to a stable canonical error authority surface.

Narrative failure labels may be used for human readability, but they are not sufficient as the sole comparison surface.

Where a canonical `error_code` registry exists, harness reporting must bind failure classification to that registry or to a documented subordinate mapping.

### R11. Tool-level outcome classes

Every completed harness run must end in exactly one verdict:

- `certified`
- `certified_with_limits`
- `unsupported`

A tool attack must not end in narrative "looks promising" without one of those outcome classes.

### R11A. Verdict-source rule

LocalClaw may adopt Prompt Reforger's result classes by reference for the same exercised tuple only when all of the following are true:

- the bridge contract is materially the same,
- the eval slice is materially the same,
- the observed runtime context is materially the same,
- the referenced Prompt Reforger service run is the one actually used for that LocalClaw tuple,
- no additional LocalClaw-side failure condition changes the tuple assessment.

When those conditions hold, the harness must record:

- the shared class label,
- `verdict_source: service_adopted`,
- `service_result_ref`.

Otherwise the harness must derive its own verdict and must record:

- the harness verdict class,
- `verdict_source: harness_derived`,
- `service_result_ref` when a Prompt Reforger run informed the final harness verdict.

Shared class labels do not merge authority. Prompt Reforger owns service-result authority. LocalClaw owns harness-verdict authority.

### R12. Compatibility matrix artifact

The harness must publish or persist a compatibility matrix artifact that records, per evaluated tuple:

- model candidate identity,
- OpenClaw tool identity,
- bridge contract identity,
- eval slice identity,
- verdict,
- `verdict_source`,
- `service_result_ref` when applicable,
- baseline score,
- post-adaptation score when applicable,
- winning Prompt Reforger bundle reference when applicable,
- known limits,
- observed runtime context when available,
- canonical `error_code` when available,
- narrative failure label,
- source authority surface,
- whether the failure is attributed to prompt behavior, bridge behavior, validator behavior, downstream system behavior, or BFF/orchestration behavior.

### R13. No raw external complexity leakage

The harness should not require the model to reason about raw downstream API complexity when a bridge can absorb that complexity instead.

If repeated failures are caused primarily by raw external semantics leaking through the bridge, that should be recorded as a bridge-boundary defect rather than treated only as a prompt defect.

### R14. Orket-boundary truth

LocalClaw must not represent a successful Prompt Reforger result as proof that:

- LocalClaw orchestration is correct everywhere,
- the bridge is generally correct outside the exercised slice,
- or the LocalClaw matrix is authoritative beyond the exercised tuples.

### R15. Bridge drift invalidates results

If the bridge contract changes materially, prior tool-level compatibility results must be treated as invalid until re-evaluated.

### R16. Runtime drift warning

If the model runtime changes materially, prior tool-level compatibility results must be treated as requiring re-evaluation.

### R17. Service drift warning

If Prompt Reforger service semantics or canonical contract references used by the harness change materially, prior harness results must be treated as requiring re-evaluation.

## 9. Workflow Requirements

### W1. Select one tool target

A tool attack must begin with one target tool or narrow tool family.

### W2. Freeze bridge and eval slice

Before comparison or adaptation, the bridge contract and eval slice must be frozen for that attack.

### W3. Run baseline across model candidates

Model candidates should be measured against the same attack conditions to preserve comparability.

### W4. Adapt only when useful

Prompt/control adaptation should be attempted only when the baseline result indicates a plausible rescue path.

### W5. Keep tool, bridge, BFF, and downstream defects separate

The harness must distinguish between:

- model/prompt failure,
- bridge-contract failure,
- validator defect,
- downstream external-system defect,
- BFF/orchestration defect.

### W6. Freeze winning bundle on success

If a model candidate clears thresholds after Prompt Reforger-assisted adaptation, the winning bundle reference must be frozen and linked to that exact tool/runtime tuple.

## 10. Acceptance Requirements

A tool/model tuple may be marked `certified` only if all of the following are true:

- the tuple passes the required eval slice,
- deterministic validators confirm correct invocation and outcome behavior,
- silent wrong-success is absent or within explicitly allowed threshold,
- known boundaries are recorded,
- the result is tied to the exact bridge contract and runtime actually exercised.

A tool/model tuple may be marked `certified_with_limits` only if all of the following are true:

- the tuple is useful within a narrowed envelope,
- unsupported patterns are explicitly recorded,
- fallback or review requirements are explicit,
- the result is tied to the exact bridge contract and runtime actually exercised.

Otherwise the result must be `unsupported`.

## 11. Non-goals

This harness does not aim to:

- make Orket application-specific,
- push LocalClaw BFF ownership into Orket,
- produce generic model rankings without tool context,
- replace bridge design with prompt text,
- prove universal OpenClaw compatibility from one successful tool attack,
- use one good example as proof,
- hide unsupported pairings.

## 12. Proposed Decision Set

The following decisions are proposed by this document for future promotion:

1. LocalClaw remains an external harness and BFF consumer of Orket.
2. The primary unit of truth is `model x tool x bridge x eval slice`.
3. Compatibility must be decided by deterministic validation and measured outcomes.
4. Prompt Reforger may be used as the bounded adaptation engine inside the harness.
5. The harness exists to attack specific tools, not to generate vague global model rankings.
6. Bridge defects, BFF defects, and prompt defects must be distinguished.
7. Compatibility results must be published as a matrix artifact, not left as narrative impressions.
