# McElyea Project: Orket Maturation

This document tracks the milestones, lessons learned, and quality benchmarks for the Orket platform.

## Organization: McElyea
**Vision:** Local-first autonomous market intelligence.
**Ethos:** Excellence through iteration, transparency, and sovereignty.

---

## Current Status: v0.3.5 (The Reforge Release)

We have pivoted from a descriptive orchestration model to a **mechanical enforcement model** based on a brutal architectural audit.

---

## Maturation Roadmap

### Phase 1: Ruthless Simplification (Current)
*   **Merge Skills into Roles:** Eliminate the complexity tax of dual persona layers.
*   **Simplify Dialects:** Consolidate output contracts to focus only on tool-calling precision.
*   **Atomic Card Identity:** Ensure every Rock, Epic, and Issue has a stable, non-volatile ID.

### Phase 2: Mechanical Enforcement
*   **Hard State Machines:** Implement Python-level guards for transitions (e.g., No `DONE` without Verifier sign-off).
*   **Tool Gating:** Intercept `write_file` and state changes at the engine level to enforce organizational invariants.
*   **The Verifier Pivot:** Transform the "Integrity Guard" from an advisor to a gatekeeper.

### Phase 3: Elegant Failure & Recovery
*   **The Elegant Stop:** When an invariant is broken, the engine terminates with a clear "Policy Violation" report.
*   **Memory Hygiene:** Implement logic to clear model context/memory on restart to prevent hallucination drift.
*   **Restart Mechanism:** Enable resuming a run from the last valid state machine checkpoint.

### Phase 4: Empirical Verification (North Star)
*   **FIT Fixtures:** Integrated testing where Orket runs code and verifies results before advancing cards.
*   **Local Sandboxing:** Host and verify applications in an isolated environment.

---

## Case Study: Sneaky Price Watch
The maturation of the Price Watcher project served as our baseline for Quality Auditing.

*   **Initial Audit Score:** 4.1 / 10 (Non-Shippable).
*   **Lessons Learned (Negative):** Empty file syndrome, "Headless" gap.
*   **Lessons Learned (Positive):** Playwright stealth worked exceptionally well.
*   **Action Plan:** Transitioned to iDesign: False (Tactical/Flat) to simplify logic and merge arbitrage artifacts.

---

## iDesign in Practice
We utilize iDesign as a "Complexity Gate."
*   **Current Threshold:** 7 Issues.
*   **Mandatory Structure:** Managers, Engines, Accessors.
*   **Goal:** To ensure that Orket never produces "Spaghetti Code" as it grows.