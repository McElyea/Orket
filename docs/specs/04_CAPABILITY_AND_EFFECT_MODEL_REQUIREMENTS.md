# Capability and Effect Model Requirements
Last updated: 2026-04-09
Status: Active durable spec authority
Owner: Orket Core
Lane type: Control-plane foundation / safe tooling

## Purpose

Define the minimum capability and effect model required for Orket to mediate tools, workloads, mutation rights, retries, and recovery safely.

## Authority note

Shared capability, effect, idempotency, compensation, evidence, and observability enums are defined in [00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/specs/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md).

Namespace and tooling extensions are defined in:
1. [11_NAMESPACE_AND_WORKLOAD_COMPOSITION_REQUIREMENTS.md](docs/specs/11_NAMESPACE_AND_WORKLOAD_COMPOSITION_REQUIREMENTS.md)
2. [12_SAFE_TOOLING_WORKLOAD_INTEGRATION_REQUIREMENTS.md](docs/specs/12_SAFE_TOOLING_WORKLOAD_INTEGRATION_REQUIREMENTS.md)

## Core assertion

Availability is not enough.

A tool or workload action must be classified by capability and effect class so the control plane can determine:
1. whether the action is allowed
2. how dangerous it is
3. whether retry is safe
4. whether reconciliation is required
5. whether compensation exists
6. whether operator approval is required

## Capability rules

### CE-01. Canonical capability classes

The canonical capability classes are defined in the glossary.

### CE-02. Capability declaration

Every workload action surface and tool surface must declare:
1. required capability class
2. allowed caller scope
3. required evidence contract
4. retry safety constraints
5. reconciliation requirement class
6. operator gate requirements if any

## Effect rules

### CE-03. Canonical effect classes

The canonical effect classes are defined in the glossary.

### CE-04. Effect declaration requirements

Each effect-bearing action must declare or resolve at minimum:
1. effect class
2. target class
3. idempotency class
4. compensation class
5. observability class
6. uncertainty handling rules

### CE-05. Effect journal compatibility

Every effect-bearing action contract must be compatible with [10_EFFECT_JOURNAL_AND_CHECKPOINT_REQUIREMENTS.md](docs/specs/10_EFFECT_JOURNAL_AND_CHECKPOINT_REQUIREMENTS.md).

## Policy implications

### CE-06. Capability-policy matrix

Policy must be able to express at minimum:
1. workload X may use capability Y
2. capability Y is forbidden in degraded mode Z
3. capability Y requires operator approval under condition C
4. capability Y requires reconciliation on uncertainty class U
5. capability Y may only target namespace N or resource class R

### CE-07. Effect-policy coupling

Recovery policy must be allowed to depend on:
1. capability class
2. effect class
3. idempotency class
4. compensation class
5. observability class

Unknown idempotency or unknown compensation must not be silently treated as safe.

## Tool and workload declaration rules

### CE-08. Tool contract declarations

A tool or workload action contract must not be considered safe for governed execution unless it declares:
1. capability class
2. effect class
3. idempotency class
4. evidence contract
5. observability class

Compensation class may be omitted only when effect class is `no_effect` or clearly local and reversible by construction.

### CE-09. Undeclared capability requests

A proposed action requesting an undeclared capability is a protocol failure and must not be auto-upgraded by runtime convenience.

## Recovery coupling

### CE-10. Capability-aware recovery

Recovery must consider capability and effect classes at decision time.
At minimum:
1. observe-only actions may retry more freely
2. deterministic compute may re-run under normal replay rules
3. bounded local mutation may retry only under idempotent or reconciled conditions
4. external or destructive mutation requires stricter gating

### CE-11. Degraded-mode capability restrictions

Degraded modes must be able to explicitly block one or more capability classes.

## Acceptance criteria

This draft is acceptable only when:
1. safe tooling can consume it directly
2. retry and reconciliation policy can branch on capability and effect classes
3. undeclared or unknown classes become meaningful control-plane constraints
4. destructive or opaque effects cannot masquerade as low-risk actions
5. future workload contracts can declare these classes without redefining the vocabulary
