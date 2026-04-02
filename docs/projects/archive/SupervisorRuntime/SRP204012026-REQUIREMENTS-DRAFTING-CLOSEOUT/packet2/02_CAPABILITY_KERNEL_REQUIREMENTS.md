# Capability Kernel Requirements
Last updated: 2026-04-01
Status: Completed archived draft packet requirements authority
Owner: Orket Core
Packet role: Stage 1

## Purpose

Define one named capability kernel over privileged runtime actions.

## Draft requirements

1. Every privileged action admitted by Packet 2 must map to one named capability.
2. Each capability must declare at minimum:
   - allowed principal families
   - scope boundary
   - timeout or budget class
   - approval policy
   - audit expectations
3. Capability checks must remain distinct from workload identity and from operator action identity.
4. Capability denial may block execution, but capability framing must not become a second closure authority.
5. Packet 2 must assume safe-tooling and control-plane surfaces converge toward this kernel rather than around it.

## Non-goals

1. large capability catalog expansion
2. cloud IAM modeling
3. policy-engine implementation detail
