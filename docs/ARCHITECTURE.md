# Orket Architecture: Volatility Decomposition (v0.3.9)

This document defines the structural and philosophical foundations of the Vibe Rail Orket engine.

---

# 1. iDesign & The Vibe Rail Gate

At Vibe Rail, we treat system design as the management of complexity. We avoid designing around features, which are volatile, and instead design around **Encapsulated Volatility**.

### The Complexity Gate
Orket enforces architectural discipline through a quantified threshold:
*   **Issues <= 7:** "Flat and Fast" (Tactical) projects allowed.
*   **Issues > 7:** Mandatory iDesign structure (Managers, Engines, Accessors).

### SRP-Compliant Cards
To ensure the Single Responsibility Principle, our **IssueConfig** is decomposed into specialized concerns:
*   **Metrics:** Focused on scoring, grading, and shippability thresholds.
*   **Verification:** Focused on fixtures, scenarios, and execution results.

---

# 2. The Prompt Engine (Intelligent Compile)

The v0.3.6 refactor introduced the `PromptCompiler` service, which eliminates the "Role-Model-Version" matrix explosion.

### The Merge Strategy
At runtime, the `ExecutionPipeline` compiles three distinct vectors:
1.  **Intent (Atomic Role):** The professional persona (`roles/*.json`).
2.  **Syntax (Dialect):** The model-specific grammar (`dialects/*.json`).
3.  **Ethos (Organization):** Global Vibe Rail standards and architectural policy.

---

# 3. Configuration Hierarchy (ConfigLoader)

Orket utilizes a prioritized configuration system to ensure both flexibility and organizational control:
1.  **Unified Config (`config/`):** Primary location for organization and department standards.
2.  **Legacy Assets (`model/{dept}/`):** Department-specific assets and overrides.
3.  **Core Fallbacks (`model/core/`):** The organizational "Safety Net."

---

# 4. Tool Sovereignty & Decoupling

The monolithic `ToolBox` has been decomposed into specialized toolsets to improve security and extensibility:
*   **FileSystemTools:** Implements path-sandboxing and workspace boundaries.
*   **VisionTools:** Manages multi-modal assets (Stable Diffusion) with hardware-aware fallbacks (CUDA/CPU).
*   **CardManagementTools:** Encapsulates the persistence and lifecycle of the Card System.

---

# 5. State Machine (Flow of Work)

Cards move through a professional lifecycle:
`Ready` -> `In Progress` -> `Blocked` -> `Ready_For_Testing` -> `Code_Review` -> `Done`.

The **Code_Review** state is a mandatory "Freezer" where work awaits an audit score before finalization.

### v0.3.8 Enhancements: Diagnostic Governance

The state machine now enforces explicit diagnostic tracking:

*   **WaitReason Requirement:** Cards transitioning to `BLOCKED` or `WAITING_FOR_DEVELOPER` must specify why:
    *   `RESOURCE` — Waiting for available resources (VRAM, LLM slot, etc.)
    *   `DEPENDENCY` — Waiting for another card to complete
    *   `REVIEW` — Waiting for human review/approval
    *   `INPUT` — Waiting for human input/clarification

*   **Multi-Role Validation:** System actors can now hold multiple roles, allowing flexible transitions while maintaining integrity gates (e.g., only `integrity_guard` can finalize issues to `DONE`).

*   **Bottleneck Detection:** Configurable thresholds (`config/bottleneck_thresholds.json`) distinguish normal operation from chronic bottlenecks, preventing alert fatigue.

### Priority System Evolution

Priorities migrated from strings ("High"/"Medium"/"Low") to floats (3.0/2.0/1.0) for precise sorting:
*   **3.0 — High:** Critical path items, blockers
*   **2.0 — Medium:** Standard work items
*   **1.0 — Low:** Nice-to-have, cleanup tasks

Legacy string priorities are automatically converted via field validators for backward compatibility.