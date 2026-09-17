# Explicit epic artifact export recovery

## Summary
- Change title: Fence an interrupted export owner and authorize an exact-commit retry.
- Owner: Orket Core, architectural-truth BT-3.
- Date: 2026-09-13.
- Affected contract(s): `docs/specs/GITEA_ARTIFACT_EXPORT_CONTRACT.md`,
  `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`, `CURRENT_AUTHORITY.md`.

## Delta
- Current behavior: an unconfirmed phase-four export has no owner recovery path,
  including process death after retaining intent but before the first push.
- Proposed behavior: one explicit, bound recovery request can fence the prior
  local export owner, confirm remote delivery, or grant one retry of the original
  Git commit. Matching reentry does not grant a second dispatch. The stored
  admission, outcome, acceptance and intent remain authoritative.
- Why this break is required now: post-initialization export recovery is a
  remaining required plan gate; a permanent uncertainty marker alone cannot
  complete interrupted delivery.

## Migration Plan
1. Compatibility window: no inferred ownership upgrade. Older phase-four records
   retain confirmation-only recovery and cannot request a retry.
2. Migration steps: add a journal-owned dispatch record and bind new preparation
   and publication artifacts to it; pass an explicit recovery input through the
   existing canonical Python epic entry path. Keep automatic recovery read-only.
3. Validation gates: real SQLite races and corruption, paused original owner,
   native process death, conflicting/idempotent recovery, actual localhost Gitea
   commit and branch observations, installed-platform proof and live llama.cpp
   workload delivery without repeated work.

## Rollback Plan
1. Rollback trigger: duplicate dispatch authority, changed intent or false
   completion under recovery.
2. Rollback steps: disable explicit retry admission, preserve dispatch history and
   return to confirmation-only recovery. Do not discard the new owner records.
3. Data/state recovery notes: an old binary cannot validate new owner markers;
   rollback must reject marked records or include their reader. Preserve all
   original Git objects, journal rows and published references.

## Versioning Decision
- Version bump type: patch with the eventual versioned release commit.
- Effective version/date: worktree implementation, 2026-09-13; no release here.
- Downstream impact: opt-in Python recovery input and additive durable owner
  references. Arbitrary remote hooks, unknown workload effects, remote takeover
  endpoints and cross-journal recovery remain outside this scoped contract.
