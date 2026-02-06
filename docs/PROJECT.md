# Orket Project Overview

This document tracks the roadmap, decisions, and long‑term direction of Orket.

## Vision

Orket aims to be the most transparent, deterministic, local‑first multi‑agent automation platform for engineering work.

## Roadmap

### Near‑term

- Complete migration to Band + Score architecture  
- Expand Venue capabilities  
- Add richer Prelude options  
- Improve tool dispatcher safety  
- Add CLI subcommands  

### Mid‑term

- Add Session replay  
- Add structured tool schemas  
- Add Band‑level capability profiles  
- Add Score templates  

### Long‑term

- UI for inspecting Sessions  
- Visual orchestration graph  
- Plugin system for tools  
- Multi‑Venue pipelines  

## Architectural Decisions (ADRs)

### ADR 001 — Band is the single source of truth for roles  
Roles, prompts, and tools belong exclusively to Bands.

### ADR 002 — Score defines orchestration only  
Scores reference roles but never define them.

### ADR 003 — Venue binds Band + Score  
Venue is the environment configuration layer.

### ADR 004 — Prelude is optional  
Prelude is a first‑class stage but can be disabled.

## Migration Notes

- teams.json replaced by bands/ + scores/  
- orchestrator updated to use Venue → Band → Score  
- dispatcher now enforces Band‑level tool permissions  

## Versioning Strategy

Semantic versioning:

MAJOR — breaking changes  
MINOR — new features  
PATCH — fixes

## Current Status (v0.2.1-patched)

As of February 6, 2026, the core orchestration engine has been repaired and is fully functional:
- **Hybrid Tool Parsing:** Agents now support both JSON and the `TOOL/PATH/CONTENT` DSL.
- **Stateful Workflows:** The `orchestrate` loop now passes the full transcript to agents, allowing them to see previous steps and plans.
- **Runtime Notes:** Implemented the `NOTES_UPDATE` mechanism for inter-agent communication (e.g., Task Decomposition).
- **Workspace Safety:** Tools now dynamically resolve relative paths against the active workspace and are correctly authorized by the `FilesystemPolicy`.
- **Verified Roles:** Architect, Coder, and Reviewer are now correctly using tools and sharing context.
  