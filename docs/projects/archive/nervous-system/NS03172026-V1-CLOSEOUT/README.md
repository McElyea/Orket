# Orket as Nervous System

Date: 2026-03-17

## Status

Historical archive summary for the completed Nervous System v1 action-path lane.

- Closeout authority: `docs/projects/archive/nervous-system/NS03172026-V1-CLOSEOUT/CLOSEOUT.md`
- Historical implementation plan: `docs/projects/archive/nervous-system/NS03172026-V1-CLOSEOUT/IMPLEMENTATION_PLAN.md`
- Historical requirements record: `docs/projects/archive/nervous-system/NS03172026-V1-CLOSEOUT/GovernanceFabric.md`
- Historical live verification record: `docs/projects/archive/nervous-system/NS03172026-V1-CLOSEOUT/LIVE_VERIFICATION.md`

## Thesis

Orket is not the agent brain and not the execution muscle. Orket is the governance layer between an untrusted agent decision and the systems that decision wants to touch.

Every action proposal passes through deterministic gates:

1. projection
2. admission
3. approval when required
4. execution
5. result validation
6. append-only ledger commit

The user-facing goal is straightforward: run agents locally without handing them unchecked authority over files, credentials, outbound channels, or irreversible actions.

## What v1 Covers

The closed v1 slice was intentionally narrow:

- `action.tool_call` proposals only
- deterministic admission and commit
- approval queue and approval decision flow
- scoped per-action credential tokens
- append-only governance ledger
- replay and audit over one action lifecycle
- OpenClaw JSONL subprocess live verification

## Why This Matters

Agent frameworks can make unsafe actions easy:

- destructive file mutation
- outbound exfiltration
- credential misuse
- prompt-injected tool escalation
- unreviewed extension behavior

Orket's job is to convert those actions into governed proposals with explicit decisions, evidence, and replayable lineage.

## Relation to Existing Work

The Nervous System lane draws on existing Orket primitives:

- policy and tool gating
- deterministic runtime contracts
- state and ledger discipline
- approval workflows
- capability scoping
- leak detection and sanitization

The broader federated-stream framing remains in `docs/projects/archive/nervous-system/NS03172026-V1-CLOSEOUT/Broker.md`, while the unified requirements record for this archived lane lives in `docs/projects/archive/nervous-system/NS03172026-V1-CLOSEOUT/GovernanceFabric.md`.

## Non-Goals

- replacing the agent framework
- claiming perfect safety
- treating mock or structural tests as runtime proof
- widening scope beyond the locked v1 action path without an explicit roadmap change

## This Document

This README is the archive entrypoint for the completed Nervous System lane. The closeout record defines the closure boundary and proof.
