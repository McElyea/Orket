# Orket OS Program (v1)

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
- Implementation Plan: `IMPLEMENTATION_PLAN.md`
- Next Part v1 Requirements: `NEXT_PART_V1_REQUIREMENTS.md`
- Roadmap / Cards: `Roadmap/Cards.md`
- Closure Checklist: `Roadmap/Closeout-Checklist.md`
- v1.2 Archive Pack: `../archive/OS-v1.2/README.md`
