# Orket Architecture: Loop & Governance

This document defines the mechanical operation of the Orket execution engine.

---

## 1. Structural Enforcement

Orket uses structural rules to manage workflow complexity.

### The Complexity Gate
The engine enforces a component structure based on the quantity of work:
*   Issues <= 7: "Flat" structure allowed (simple list of issues).
*   Issues > 7: Mandatory structural decomposition (Managers, Engines, Accessors).

### Card Separation
Work units (Cards) are decomposed into specialized models:
*   Metrics: Tracking scores and completion thresholds.
*   Verification: Defining fixture paths and test scenarios.

---

## 2. Prompt Compilation

The PromptCompiler assembles system instructions at runtime by merging three vectors:
1.  Intent: The persona and toolset defined in roles/*.json.
2.  Syntax: The model-specific formatting rules defined in dialects/*.json.
3.  Context: The current organizational ethos and design rules.

---

## 3. Data Persistence

Orket utilizes an asynchronous repository pattern for all state management:
*   AsyncCardRepository: Manages card states, comments, and transactions using aiosqlite.
*   WebhookDatabase: Tracks PR review cycles and event history.
*   FileSystem: All file operations are non-blocking and path-validated.

---

## 4. State Machine (Lifecycle Enforcement)

All work units follow a enforced lifecycle:
Ready -> In Progress -> Ready_For_Testing -> Code_Review -> Done.

### Governance Gates
*   WaitReason: Transitions to BLOCKED require an explicit reason (RESOURCE, DEPENDENCY, REVIEW, INPUT).
*   Integrity Guard: Transitions to DONE are restricted to specific system roles.
*   Boundary Enforcement: Tool calls that attempt to write outside of the agent_output/ directory result in immediate card blockage and a policy violation report.