# Prompt Reforger Generic Service Requirements

Owner: Orket Core
Status: Archived supporting draft
Last updated: 2026-04-03

## Status Note

This project-local requirements draft informed the extracted canonical Orket-side service contract at [docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md](docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md).

It remains useful for project-local rationale and source detail, but when it conflicts with the active spec or implementation plan, the active spec and plan control.

Archived implementation authority now lives at [docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/Phase0ImplementationPlan.md](docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/Phase0ImplementationPlan.md).

## 1. Purpose

This document defines Prompt Reforger as a generic bounded adaptation service hosted by Orket.

The purpose of this service is to let an external consumer submit a bridged canonical tool surface, a bounded eval slice, and an observed target runtime context so that Orket can perform prompt-only adaptation and return a truthful adaptation result.

This service is extension agnostic.

This document governs:

- the Prompt Reforger service boundary,
- the generic service surface expected to expose that service,
- the adaptation method,
- the acceptance and rejection rules for service results.

Prompt Reforger is not an authority boundary for canonical tool contracts, canonical schemas, canonical validators, or consumer-specific orchestration.

## 2. Scope

This document applies when all of the following are true:

- Orket is acting as a generic service host,
- an external consumer supplies a bounded adaptation request,
- the target runtime is a local model runtime,
- the request is tied to a bridged canonical tool surface and a bounded workload/eval slice,
- the service performs prompt and control refinement only.

This document does not authorize:

- app-specific orchestration inside Orket,
- consumer-specific bridge ownership inside Orket,
- provider-setting tuning as part of this service,
- provider-quality certification,
- raw external API exposure as the primary model-facing contract,
- unconstrained prompt experimentation,
- narrative success without measured evidence.

## 3. Service Definition

The service defined by this document is:

> Given a consumer-supplied bridged canonical tool surface, a scoped workload/eval slice, and an observed target runtime context, Prompt Reforger must attempt to produce a compatibility result by adapting prompt and control surfaces only.

The service result must be exactly one of:

- `certified`
- `certified_with_limits`
- `unsupported`

A service run must not claim success outside one of those result classes.

A qualifying run is a service run whose final result is either:

- `certified`
- `certified_with_limits`

`unsupported` is never a bundle-freeze outcome.

A `certified_with_limits` bundle may be frozen only when the narrowed acceptance envelope, unsupported cases, and fallback/review requirements are explicitly recorded in the frozen bundle.

### 3.1 Shared Vocabulary and Consumer Verdict Authority

Prompt Reforger defines the service result vocabulary for service runs.

External consumers may reuse that vocabulary for their own harness verdicts only under an explicit by-reference rule.

Shared class labels do not imply shared authority.

Prompt Reforger owns service-result authority.

External consumers own their own harness-verdict authority and must record whether a harness verdict is adopted by reference from a Prompt Reforger service result or derived independently from additional consumer-side evidence or failure conditions.

Prompt Reforger does not control consumer-side verdict authority merely because the class labels are shared.

## 4. Generic Service Surface Thesis

Prompt Reforger must be exposed through a generic Orket service surface rather than a consumer-specific endpoint tree.

The service surface must be usable by extension consumers and external BFF layers without requiring Orket to become application-specific.

The service surface may be exposed through:

- generic runtime/service endpoints,
- SDK parity helpers,
- or both.

SDK support and generic endpoint support must remain semantically aligned.

## 5. Consumer Boundary Thesis

Prompt Reforger must not primarily adapt a model to a raw external API.

The consuming side is expected to supply or reference a bridged canonical tool surface that narrows external complexity into a stable model-facing contract.

The consuming side owns:

- app-specific orchestration,
- bridge ownership,
- eval-slice ownership,
- matrix/reporting ownership,
- consumer-specific presentation and workflow policy.

Prompt Reforger consumes those inputs as a bounded service. It does not absorb them into Orket authority.

## 6. Core Operating Thesis

Prompt Reforger must assume that most useful adaptation gains come from small, isolated prompt or control changes rather than broad prompt rewrites.

Broad prompt reform is an escalation path, not the default operating mode.

The default operating mode must prefer bounded micro-variation that allows the effect of each change to be measured and attributed.

The service must optimize prompt and control surfaces against the observed runtime conditions supplied by the consumer. It must not attempt to optimize provider or runtime settings as part of the normal adaptation loop.

## 7. Normative Definitions

### 7.1 Consumer

An external caller that invokes Prompt Reforger through a generic Orket service surface.

A consumer may be:

- an external BFF,
- an external extension runtime,
- an SDK client,
- or another extension-agnostic integration layer.

### 7.2 Service request

A bounded Prompt Reforger invocation that includes, directly or by stable reference:

- consumer identity when available,
- a bridged canonical tool surface or reference,
- a workload/eval slice or reference,
- a target runtime context,
- a baseline prompt/control surface,
- acceptance thresholds.

### 7.3 Service run

One recorded execution of Prompt Reforger for one service request.

### 7.4 Bridged canonical tool surface

The controlled model-facing contract used during adaptation.

A bridged canonical tool surface should narrow external complexity into stable fields, stable errors, and stable expected outcomes.

