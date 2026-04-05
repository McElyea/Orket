# Prompt Reforger Generic Service Surface Phase 0 Implementation Plan

Owner: Orket Core
Status: Archived
Last updated: 2026-04-03

## Status Note

This document is the archived Phase 0 implementation plan for the completed `PromptReforgerToolCompatibility` lane.

The durable Orket-side service contract extracted from Workstream 0 lives at [docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md](docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md).

Closeout authority now lives at [docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/CLOSEOUT.md](docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/CLOSEOUT.md).

## 1. Purpose

This document defines a concrete Phase 0 implementation plan for Prompt Reforger as a generic Orket service surface.

The purpose of Phase 0 is to prove one end-to-end bounded service slice for one consumer-supplied bridged tool surface and one bounded eval slice through an extension-agnostic Orket service host.

This plan exists to turn the Prompt Reforger project requirements into a bounded implementation path without collapsing the boundary between:

- Prompt Reforger as a generic Orket service, and
- external consumers such as LocalClaw that own harness logic, bridge ownership, eval ownership, and orchestration.

## 2. Phase 0 Objective

Phase 0 is complete only when all of the following are true for one selected proof slice:

- a generic Prompt Reforger service surface exists,
- a stable request/result contract exists,
- a service run model exists,
- a bounded baseline evaluation path exists,
- a bounded mutation path exists,
- the service emits deterministic run artifacts for every evaluated service run,
- every evaluated service run ends in exactly one result class:
  - `certified`
  - `certified_with_limits`
  - `unsupported`,
- a compatibility bundle is frozen only for qualifying service runs that clear the required acceptance thresholds,
- at least one external-consumer proof path can invoke the service through the generic surface without requiring Orket to become consumer-specific.

A qualifying service run is a service run whose final result is either:

- `certified`
- `certified_with_limits`

`unsupported` is never a bundle-freeze outcome.

A `certified_with_limits` bundle may be frozen only when the narrowed acceptance envelope, unsupported cases, and fallback/review requirements are explicitly recorded in the frozen bundle.

If no run qualifies for bundle freeze, the truthful Phase 0 outcome is one or more `unsupported` or non-qualifying results without manufacturing a qualifying bundle.

Phase 0 does not attempt to prove:

- broad OpenClaw compatibility,
- LocalClaw matrix publication inside Orket,
- provider-setting optimization,
- app-specific BFF orchestration inside Orket.

## 2A. Workstream 0 Baseline

Workstream 0 is complete for this active lane and freezes the following entry conditions for later execution:

1. The first proof slice is one LocalClaw-style external consumer request over one consumer-supplied bridged tool surface, one bounded eval slice, and one observed runtime context. This freeze does not claim matrix-level coverage.
2. The canonical Orket-side service contract is [docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md](docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md).
3. The frozen request and result envelope examples live at:
   - [docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/request_examples.jsonl](docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/request_examples.jsonl)
   - [docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/result_examples.jsonl](docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/result_examples.jsonl)
4. SDK parity is deferred at this baseline. Workstream 1 may reopen that decision only if the generic service surface actually exposes SDK helpers.
5. The existing bounded `orket.reforger` tool family is the structural anchor for later Phase 0 service promotion, but this baseline does not yet present that tool family as the final Prompt Reforger service authority.

## 3. Locked Constraints

The following implementation constraints are locked for Phase 0:

1. Prompt Reforger remains a prompt-only adaptation service.
2. Prompt Reforger is not an authority boundary for canonical tool contracts, canonical schemas, or canonical validators.
3. Orket remains extension agnostic.
4. The service surface must remain generic rather than LocalClaw-specific.
5. Provider and runtime settings remain consumer-owned and out of scope for tuning.
6. Unsupported outcomes are valid and must be recorded truthfully.
7. Every evaluated service run must emit run artifacts even when the final result is `unsupported`.
8. Frozen compatibility bundles are produced only for qualifying service runs.
9. Live proof must record observed path, observed result, and the exact blocker when live proof cannot run.
10. LocalClaw-specific harness logic, matrix publication, and BFF orchestration remain outside this Orket implementation plan.

