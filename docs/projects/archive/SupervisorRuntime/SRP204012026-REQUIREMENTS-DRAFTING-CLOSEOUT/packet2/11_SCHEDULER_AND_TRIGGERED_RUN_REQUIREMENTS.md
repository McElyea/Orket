# Scheduler And Triggered Run Requirements
Last updated: 2026-04-01
Status: Completed archived draft packet requirements authority
Owner: Orket Core
Packet role: Stage 4

## Purpose

Define how scheduled and triggered execution fits into the same host-owned authority model.

## Draft requirements

1. Packet 2 must admit direct operator, scheduler, event, and policy-triggered starts as explicit trigger classes.
2. Trigger class must not bypass admission, capability, namespace, recovery, or closure rules.
3. Scheduled and triggered runs must share the same run, attempt, resource, effect, and final-truth authority families as direct runs.
4. Child composition and scheduler-driven fan-out must preserve supervisor-owned authority and explicit grants.
5. Packet 2 must avoid treating the scheduler as a second runtime authority center.

## Non-goals

1. distributed cluster scheduler design
2. workflow DAG product design
3. exhaustive automation catalog work