### 7.5 Workload/eval slice

The fixed set of representative and adversarial cases used to compare baseline and candidate bundles.

### 7.6 Target runtime context

The observed execution context used during adaptation and evaluation, including any of the following when observable:

- provider identity,
- model name,
- version, tag, or quant identifier,
- adapter or endpoint identity,
- surfaced runtime metadata.

### 7.7 Compatibility bundle

The frozen output artifact for a qualifying service run.

A compatibility bundle includes:

- frozen prompt surfaces,
- frozen prompt-facing tool instructions derived from the canonical contract,
- frozen examples,
- frozen prompt-facing repair and retry guidance subordinate to canonical validator outcomes,
- references to the canonical tool and validator versions used during evaluation,
- certification evidence,
- known boundaries,
- observed runtime context when available.

A compatibility bundle remains subordinate to canonical tool and validator authority. It must not contradict or replace canonical tool contracts, canonical schemas, or canonical validator behavior.

### 7.8 Helper model

A stronger model used to propose candidate mutations, cluster failures, or suggest next-step refinements.

The helper model is not runtime authority and cannot declare certification.

## 8. Protected Properties

The service defined by this document protects the following properties:

1. **Extension-agnostic service truth**
   - Prompt Reforger remains a generic Orket service surface rather than a consumer-specific harness.

2. **Runtime-specific truth**
   - compatibility claims must stay attached to the runtime conditions actually exercised during evaluation.

3. **Tool/bridge-specific truth**
   - compatibility claims must stay attached to the exact bridged canonical tool surface and workload/eval slice used during evaluation.

4. **Measured selection authority**
   - accepted mutations must be chosen by eval evidence rather than intuition or narrative preference.

5. **Fail-closed certification**
   - unsupported pairings must be rejected rather than represented as generally usable.

6. **Controlled search space**
   - prompt/control mutation must remain bounded and measurable.

7. **Consumer-owned orchestration boundary**
   - external orchestration, matrix publication, and consumer workflow policy remain outside Orket service authority.

## 9. Core Requirements

### R1. Generic service exposure

Prompt Reforger must be reachable through a generic Orket service surface.

That service surface must not encode LocalClaw-specific or other consumer-specific product assumptions.

### R2. SDK parity

If an SDK surface exists for Prompt Reforger, it must remain semantically aligned with the generic service surface.

SDK helpers must not expose a wider authority boundary than the generic service endpoints.

### R3. Exact request binding

Every service run must bind to:

- one service request,
- one bridged canonical tool surface,
- one workload/eval slice,
- one observed target runtime context.

A result produced for one tuple must not be reused as authority for a materially different tuple without re-evaluation.

### R4. Consumer-supplied bridge

Prompt Reforger must adapt to a bridged canonical tool surface rather than directly to a raw external API whenever the consumer supplies such a bridge.

If the raw external API is the only available surface, the run evidence must record that the bridge is incomplete or absent.

### R5. Canonical authority subordination

Prompt Reforger may generate and evaluate prompt-facing representations derived from canonical tool and validator authority surfaces for the purpose of model adaptation.

Any prompt-facing representation used by Prompt Reforger must remain subordinate to, and must not contradict or replace, the canonical tool and validator authority surfaces.

### R6. Evidence-backed result

Every service run must produce, at minimum:

- baseline metrics,
- candidate mutation records,
- per-candidate eval outcomes,
- selected bundle or rejection result,
- explicit acceptance or rejection reason,
- observed runtime context when available.

### R7. Small-delta default

The default mutation strategy must prefer bounded micro-variations such as:

- wording changes,
- instruction ordering changes,
- tool description tightening,
- prompt-facing schema phrasing changes derived from the canonical contract,
- field explanation changes,
- example substitution,
- retry wording changes,
- repair wording changes.

A candidate should change one variable at a time unless a documented escalation rule is active.

### R8. Broad-rewrite escalation only

Broad prompt reform must not be the default strategy.

Broad rewrite is allowed only when one or more of the following are true:

- multiple bounded rounds have stalled,
- failures span unrelated categories,
- the baseline prompt architecture is structurally invalid,
- the baseline is catastrophically nonfunctional.

The escalation trigger must be recorded in the run evidence.

### R9. Helper-model boundary

A helper model may be used to:

- propose candidate mutations,
- cluster failure cases,
- suggest next-step refinements,
- propose bounded repair patterns.

A helper model must not:

- declare certification,
- override deterministic validators,
- replace measured acceptance thresholds,
- become runtime truth authority.

### R10. Failure taxonomy

Prompt Reforger must classify observed failures into stable categories sufficient to drive targeted mutation.

At minimum, the taxonomy should support:

- wrong tool selection,
- missing tool call,
- malformed arguments,
- hallucinated arguments,
- sequencing failure,
- schema overload or schema confusion,
- repair-loop failure,
- silent wrong-success.

Failure categories used for comparison or certification must map to a stable canonical error authority surface.

Narrative failure labels may be used for human readability, but they are not sufficient as the sole comparison surface.

Where a canonical `error_code` registry exists, Prompt Reforger reporting must bind failure classification to that registry or to a documented subordinate mapping.