## 4. Phase 0 Scope

Phase 0 includes:

- one generic Prompt Reforger service contract,
- one generic invocation path through Orket,
- one bounded evaluation engine,
- one bounded mutation engine,
- one service run model and artifact family,
- one compatibility bundle artifact format for qualifying runs only,
- one external-consumer proof path,
- one SDK-parity proof path if SDK support is exposed in Phase 0.

Phase 0 excludes:

- LocalClaw harness implementation inside Orket,
- LocalClaw matrix/report publication inside Orket,
- LocalClaw bridge ownership inside Orket,
- provider-setting tuning,
- raw external API exposure as the primary model-facing contract,
- broad prompt-rewrite systems,
- canonical authority promotion.

## 5. Archived Lane Path

The archived implementation-plan record for this phase is:

- `docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/Phase0ImplementationPlan.md`

The active roadmap no longer points to this path because the lane is complete and archived.

## 6. Repository Shape

The implementation should preserve the service-host boundary.

### Suggested code layout

- `orket/reforger/`
- existing generic extension/runtime service host layer
- `tests/reforger/`
- `tests/generic_service_surface/`

Do not create `orket/localclaw/` or `tests/localclaw/` in Orket for this phase.

### Suggested project source layout

- `docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/Phase0ImplementationPlan.md`
- `docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/PromptReforgerGenericServiceRequirements.md`
- `docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/LocalClawExternalHarnessRequirements.md`
- `docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/PromptReforgerLocalClawExternalBoundaryNote.md`
- `docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/request_examples.jsonl`
- `docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/result_examples.jsonl`
- `docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md`

Do not add small project-subfolder `README.md` files by default.

## 7. Runtime Output Rules

Phase 0 does not create a new generic top-level `artifacts/` authority root.

Instead:

1. Any new script that writes rerunnable JSON results must use the repo's canonical diff-ledger write helpers.
2. Each script must declare one stable canonical output path.
3. Candidate proof artifacts produced by this phase must default to `benchmarks/staging/` until explicit publication approval exists.
4. If a rerunnable result is needed, it must be written to a stable repo-aligned canonical path rather than an ad hoc output root.
5. Staging artifacts must follow the repo's existing staging workflow.
6. Published artifacts are out of scope unless explicitly approved.

### Suggested output families

#### Prompt Reforger staging outputs

- `benchmarks/staging/General/reforger_service_run_<run_id>.json`
- `benchmarks/staging/General/reforger_service_run_<run_id>_scoreboard.json`

#### Optional canonical rerunnable results

If a script becomes the accepted canonical recorder for this lane, it may also write one stable rerunnable result to its declared canonical path.

That canonical result path must be selected and documented during Workstream 0 rather than improvised by downstream workstreams, and it must write through the repo's stable output and diff-ledger rules.

## 8. Workstream Overview

Phase 0 is divided into seven workstreams:

0. Lane bootstrap and service-contract freeze
1. Generic service surface and request/result envelopes
2. Service run model and evidence surfaces
3. Baseline evaluation engine
4. Bounded mutation engine
5. External-consumer integration proof
6. Bundle freeze and drift rules

Each workstream must produce independently reviewable artifacts and tests.

## 9. Workstream 0 - Lane Bootstrap and Service-Contract Freeze

### Goal

Freeze the smallest useful generic service slice.

### Tasks

1. Confirm the canonical implementation-plan path and extract the Orket-side durable service contract.
2. Define the first proof slice as one consumer-supplied bridged tool surface plus one bounded eval slice.
3. Define the minimum service request envelope.
4. Define the minimum service result envelope.
5. Decide whether SDK parity is in scope for Phase 0.
6. Declare canonical output families for:
   - service-run artifacts,
   - candidate mutation artifacts,
   - qualifying compatibility-bundle artifacts.
7. Declare live-proof bookkeeping requirements for:
   - observed path,
   - observed result,
   - exact blocker when live proof cannot run.

