# Tech Debt Project

Last updated: 2026-02-28

## Purpose

Track and resolve technical debt identified in the 2026-02-28 deep code review. This is maintenance work -- not features. Every item here makes the codebase safer, simpler, or easier to extend.

## Source

Findings extracted from `docs/internal/ClaudeReview.md` (Claude Opus 4.6, 2026-02-28 full audit).

## Documents

| File | Purpose |
|---|---|
| `01-REQUIREMENTS.md` | All findings organized by severity with acceptance criteria |
| `02-PLAN.md` | Implementation phases, ordering, and status |

## Scope

Security fixes, dead code removal, exception narrowing, test gaps, async correctness, and structural simplification. No new features. No refactoring for its own sake.
