# Checkpoint Recovery And Resume Requirements
Last updated: 2026-04-01
Status: Completed archived draft packet requirements authority
Owner: Orket Core
Packet role: Stage 3

## Purpose

Define supervisor-owned recovery and resume authority without resume by implication.

## Draft requirements

1. Checkpoint publication must remain an explicit supervisor-owned act, not a side effect of saving state.
2. Checkpoint existence alone must never authorize resume.
3. Resume must require checkpoint admissibility, supervisor acceptance, and an explicit recovery decision.
4. Packet 2 must keep same-attempt resume and new-attempt replacement as distinct execution modes.
5. Recovery authority must remain durable and attributable across governed paths that claim resumability.

## Non-goals

1. infinite replay or fork design
2. speculative snapshot platforms
3. broad local-state backup policy