Each evaluated candidate must record:

- canonical `error_code` when available,
- narrative failure label,
- source authority surface,
- whether the failure is attributed to prompt behavior, bridge behavior, validator behavior, or downstream system behavior.

### R11. Replayable comparison slice

Each candidate must be evaluated against a fixed comparison slice sufficient to measure both improvement and regression relative to baseline.

A candidate must not be selected solely on anecdotal examples.

### R12. Result classes and bundle freeze

If the required thresholds are not met, Prompt Reforger must return either:

- `certified_with_limits`
- `unsupported`

The service must fail closed rather than imply general usability.

A compatibility bundle may be frozen only for qualifying runs that actually clear the required acceptance thresholds.

### R13. Provider and runtime settings out of scope

Provider and runtime settings are outside the tuning and certification boundary of Prompt Reforger.

The service must assume that provider and runtime settings are consumer-owned preconditions.

Prompt Reforger may attempt to produce a working result under those conditions, but it must not claim that those settings were optimized or certified by the service.

### R14. Prompt-only search space

Prompt Reforger must restrict its adaptation loop to prompt and control mutations.

Provider or runtime knob mutation is out of scope for this service.

### R15. Runtime-condition warning

Every certified result must make clear that changing provider or runtime settings later may affect the behavior and quality of the resulting compatibility bundle.

### R16. Consumer-boundary warning

A successful Prompt Reforger result must not be represented as proof of:

- consumer harness quality,
- bridge quality outside the exercised request,
- matrix-level model ranking,
- or app-level orchestration correctness.

Those remain consumer-side concerns.

### R17. Drift sensitivity

A compatibility bundle must declare requalification triggers.

At minimum, requalification triggers should include:

- target runtime change,
- provider change when observable,
- adapter change when observable,
- bridge contract change,
- tool schema change,
- validator change,
- sustained regression beyond threshold,
- consumer runtime-setting changes known to affect behavior.

## 10. Operating Modes

### Mode A - Baseline evaluate

The service evaluates the supplied baseline prompt/control surface against the supplied bridge and eval slice and returns measured results without freezing a compatibility bundle unless thresholds are already met.

### Mode B - Bounded adapt

The service performs bounded prompt-only mutation and evaluation, then returns one of:

- `certified`
- `certified_with_limits`
- `unsupported`

This mode may freeze a compatibility bundle only for qualifying runs.

No other mode is authorized by this document.

## 11. Runtime Boundary

### P1. Consumer-owned settings

Prompt Reforger does not tune, optimize, or certify provider-level or runtime-level settings.

Those settings are consumer-owned preconditions outside the service boundary.

### P2. Best-effort under supplied conditions

Prompt Reforger must do its best to produce a useful result under the consumer's existing runtime conditions.

A successful result means the bundle worked under the observed evaluation conditions. It does not mean the service validated every possible configuration choice behind those conditions.

### P3. Observed runtime context recording

Although provider and runtime settings are out of scope for tuning, the observed runtime context must be recorded as run evidence when available.

This recording exists for diagnosis, replay, and drift analysis. It does not expand the service boundary to provider tuning.

### P4. No provider-quality claims

Prompt Reforger must not claim that a bundle is valid across arbitrary providers, arbitrary settings, or arbitrary hosts.

The service result is valid only for the execution conditions actually exercised during evaluation.

### P5. Connection compatibility is not certification

A provider may be used by the service if Orket can execute against it through a supported adapter or service path.

This establishes connection compatibility only. It does not establish provider-setting support, provider-quality certification, or cross-provider portability.

## 12. Output Requirements

Prompt Reforger service outputs must distinguish between:

- service-run artifacts for every evaluated run,
- candidate mutation records,
- qualifying compatibility bundles only.

The service must not manufacture a qualifying bundle when the truthful result is `unsupported`.

Consumer-owned matrix or harness artifacts are out of scope for Prompt Reforger outputs.

## 13. Non-goals

Prompt Reforger generic service mode does not aim to:

- make every local model work,
- erase provider differences,
- guarantee portability across runtime hosts,
- optimize provider settings,
- certify provider-quality choices,
- replace deterministic validation with model judgment,
- treat broad prompt rewrites as the normal path,
- replace the need for a stable external bridge,
- own consumer-specific orchestration or matrix publication.

## 14. Proposed Decision Set

The following decisions are proposed by this document for future promotion:

1. Prompt Reforger is a generic Orket service surface, not a consumer-specific harness.
2. Prompt Reforger is not an authority boundary for canonical tool contracts, canonical schemas, or canonical validators.
3. The default and only authorized adaptation method is measured micro-variation on prompt and control surfaces.
4. A helper model may propose changes but cannot declare success.
5. Certification is bridge-specific, workload/eval-slice-specific, and tied to the runtime conditions actually exercised during evaluation.
6. Provider and runtime settings are consumer-owned and outside the tuning boundary of this service.
7. Consumer-side orchestration, bridge ownership, and matrix publication remain outside Prompt Reforger authority.
8. A compatibility bundle is frozen only for qualifying runs that actually clear the acceptance thresholds.
