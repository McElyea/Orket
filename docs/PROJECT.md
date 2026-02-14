# Project Overview

This document defines the stable project context for Orket.

## Core Idea
- Role contracts are fixed and explicit.
- Models are unique and capability-variable.
- Routing and policy must select models by demonstrated role capability.
- Governance must make failure modes deterministic and observable.

## Organization
- Name: Vibe Rail
- Vision: Local-first autonomous market intelligence
- Ethos: Excellence through iteration, transparency, and sovereignty

## Operating Model
- Architectural authority: `docs/ARCHITECTURE.md`
- Forward work authority: `docs/ROADMAP.md`
- Version/change history: `CHANGELOG.md`

## Engineering Constraints
- Volatile behavior must be isolated behind explicit decision boundaries.
- Runtime actions must pass mechanical governance before state mutation.
- Local-first execution is the default operating assumption.

## Complexity Gate
- iDesign threshold: 7 issues
- Preferred structure at threshold and above: managers, engines, accessors
