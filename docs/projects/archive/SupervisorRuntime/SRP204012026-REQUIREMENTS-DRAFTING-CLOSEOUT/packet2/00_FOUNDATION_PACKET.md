# SupervisorRuntime Packet 2 Foundation Packet
Last updated: 2026-04-01
Status: Completed archived draft packet foundation
Owner: Orket Core
Packet role: Foundation

## Purpose

Define Packet 2 as one staged requirements packet for:
1. a host-owned capability kernel
2. default-path control-plane convergence
3. one principal, capability, recovery, operator, and closure story over governed runtime surfaces

## Decision lock

The following stay fixed while this packet is active:
1. the host remains the sole runtime authority center
2. Packet 2 builds on Packet 1 durable specs instead of replacing them
3. the paused ControlPlane convergence lane remains paused until explicitly reopened
4. products, clients, and extensions remain thin over host-owned authority
5. no resume by checkpoint, snapshot, or saved state implication
6. no operator action becomes world-state evidence
7. no alternate closure authority may compete with final truth
8. no ambient namespace or mutation authority is admitted

## Packet stages

1. Stage 0 - foundation, glossary, and crosswalk
2. Stage 1 - principal model, capability kernel, admission, and execution identity
3. Stage 2 - resource, namespace, ownership, effect journal, and mutation authority
4. Stage 3 - checkpoint, recovery, operator, reconciliation, and final-truth closure authority
5. Stage 4 - public control surfaces, extension and client boundary, and scheduler posture
6. Stage 5 - sequencing, compatibility exits, proof classes, and later promotion gates

## Non-goals

Packet 2 does not, by itself:
1. implement runtime code
2. reopen Graphs
3. define marketplace or cloud distribution posture
4. define marshaller product specifics
5. finalize distributed or multitenant cluster semantics