### Required outputs

- implementation plan file,
- frozen proof-slice definition,
- request envelope definition,
- result envelope definition,
- declared canonical output families,
- declared live-proof bookkeeping requirements.

### Exit criteria

- the first proof slice is explicitly frozen,
- the plan does not claim LocalClaw implementation inside Orket,
- the plan does not invent a new top-level `artifacts/` authority root,
- all subsequent workstreams point to the same service contract.

### Current Status

Workstream 0 is complete and remains the frozen bootstrap baseline for this active lane.

Produced bootstrap artifacts:

- [docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md](docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md)
- [docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/request_examples.jsonl](docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/request_examples.jsonl)
- [docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/result_examples.jsonl](docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/result_examples.jsonl)

Next move in this active lane:

- Workstream 1 - Generic service surface and request/result envelopes

## 10. Workstream 1 - Generic Service Surface and Request/Result Envelopes

### Goal

Implement the generic Prompt Reforger service surface.

### Tasks

1. Define the generic invocation path for Prompt Reforger.
2. Define request/response envelopes for at least:
   - baseline evaluate,
   - bounded adapt,
   - run-status or result retrieval when needed.
3. Ensure the service surface does not encode consumer-specific assumptions.
4. Add SDK-parity helpers when Phase 0 includes SDK exposure.
5. Bind every request to stable identifiers for:
   - bridge contract or bridge reference,
   - eval slice or eval-slice reference,
   - observed runtime context.

### Suggested code targets

- `orket/reforger/service.py`
- existing generic extension/runtime service host layer
- optional SDK helper surface for parity

### Suggested source targets

- `docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md`
- `docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/request_examples.jsonl`
- `docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/result_examples.jsonl`

### Exit criteria

- the service can be invoked generically,
- request/result envelopes are stable,
- consumer-specific naming is absent,
- SDK parity is either implemented or explicitly deferred.

## 11. Workstream 2 - Service Run Model and Evidence Surfaces

### Goal

Implement deterministic service-run tracking and evidence surfaces.

### Tasks

1. Implement the Prompt Reforger run manifest and run record surfaces.
2. Implement deterministic candidate ordering for runs.
3. Record observed runtime context.
4. Record canonical tool and validator references used during evaluation.
5. Record observed path and observed result for the exercised proof path, or the exact blocker when live proof cannot run.

### Suggested code targets

- `orket/reforger/manifest.py`
- `orket/reforger/runbundle.py`
- `orket/reforger/report/summary.py`
- `orket/reforger/report/diff.py`

### Suggested staging outputs

- `benchmarks/staging/General/reforger_service_run_<run_id>.json`

### Exit criteria

- service-run artifacts are deterministic,
- canonical references are recorded,
- observed path and observed result are recorded for the exercised proof path, or the exact blocker is recorded.

## 12. Workstream 3 - Baseline Evaluation Engine

### Goal

Implement baseline evaluation before mutation logic is added.

### Tasks

1. Implement baseline evaluation against one consumer-supplied bridged tool surface and bounded eval slice.
2. Support a fixed comparison slice per service run.
3. Record per-case outcomes and aggregated baseline metrics.
4. Emit deterministic machine-readable results.
5. Enforce that no canonical schema or validator authority is overridden.

### Suggested code targets

- `orket/reforger/eval/base.py`
- `orket/reforger/eval/runner.py`

### Suggested staging outputs

- `benchmarks/staging/General/reforger_service_run_<run_id>.json`

### Exit criteria

- baseline evaluation runs end-to-end,
- artifacts are deterministic,
- canonical authority references are recorded,
- no canonical schema or validator authority is overridden.

## 13. Workstream 4 - Bounded Mutation Engine

### Goal

Add the smallest useful adaptation engine consistent with the service requirements.

### Tasks

1. Implement deterministic candidate generation.
2. Support only bounded micro-variation by default.
3. Start with mutations such as:
   - wording changes,
   - instruction ordering changes,
   - example substitution,
   - field explanation changes,
   - prompt-facing repair wording changes,
   - prompt-facing retry wording changes,
   - prompt-facing schema phrasing derived from the canonical contract.
