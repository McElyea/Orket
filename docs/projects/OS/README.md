# OS Program (North Star)

Last updated: 2026-02-22
Status: Active discovery
Owner: Orket Core
This directory is the authoritative governance and contract surface for the Orket OS-class substrate.

## What this is
Orket OS v1 defines a deterministic semantic control plane + local substrate for agentic systems.

This program governs:
- Kernel API boundaries
- Local Sovereign Index (LSI) rules
- Deterministic identity + canonicalization
- Capability enforcement (deny-by-default when enabled)
- Replay and equivalence requirements
- Test gates for PR acceptance

## What this is NOT
- Not a workflow engine spec
- Not a scheduler spec
- Not a distributed mesh spec (future)
- Not a cryptographic trust model

## Authority and drift policy
If a requirement is not in the files listed in `contract-index.md`, it does not exist in OS v1.

If a requirement is normative, it MUST be testable and MUST be enforced by the OS test policy.

## Where code lives
Executable code MUST NOT live under docs/.
Kernel code lives under:
- `orket/kernel/v1/`

Tests live under:
- `tests/kernel/v1/`

## Quick links
- Contract Index: `contract-index.md`
- Versioning Policy: `versioning-policy.md`
- Test Policy: `test-policy.md`
- Migration Map: `migration-map-v1.md`
- Roadmap / Cards: `Roadmap/Cards.md`

## Purpose
Define Orket as an OS-class substrate for agentic systems with stable kernel contracts, deterministic execution, and state integrity.

## Program Areas
1. Kernel: frozen core APIs and invariants.
2. Execution: run lifecycle, stage orchestration, replay boundaries.
3. State: memory, persistence, determinism, integrity checks.
4. Security: capabilities, permissions, and policy enforcement.
5. Roadmap: phased delivery cards and dependency ordering.

## Working Rules
1. High-level ideas are captured first, then refined into implementation cards.
2. Contracts are versioned and enforced mechanically.
3. Runtime changes should preserve deterministic test gates.

## Current Inputs
1. `docs/projects/OS/Idea1.md`
2. `docs/projects/OS/Kernel/KERNEL_API_V1.md`
