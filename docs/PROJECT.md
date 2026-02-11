# Project Overview

This document defines the stable project context for Orket.

## Organization
- Name: Vibe Rail
- Vision: Local-first autonomous market intelligence
- Ethos: Excellence through iteration, transparency, and sovereignty

## Operating Model
- Architectural authority: `docs/OrketArchitectureModel.md`
- Forward work authority: `docs/ROADMAP.md`
- Version/change history: `CHANGELOG.md`

## Engineering Constraints
- Volatile behavior must be isolated behind explicit decision boundaries.
- Runtime actions must pass mechanical governance before state mutation.
- Local-first execution is the default operating assumption.

## Complexity Gate
- iDesign threshold: 7 issues
- Preferred structure at threshold and above: managers, engines, accessors