4. Evaluate every candidate on the frozen comparison slice.
5. Select winners based on measured outcomes only.
6. Record failure attribution and error mapping for each candidate.

### Suggested code targets

- `orket/reforger/optimizer/base.py`
- `orket/reforger/optimizer/noop.py`
- `orket/reforger/optimizer/micro.py`
- `orket/reforger/mutations.py`

### Suggested staging outputs

- `benchmarks/staging/General/reforger_service_run_<run_id>.json`
- `benchmarks/staging/General/reforger_service_run_<run_id>_scoreboard.json`

### Exit criteria

- candidate IDs are deterministic,
- each candidate changes only bounded prompt/control surfaces,
- failure records include:
  - canonical `error_code` when available,
  - narrative failure label,
  - source authority surface,
  - attribution class,
- selection is based on measured eval results.

## 14. Workstream 5 - External-Consumer Integration Proof

### Goal

Prove that an external consumer can invoke Prompt Reforger through the generic service surface without making Orket consumer-specific.

### Tasks

1. Implement one external-consumer proof path through the generic service surface.
2. Exercise baseline evaluate through that proof path.
3. Exercise bounded adapt through that proof path.
4. Record observed path and observed result for the exercised proof path, or the exact blocker when live proof cannot run.
5. Verify that consumer-specific bridge, matrix, and orchestration ownership remain outside Orket.
6. Record whether any external-consumer verdict shown in proof artifacts is adopted from the Prompt Reforger service result for the same exercised tuple or derived independently by the consumer harness.

### Suggested proof targets

- contract/integration tests for generic service invocation
- optional SDK-parity integration tests when SDK support is in scope

### Exit criteria

- at least one external-consumer proof path can invoke the service successfully,
- the proof path does not require LocalClaw-specific code in Orket,
- any external-consumer verdict shown in proof artifacts records whether it is `service_adopted` or `harness_derived`,
- observed path and observed result are recorded, or the exact blocker is recorded.

## 15. Workstream 6 - Bundle Freeze and Drift Rules

### Goal

Freeze qualifying outputs and make reevaluation boundaries explicit.

### Tasks

1. Freeze the winning compatibility bundle for any qualifying service run.
2. Include in the bundle:
   - target runtime identity as observed,
   - bridged canonical tool surface identity,
   - workload/eval-slice identity,
   - frozen system prompt,
   - frozen prompt-facing tool instructions derived from the canonical contract,
   - frozen examples,
   - frozen prompt-facing repair/retry guidance subordinate to canonical validator outcomes,
   - references to the canonical tool and validator versions used during evaluation,
   - scorecard,
   - known failure boundaries,
   - observed runtime context when available,
   - requalification triggers.
3. Add runtime-condition warnings to the output.
4. Define explicit reevaluation triggers for:
   - runtime drift,
   - bridge drift,
   - tool schema drift,
   - validator drift,
   - sustained regression.

### Suggested canonical rerunnable output

If Phase 0 reaches a qualifying service run and a canonical recorder exists, the qualifying bundle may be written to a stable canonical result path such as:

- `benchmarks/results/governance/reforger_service_bundle.json`

If no run qualifies for bundle freeze, no qualifying compatibility bundle is emitted.

### Exit criteria

- at least one bundle is frozen for a qualifying service run, or the lane truthfully records that no run qualified for bundle freeze,
- runtime-condition warnings are present,
- reevaluation boundaries are explicit.

## 16. PR Slice Order

Phase 0 should be shipped in six PRs.

### PR1 - Future-lane scaffolding and service-contract freeze

Includes:

- implementation plan file,
- frozen proof-slice definition,
- stable request/result envelopes,
- declared output families.

### PR2 - Generic service surface

Includes:

- generic service invocation path,
- request/response contracts,
- optional SDK parity helpers.

### PR3 - Service run model and baseline evaluation

Includes:

- run manifest,
- run record,
- baseline evaluation engine,
- baseline run artifacts.

