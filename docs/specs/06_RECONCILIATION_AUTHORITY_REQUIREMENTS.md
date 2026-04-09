# Reconciliation Authority Requirements
Last updated: 2026-04-09
Status: Active durable spec authority
Owner: Orket Core
Lane type: Control-plane foundation / truth repair

## Purpose

Define the authority, triggers, outputs, and constraints of reconciliation so Orket can compare intended state and observed state after uncertainty, contradiction, or failure.

## Authority note

Shared reconciliation enums and operator input classes are defined in [00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/specs/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md).

## Core assertion

Reconciliation is the control-plane process that answers:
"What is actually true now, relative to what the runtime believed or intended?"

It is not a model reflection step and must not depend on narrative explanation.

## Reconciliation triggers

### RA-01. Mandatory reconciliation triggers

The control plane must support mandatory reconciliation at minimum when:
1. an attempt ends with `effect_boundary_uncertain`
2. resource state is uncertain
3. a cleanup-critical lease is uncertain
4. contradiction exists between receipts and observed state
5. a recovery policy explicitly requires it
6. a run resumes from a checkpoint that requires re-observation

### RA-02. Optional reconciliation triggers

Policy may additionally require reconciliation for:
1. high-risk capability classes
2. destructive effects
3. long-running attempts
4. externally observable but eventually consistent systems

## Reconciliation authority

### RA-03. Runtime authority

Only the runtime, through the reconciler under supervisor control, may publish authoritative reconciliation results.

Adapters may supply observations.
Models may propose hypotheses.
Neither may publish final reconciliation truth.

### RA-04. Allowed evidence

Reconciliation may use only:
1. durable intended state and effect journal entries
2. validated artifacts
3. reservation, lease, and resource records
4. authoritative adapter observations
5. explicit operator attestations where policy allows them
6. policy rules governing comparison

### RA-05. Forbidden evidence

Reconciliation must not use:
1. model explanations as evidence
2. inferred hidden side effects without observation or receipt
3. stale cached assumptions not tied to known observation basis
4. operator risk acceptance as evidence of world state
5. operator commands as a substitute for observation

## Operator interaction

### RA-06. Operator attestation

Operator attestation may serve as an explicit reconciliation input only when:
1. policy allows attestation for the specific scope
2. the attestation is recorded as `operator_attestation`
3. the resulting reconciliation output keeps the evidence visibly labeled as attested rather than observed

### RA-07. Operator risk acceptance

Operator risk acceptance may influence continuation policy after reconciliation.
It may not satisfy evidence requirements for external or world-state truth.

## Reconciliation scope and outputs

### RA-08. Comparison scope

Every reconciliation record must declare scope at minimum as one of:
1. `single_resource`
2. `resource_set`
3. `attempt_effects`
4. `run_scope`
5. `cleanup_scope`

### RA-09. Comparison basis

Reconciliation must compare:
1. intended or authorized state and effects
2. observed state and effects
3. missing observations
4. contradictions
5. residual uncertainty

### RA-10. Divergence classes

Divergence classes are canonical in the glossary.

### RA-11. Safe continuation classes

A reconciliation result must publish one safe continuation class from the glossary.

### RA-12. Residual uncertainty

Reconciliation results must include whether residual uncertainty remains and what class it belongs to.
Successful comparison does not permit silent omission of remaining unknowns.

## Reconciler behavior

### RA-13. Reconciler duties

The reconciler must:
1. consume declared scope and comparison basis
2. collect required observations
3. compare against intended and journaled state
4. classify divergence
5. publish continuation safety class
6. emit machine-readable evidence references

### RA-14. Reconciler limits

The reconciler must not:
1. authorize mutation beyond declared reconciliation policy
2. silently clean up resources unless a governed cleanup effect is separately authorized
3. collapse contradictions into success for convenience

## Relationship to recovery and completion

### RA-15. Reconciliation before recovery

Where required, reconciliation must precede recovery authorization.
Recovery may depend on reconciliation output but must remain a distinct supervisory decision.

### RA-16. Reconciliation and completion

A run may close as completed after reconciliation only if the supervisor determines:
1. final truth can be published honestly
2. required effects or outputs are satisfied
3. residual uncertainty is either absent or explicitly acceptable under policy
4. operator requirements are met

## Acceptance criteria

This draft is acceptable only when:
1. reconciliation is clearly distinct from model reflection
2. operator attestation is visibly distinct from observation
3. operator risk acceptance cannot masquerade as evidence
4. triggers are strong enough to catch unsafe uncertainty
5. outputs are actionable for recovery and operator control
6. residual uncertainty remains visible in final truth surfaces
