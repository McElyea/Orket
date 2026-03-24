# Namespace and Workload Composition Requirements
Last updated: 2026-03-23
Status: Accepted for implementation planning
Owner: Orket Core
Lane type: Control-plane foundation / namespace and composition

## Purpose

Define the slim namespace and workload-composition contract required now so resource ownership, tool visibility, and shared-resource rules do not remain ambiguous.

This document intentionally locks a minimal contract rather than a full rich tenancy model.

## Authority note

Shared enums and first-class object nouns are defined in [00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/projects/ControlPlane/orket_control_plane_packet/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md).

## Core assertions

1. Namespace semantics are needed now because resources, capabilities, and shared-resource rules already imply namespace boundaries.
2. Workload composition must not become an escape hatch that bypasses supervisor, effect, reservation, or operator rules.

## Minimal namespace requirements

### NW-01. Namespace object requirements

Every governed workload must execute within a declared namespace or scope that provides at minimum:
1. namespace identifier
2. visibility class
3. default resource ownership rule
4. tool visibility rule
5. shared-resource policy reference

### NW-02. Private versus shared resources

The control plane must distinguish:
1. namespace-private resources
2. shared governed resources
3. externally referenced resources

That distinction must influence:
1. reservation scope
2. lease acquisition
3. cleanup authority
4. mutation permissions

### NW-03. Capability target scoping

Capability declarations must be able to constrain:
1. which namespaces may be targeted
2. which resource classes may be targeted
3. whether cross-namespace mutation is forbidden, gated, or allowed

## Workload composition requirements

### NW-04. Child workload declaration

If a workload may start or coordinate another workload, the parent workload contract must declare at minimum:
1. child workload relationship class
2. namespace inheritance or override rule
3. capability escalation policy
4. reservation and lease interaction rule
5. final-truth publication rule for parent and child

### NW-05. Composition does not bypass control-plane authority

A child workload or composed workload may not:
1. bypass admission checks
2. bypass reservation or lease rules
3. bypass effect journal publication
4. bypass reconciliation triggers
5. bypass operator gate requirements

### NW-06. Shared-resource usage

When multiple workloads may touch the same shared governed resource, the control plane must require:
1. explicit shared-resource declaration
2. namespace-safe reservation or lease rules
3. cleanup and mutation ownership rules
4. reconciliation scope strong enough to detect cross-workload divergence

## Visibility requirements

### NW-07. Tool visibility

Tool availability must be scoped by:
1. workload identity
2. namespace
3. declared capability class
4. degraded mode if active

### NW-08. Operator visibility

Operator inspection surfaces must preserve namespace boundaries so:
1. private resources remain attributable
2. shared resources remain visibly shared
3. cross-namespace actions remain auditable

## Deferred but explicit

### NW-09. Slim now, rich later

This document does not require:
1. full multitenant scheduling
2. rich namespace hierarchy semantics
3. marketplace-scale trust zones

It does require a slim contract that prevents ambiguity in current packet requirements.

## Acceptance criteria

This document is acceptable only when:
1. namespace scope is no longer implicit
2. shared versus private resource rules are explicit
3. child workload composition cannot bypass control-plane rules
4. later richer namespace work can extend this contract instead of replacing it
