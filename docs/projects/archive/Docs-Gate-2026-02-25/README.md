# Docs Gate Project

Date: 2026-02-24

## Purpose
Define and deliver a deterministic documentation verification gate for Orket so doc mutations remain auditable, safe, and CI-enforceable.

## Canonical Docs
1. `docs/projects/archive/Docs-Gate-2026-02-25/README.md`
2. `docs/projects/archive/Docs-Gate-2026-02-25/01-REQUIREMENTS.md`
3. `docs/projects/archive/Docs-Gate-2026-02-25/02-IMPLEMENTATION-PLAN.md`
4. `docs/projects/archive/Docs-Gate-2026-02-25/03-MILESTONES.md`

## Scope
1. Deterministic linting for docs under `docs/projects/core-pillars/`.
2. Contract checks for relative links, canonical document presence, and required active-doc headers.
3. Acceptance tests that are executable and non-interactive.
4. CI-ready command contract for docs verification profiles.

## Non-Goals
1. Full markdown semantic parsing and anchor validation.
2. Natural-language quality scoring.
3. Automatic content rewriting.
4. Cross-repo or remote registry synchronization.
