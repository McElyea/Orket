# Admission And Execution Identity Requirements
Last updated: 2026-04-01
Status: Completed archived draft packet requirements authority
Owner: Orket Core
Packet role: Stage 1

## Purpose

Define one admission and execution identity story across governed runtime surfaces.

## Draft requirements

1. Packet 2 must draft one explicit admission contract that accepts or denies governed execution against declared inputs and policy.
2. Run, attempt, and step identity must stay stable across replay, recovery, reconciliation, and closure.
3. Admission identity must remain distinct from session identity and from client-facing transport identity.
4. Attempt history must remain append-only and must distinguish resumed execution from replacement execution.
5. Every governed effectful or closure-relevant action must be attributable to workload, run, attempt, step, and authorization basis.

## Non-goals

1. broad workflow DSL design
2. alternate execution object hierarchies
3. UI-local naming or transport-local aliases
