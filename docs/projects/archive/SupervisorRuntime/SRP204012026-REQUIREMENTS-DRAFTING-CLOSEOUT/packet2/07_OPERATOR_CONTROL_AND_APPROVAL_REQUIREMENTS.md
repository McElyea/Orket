# Operator Control And Approval Requirements
Last updated: 2026-04-01
Status: Completed archived draft packet requirements authority
Owner: Orket Core
Packet role: Stage 3

## Purpose

Define one bounded operator authority family for commands, approvals, risk acceptance, and attestation.

## Draft requirements

1. Packet 2 must preserve distinct operator action classes for command, risk acceptance, and attestation.
2. Approval-gated continuation must remain explicit and policy-bounded rather than implied by transport or checkpoint presence.
3. Operator actions affecting governed execution must publish first-class operator records.
4. Operator influence must remain inspectable in read models and final-truth inputs.
5. Risk acceptance must never become world-state evidence, and attestation must stay visibly distinct from observation.

## Non-goals

1. full operator workbench UX
2. role-based permission system design
3. general manual resume API design beyond selected packet slices
