# Effect Journal And Mutation Requirements
Last updated: 2026-04-01
Status: Completed archived draft packet requirements authority
Owner: Orket Core
Packet role: Stage 2

## Purpose

Define the normative mutation and closure-relevant write path for Packet 2.

## Draft requirements

1. Governed mutation and closure-relevant writes must publish through the effect journal rather than rely on after-the-fact reconstruction.
2. Effect publication must remain ordered, append-only, attributable, and integrity-verifiable.
3. Mutation authority must stay bound to capability, namespace, reservation or lease, and run, attempt, or step identity.
4. Packet 2 must keep debugging artifacts and summaries projection-only where published effect truth is required.
5. Degraded or uncertain mutation outcomes must remain visible rather than being normalized into success-shaped closure.

## Non-goals

1. analytics or BI event modeling
2. replacing all debugging artifacts
3. speculating about eventual distributed journals
