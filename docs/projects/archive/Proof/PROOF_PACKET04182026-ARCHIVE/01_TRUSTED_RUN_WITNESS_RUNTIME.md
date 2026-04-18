# Trusted Run Witness Runtime

Last updated: 2026-04-18
Status: Historical staging source
Authority status: Historical staging source only. Accepted requirements live in `docs/projects/archive/Proof/TRW04162026-REQUIREMENTS-CLOSEOUT/TRUSTED_RUN_WITNESS_RUNTIME_REQUIREMENTS_PLAN.md`.
Owner: Orket Core
Accepted requirements archive: `docs/projects/archive/Proof/TRW04162026-REQUIREMENTS-CLOSEOUT/TRUSTED_RUN_WITNESS_RUNTIME_REQUIREMENTS_PLAN.md`

## Current Shipped Baseline

Orket already has:

1. deterministic-runtime target architecture in `docs/ARCHITECTURE.md`
2. control-plane records for selected governed paths in `CURRENT_AUTHORITY.md`
3. a governed ProductFlow `write_file` proof lane in `docs/specs/PRODUCTFLOW_GOVERNED_RUN_WALKTHROUGH_V1.md`
4. operator review package expectations in `docs/specs/PRODUCTFLOW_OPERATOR_REVIEW_PACKAGE_V1.md`
5. determinism claim tiers in `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
6. MAR completeness rules in `docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md`

The current ProductFlow evidence proves a useful slice of approval-governed execution and review packaging, but the replay review still truthfully reports `replay_ready=false`, `stability_status=not_evaluable`, and `claim_tier=non_deterministic_lab_only`.

## Future Delta Proposed By This Doc

Promote one bounded run class into a `Trusted Run v1` witness.

The witness should answer:

1. what was requested
2. what runtime authority admitted the work
3. what model or tool path executed
4. what operator approval or denial occurred
5. what effect was observed
6. what final truth was assigned
7. what replay or stability claim is allowed
8. what evidence is missing if the claim cannot be upgraded

The product object is not the control plane itself.
The product object is the verified witness bundle.

## What This Doc Does Not Reopen

1. It does not reopen ControlPlane as a broad implementation lane.
2. It does not require universal control-plane coverage.
3. It does not promote all current run surfaces to trusted-run status.
4. It does not claim model output correctness.
5. It does not require byte-identical text determinism.
6. It does not create a public publication claim by itself.

## Core Idea

Orket should be able to produce one portable bundle for a completed governed run:

```text
trusted_run_bundle =
    governed_input
    + resolved_policy
    + resolved_configuration
    + runtime_trace
    + approval_or_operator_actions
    + checkpoint_and_resource_lineage
    + effect_journal
    + final_truth
    + replay_or_stability_status
```

An operator should be able to hand that bundle to another person or process and say:

```text
This is what Orket can prove about the run.
This is what Orket cannot prove.
```

## Why This Matters

Other workflow runtimes can often show logs, traces, tasks, retries, and state.

Orket's differentiator should be stronger:

1. success is tied to verified evidence
2. missing evidence is surfaced as missing evidence
3. model output is not allowed to become runtime truth by narration
4. approval continuation binds to a specific run, checkpoint, and effect path
5. replay and stability claims use named claim tiers

This is a practical reason to trust Orket over another runtime with similar data.

## Candidate Trusted Run V1 Shape

The first `Trusted Run v1` should be intentionally small:

1. one persisted workflow input
2. one governed run id
3. one operator approval boundary
4. one bounded file or state mutation
5. one deterministic validation or verdict surface
6. one final truth record
7. one offline verifier report

## Acceptance Boundary

This idea becomes real only when:

1. a run emits a complete witness bundle
2. the bundle can be verified without rerunning the workflow
3. the verifier reports an allowed claim tier
4. a missing or corrupted required record causes verifier failure
5. the human-facing result does not overclaim beyond the verifier report

## First Proof Target

The first target should not be broad orchestration.

The first target should be:

```text
one approval-governed local mutation with a deterministic contract verdict
```

That target is narrow enough to verify and useful enough to explain.
