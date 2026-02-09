# McElyea Project: Orket Maturation

This document tracks the milestones, lessons learned, and quality benchmarks for the Orket platform.

## Organization: McElyea
**Vision:** Local-first autonomous market intelligence.
**Ethos:** Excellence through iteration, transparency, and sovereignty.

---

## Current Status: v0.3.6 (The Integrity Release)

We have pivoted from a descriptive orchestration model to a **mechanical enforcement model** based on a brutal architectural audit. v0.3.6 focuses on security, tool decoupling, and Single Responsibility Principle (SRP) compliance.

---

## v0.3.6 Milestones (Completed)
*   **Secret Rotation & Sovereignty:** Moved all sensitive credentials to `.env`; implemented `.gitignore` guards for all `.db` and `.json` settings.
*   **Tool Decomposition:** Refactored the monolithic `ToolBox` into specialized, sandboxed toolsets (`FileSystem`, `Vision`, `Cards`).
*   **SRP-Based Schema:** Refactored `IssueConfig` to decouple metrics from verification logic.
*   **Model Resiliency:** Implemented exponential backoff retry logic and specific LLM error handling.
*   **Hardware-Aware Multi-Modal:** Vision tools now automatically detect CUDA/CPU and use configurable models.

---

## Maturation Roadmap

### Phase 1: Ruthless Simplification (DONE)
*   **Merge Skills into Roles:** Eliminate the complexity tax of dual persona layers.
*   **Unified Configuration:** Established the `config/` directory with prioritized overrides.
*   **Atomic Card Identity:** Ensure every Rock, Epic, and Issue has a stable, non-volatile ID.

### Phase 2: Mechanical Enforcement (Current)
*   **Hard State Machines:** Implement Python-level guards for transitions (e.g., No `DONE` without Verifier sign-off).
*   **Tool Gating:** Intercept `write_file` and state changes at the engine level to enforce organizational invariants.
*   **Integration Testing:** Establish a robust suite of core flow tests (Prompt Compilation, Tool Execution).

### Phase 3: Elegant Failure & Recovery
*   **The Elegant Stop:** When an invariant is broken, the engine terminates with a clear "Policy Violation" report.
*   **Memory Hygiene:** Implement logic to clear model context/memory on restart to prevent hallucination drift.
*   **Restart Mechanism:** Enable resuming a run from the last valid state machine checkpoint.

### Phase 4: Empirical Verification (North Star)
*   **FIT Fixtures:** Integrated testing where Orket runs code and verifies results before advancing cards.
*   **Local Sandboxing:** Host and verify applications in an isolated environment.

---

## iDesign in Practice
We utilize iDesign as a "Complexity Gate."
*   **Current Threshold:** 7 Issues.
*   **Mandatory Structure:** Managers, Engines, Accessors.
*   **Goal:** To ensure that Orket never produces "Spaghetti Code" as it grows.