### PR4 - Bounded mutation engine

Includes:

- bounded mutation engine,
- candidate artifacts,
- candidate selection.

### PR5 - External-consumer integration proof

Includes:

- generic invocation integration proof,
- optional SDK-parity integration proof,
- verdict-source recording for any external-consumer verdicts shown,
- live-proof bookkeeping.

### PR6 - Qualifying bundle freeze and drift rules

Includes:

- bundle-freeze path for qualifying runs only,
- runtime/bridge reevaluation rules,
- service output warnings.

## 17. Verification Plan

### Structural proof

The following must be tested structurally:

- deterministic ordering of candidates and artifacts,
- required artifact completeness,
- stable error mapping shape,
- stable request/result serialization,
- separation of service artifacts from consumer-owned artifacts.

### Behavioral proof

The following must be tested behaviorally:

- one selected proof slice runs end-to-end,
- baseline evaluation executes against a bounded bridged surface and eval slice,
- at least one adaptation cycle executes,
- every evaluated service run receives an allowed result class,
- prompt, bridge, validator, and downstream defects can be distinguished in outputs.

### Truthfulness proof

The following must be verified explicitly:

- provider-setting tuning does not occur,
- canonical schema authority is not overridden,
- canonical validator authority is not overridden,
- unsupported results are emitted truthfully,
- results are not generalized beyond exercised runtime and bridge conditions,
- Orket does not silently take ownership of consumer orchestration.

### Required live-proof bookkeeping

For any claimed end-to-end service slice across real local model runtimes, the plan must record:

1. one explicit live command or runner path used for the service proof;
2. observed path classification:
   - `primary`
   - `fallback`
   - `degraded`
   - `blocked`
3. observed result classification:
   - `success`
   - `failure`
   - `partial success`
   - `environment blocker`
4. exact failing step and exact error when blocked;
5. the stable canonical output path for the rerunnable JSON result, when one exists;
6. an explicit statement when only structural or fake-adapter proof was achieved and live proof remains blocked;
7. whether any external-consumer verdict shown is `service_adopted` or `harness_derived`, plus the referenced service result when applicable.

Structural, mocked, import-only, dry-run-only, or code-inspection-only evidence must not be presented as live proof for the Phase 0 slice.

## 18. Phase 0 Exit Criteria

Phase 0 is complete only when all of the following are true:

1. one generic Prompt Reforger service surface exists;
2. one stable request/result contract exists;
3. baseline evaluation works for one frozen proof slice;
4. bounded prompt-only adaptation works for that same proof slice;
5. deterministic artifacts are emitted for:
   - service runs,
   - candidates,
   - qualifying bundles only;
6. every evaluated service run ends in:
   - `certified`
   - `certified_with_limits`
   - `unsupported`;
7. at least one compatibility bundle is frozen for a qualifying service run, or the lane truthfully records that no run qualified for bundle freeze;
8. reevaluation triggers are recorded for runtime drift and bridge drift;
9. at least one external-consumer proof path has recorded observed path / observed result bookkeeping, or the exact blocker to live proof is recorded explicitly without claiming completion beyond the proven layer.

## 19. Non-goals

Phase 0 does not aim to:

- implement LocalClaw inside Orket,
- support multiple unrelated tool families,
- provide global model rankings,
- optimize provider settings,
- certify raw external API compatibility,
- replace bridge design with prompt text,
- silently widen Phase 0 beyond the frozen Workstream 0 bootstrap baseline.

## 20. Proposed Decision Set

The following decisions are proposed by this implementation plan for future promotion:

1. Phase 0 proves one generic service slice before any broader expansion.
2. Prompt Reforger is implemented as an extension-agnostic Orket service surface.
3. Consumer orchestration and matrix truth remain outside Orket.
4. The service remains bounded, prompt-only, and subordinate to canonical tool/schema/validator authority.
5. Unsupported is a valid and expected outcome.
6. A compatibility bundle is frozen only for service runs that actually clear the acceptance thresholds.
7. Broad expansion is blocked until one concrete service slice is proven end-to-end.
