# Safe Tooling Workload Integration Requirements
Last updated: 2026-03-23
Status: Accepted for implementation planning
Owner: Orket Core
Lane type: Control-plane foundation / safe tooling integration

## Purpose

Define the minimum rules by which tools and workload actions plug into the control plane without bypassing capability declarations, reservation or lease truth, effect publication, or operator gates.

## Authority note

Shared enums and first-class object nouns are defined in [00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/projects/ControlPlane/orket_control_plane_packet/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md).

## Core assertions

1. Tool availability is not execution authority.
2. A tool integration that cannot declare its control-plane consequences is not safe for governed execution.

## Tool contract requirements

### ST-01. Required declarations

A tool or workload action contract must declare at minimum:
1. capability class
2. effect class
3. idempotency class
4. evidence contract class
5. observability class
6. namespace or scope targeting rule

### ST-02. Invocation envelope

Every governed tool invocation must be attributable to:
1. workload identifier
2. run identifier
3. attempt identifier
4. step identifier
5. reservation or lease references if applicable
6. authorization basis

### ST-03. Proposal versus authorization

Models or planners may propose tool use.

Only the runtime may:
1. authorize tool execution
2. attach capability and effect meaning
3. publish resulting effect truth

## Tool result requirements

### ST-04. Effect and receipt publication

A tool invocation that can affect governed state must produce:
1. receipt references
2. effect records
3. effect journal linkage
4. resource records if resources were created or mutated

### ST-05. Undeclared or escalated requests

If a proposed invocation requests:
1. an undeclared capability
2. a broader namespace target
3. stronger mutation rights

the runtime must reject it as a governed defect rather than upgrading it by convenience.

## Resource and lifecycle coupling

### ST-06. Reservation and lease coupling

If a tool requires exclusive access, concurrency claims, or resource ownership, the control plane must require:
1. reservation before execution where admission or scheduling needs it
2. lease promotion when active ownership or mutation begins
3. explicit release, transfer, or cleanup semantics on failure or cancellation

### ST-07. Degraded-mode tooling

Degraded modes must be able to:
1. disable specific tool families
2. narrow namespace targets
3. force observe-only or no-mutation operation

### ST-08. Operator-gated tooling

When a tool requires explicit operator authorization, the resulting operator action must be recorded separately from the tool effect and must not become evidence of world state by itself.

## Composition requirements

### ST-09. Workload-carried tooling contracts

If a workload exposes tools or tool-like action surfaces, the workload contract must carry the same governed declarations required of first-class tools.

### ST-10. Child workload tool inheritance

If a workload composes child workloads, tool visibility and capability grants must follow explicit inheritance or override rules rather than implicit ambient access.

## Acceptance criteria

This document is acceptable only when:
1. safe tooling can consume the control-plane contracts directly
2. tool invocation cannot bypass reservation, lease, or effect-journal truth
3. degraded modes can meaningfully reduce tool authority
4. operator-gated tooling stays explicit and auditable
