# Prompt Reforger Generic Service Contract

Owner: Orket Core
Status: Active
Last updated: 2026-04-03

## Purpose

This contract defines Prompt Reforger as a generic bounded adaptation service hosted by Orket.

Prompt Reforger accepts one bounded service request tied to one consumer-supplied bridged tool surface, one bounded eval slice, and one observed runtime context, then returns one truthful service result for that exact tuple.

Prompt Reforger is not an authority boundary for canonical tool contracts, canonical schemas, canonical validators, or consumer-specific orchestration.

## Scope

This contract applies when all of the following are true:

1. Orket is acting as a generic service host.
2. An external consumer supplies a bounded adaptation request.
3. The target runtime is a local model runtime.
4. The request is tied to a bridged canonical tool surface and a bounded workload or eval slice.
5. The service performs prompt and control refinement only.

This contract does not authorize:

1. app-specific orchestration inside Orket
2. consumer-specific bridge ownership inside Orket
3. provider-setting tuning as part of the service
4. raw external API exposure as the primary model-facing contract
5. narrative success without measured evidence

## Result Classes

Every evaluated service run must end in exactly one result class:

1. `certified`
2. `certified_with_limits`
3. `unsupported`

A qualifying service run is one whose final result is either `certified` or `certified_with_limits`.

`unsupported` is never a bundle-freeze outcome.

A `certified_with_limits` bundle may be frozen only when the narrowed acceptance envelope, unsupported cases, and fallback or review requirements are explicitly recorded in the frozen bundle.

If no run qualifies for bundle freeze, the truthful outcome is one or more `unsupported` or non-qualifying results without manufacturing a qualifying bundle.

## Request Envelope

Every service request must bind to exactly one:

1. `request_id`
2. `service_mode`
3. `bridge_contract_ref`
4. `eval_slice_ref`
5. `runtime_context`
6. `baseline_bundle_ref` or `baseline_prompt_ref`
7. `acceptance_thresholds`

The minimum request envelope fields are:

1. `request_id`
2. `service_mode`
   Allowed values at Phase 0:
   - `baseline_evaluate`
   - `bounded_adapt`
3. `consumer_id`
   Optional but recommended when available.
4. `bridge_contract_ref`
5. `eval_slice_ref`
6. `runtime_context`
   Required subfields when observable:
   - `provider`
   - `model_id`
   - `adapter`
   Optional subfields when observable:
   - `runtime_version`
   - `endpoint_id`
   - `quantization`
7. `baseline_bundle_ref` or `baseline_prompt_ref`
8. `acceptance_thresholds`
   Required subfields:
   - `certified_min_score`
   - `certified_with_limits_min_score`
9. `candidate_budget`
   Required for `bounded_adapt`, optional for `baseline_evaluate`.

## Result Envelope

Every service result must bind to the exact request tuple that produced it and must include at minimum:

1. `request_id`
2. `service_run_id`
3. `result_class`
4. `observed_path`
5. `observed_result`
6. `runtime_context`
7. `bridge_contract_ref`
8. `eval_slice_ref`
9. `baseline_metrics`
10. `candidate_summary`
11. `acceptance_reason`
12. `bundle_ref`
    This must be null or absent when the result class is `unsupported`.
13. `known_limits`
14. `requalification_triggers`

Allowed `observed_path` values:

1. `primary`
2. `fallback`
3. `degraded`
4. `blocked`

Allowed `observed_result` values:

1. `success`
2. `failure`
3. `partial success`
4. `environment blocker`

When live proof cannot run, the result must record the exact failing step and exact blocker instead of claiming completion beyond the proven layer.

## Service Modes

Phase 0 admits two service modes only:

1. `baseline_evaluate`
   - evaluates the supplied baseline prompt or control surface
   - may return any allowed result class
   - must not freeze a bundle unless thresholds are already met
2. `bounded_adapt`
   - performs bounded prompt-only mutation and evaluation
   - may return any allowed result class
   - may freeze a bundle only for a qualifying run

No provider-setting or runtime-setting optimization mode is admitted.

## Bundle Freeze Rules

If a qualifying service run produces a compatibility bundle, the frozen bundle must include:

1. target runtime identity as observed
2. bridged canonical tool surface identity
3. workload or eval-slice identity
4. frozen prompt surfaces
5. frozen prompt-facing tool instructions derived from the canonical contract
6. frozen examples
7. frozen prompt-facing repair and retry guidance subordinate to canonical validator outcomes
8. references to the canonical tool and validator versions used during evaluation
9. scorecard and acceptance basis
10. known failure boundaries
11. requalification triggers

## Artifact and Output Rules

Prompt Reforger must distinguish between:

1. service-run artifacts for every evaluated run
2. candidate mutation records
3. qualifying compatibility bundles only

Phase 0 bootstrap freezes the following output families:

1. staging service-run artifact:
   - `benchmarks/staging/General/reforger_service_run_<run_id>.json`
2. staging scoreboard artifact:
   - `benchmarks/staging/General/reforger_service_run_<run_id>_scoreboard.json`

No new top-level `artifacts/` authority root is admitted.

## Truth and Boundary Rules

Prompt Reforger must remain:

1. extension agnostic
2. prompt-only within the adaptation loop
3. subordinate to canonical tool and validator authority
4. fail-closed for unsupported pairings

Prompt Reforger must not:

1. become LocalClaw-specific
2. claim provider-quality certification
3. replace deterministic validators with model judgment
4. absorb consumer-owned orchestration or matrix authority

When an external consumer reuses Prompt Reforger result classes, shared labels do not merge authority:

1. Prompt Reforger owns service-result authority.
2. The external consumer owns its own harness-verdict authority.
3. Any external verdict shown from the same exercised tuple must record whether it is `service_adopted` or `harness_derived`.

## Requalification Triggers

At minimum, prior compatibility results must be treated as requiring re-evaluation when any of the following change materially:

1. target runtime
2. provider when observable
3. adapter or endpoint identity when observable
4. bridge contract
5. tool schema
6. validator behavior
7. sustained regression beyond the accepted threshold

## Bootstrap Artifacts

The Phase 0 bootstrap freeze for this contract is accompanied by:

1. [docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/request_examples.jsonl](docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/request_examples.jsonl)
2. [docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/result_examples.jsonl](docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/result_examples.jsonl)
3. [docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/Phase0ImplementationPlan.md](docs/projects/archive/PromptReforgerToolCompatibility/PR04032026-PHASE0-CLOSEOUT/Phase0ImplementationPlan.md)
