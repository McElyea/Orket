# Orket Architecture: Volatility Decomposition (v0.3.5)

This document defines the structural and philosophical foundations of the McElyea Orket engine.

---

# 1. iDesign & The McElyea Gate

At McElyea, we treat system design as the management of complexity. We avoid designing around features, which are volatile, and instead design around **Encapsulated Volatility**.

### The Complexity Gate
Orket enforces architectural discipline through a quantified threshold:
*   **Issues <= 7:** "Flat and Fast" (Tactical) projects allowed.
*   **Issues > 7:** Mandatory iDesign structure (Managers, Engines, Accessors).

### Component Definitions
*   **Managers:** Conductors of use-cases. They own the workflow.
*   **Engines:** Pure business logic. They know nothing of state or external resources.
*   **Accessors:** Wrappers for volatility (APIs, Databases, Files).

---

# 2. The Prompt Engine (Intelligent Compile)

The v0.3.5 refactor introduced the **Data-Driven Prompt Engine**, which eliminates the "Role-Model-Version" matrix explosion.

### The Merge Strategy
At runtime, the `OrchestrationEngine` compiles three distinct vectors:
1.  **Intent (Atomic Role):** The professional persona (`coder.json`, `architect.json`).
2.  **Syntax (Dialect):** The model-specific grammar (`llama.txt`, `qwen.txt`).
3.  **Ethos (Organization):** Global McElyea standards and branding "Do's and Don'ts."

---

# 3. Structural Reconciler

To prevent "Board Drift," Orket runs a reconciliation sweep on every startup.
*   **Adoption:** Any orphaned Epic is moved to the **"Run the Business"** Rock.
*   **Catchment:** Any orphaned Issue is moved to the **"unplanned support"** Epic.
*   **Integrity:** Ensures the Traction Tree is always a valid, traversable graph.

---

# 4. State Machine (Flow of Work)

Cards move through a professional lifecycle:
`Ready` -> `In Progress` -> `Blocked` -> `Ready_For_Testing` -> `Code_Review` -> `Done`.

The **Code_Review** state is a mandatory "Freezer" where work awaits an audit score (Target: > 7.0) before finalization.