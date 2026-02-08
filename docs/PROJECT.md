# McElyea Orket: Project Maturation (v0.3.5)

This document tracks the milestones, quality benchmarks, and the "McElyea Reforge" results.

## Current Milestone: v0.3.5 (The Reforge)

We have successfully migrated Orket from an implicit monolithic core to an explicit, data-driven orchestration engine.

### Reforge Accomplishments
*   **Decoupled Orchestration:** Moved all logic from CLI/API into a single `OrchestrationEngine`.
*   **Atomic Roles:** Extracted roles from code into `model/core/roles/*.json`.
*   **Model Selector:** Centralized engine choices based on `user_settings.json` and Organization rules.
*   **NoteStore:** Implemented deterministic, ephemeral inter-agent tactical notes.
*   **UI Recovery:** Restored the WorkStation, added collapsible trees, and the "Binocular" preview mode.

---

## Roadmap

### v0.4.0 (Autonomous Auditor)
*   **Automated QA:** Agents that generate "QA Cards" automatically when project scores fall below 7.0.
*   **Gated Handoffs:** Mandatory "Member-to-Member Memos" via the NoteStore.

### v0.5.0 (Multi-Model Swarm)
*   **Parallel Coordination:** Supporting single-turn Swarm strategies (Sequential vs Parallel).
*   **Cross-Departmental Loops:** Autonomous work pulling from Marketing, Product, and Engineering simultaneously.

---

## Lessons Learned Ledger (v0.3.5)

### Positive
*   **Refactor Clarity:** Centralizing the engine reduced "Architecture Smearing" and simplified API maintenance.
*   **Atomic Roles:** Moving roles to JSON made it possible to update agent personas without restarting the server.

### Negative
*   **ID Volatility:** Auto-generated IDs in Pydantic caused 500 errors in the previewer. Resolved by adding stable IDs to assets.
*   **Empty File Syndrome:** Modular scaffolding led to "Done" cards with no logic. Resolved by the 7-Issue iDesign Gate.
