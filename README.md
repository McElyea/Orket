# McElyea Orket EOS (v0.3.5)

Orket is a professional‑grade, multi‑agent orchestration engine for autonomous engineering operations.  
Owned and operated by **McElyea**, it utilizes a high‑precision **Prompt Engine** and **iDesign architectural governance** to manage complexity through volatility decomposition.

---

## The McElyea Standard
*Excellence through iteration, transparency in process, and local-first sovereignty.*

Orket v0.3.5 (The Reforge Release) marks the transition from a monolithic core to a decoupled, data‑driven engine aligned with modern enterprise standards.

---

## The Engine of Operations (EOS) & The Card System

At the heart of Orket is the **Engine of Operations (EOS)**. We believe that autonomous work must be as structured and accountable as a professional human team. We achieve this through our **Universal Card System**, where every unit of work is a polymorphic object (a "Card") with a stateful lifecycle.

*   **Rocks (Strategic):** High-level milestones and quarterly objectives.
*   **Epics (Tactical):** Functional groupings of issues that define a specific feature or initiative.
*   **Issues (Operational):** The atomic unit of execution. Every issue is assigned to a specific "Seat" (Role) and moves through a professional pipeline:
    `Ready` -> `In Progress` -> `Blocked` | `Waiting_For_Developer` -> `Ready_For_Testing` -> `Code_Review` -> `Done`.

This system ensures **Full Traceability** and **Velocity Tracking**, allowing the McElyea organization to measure progress with high fidelity.

---

## Core Pillars

### 1. The Prompt Engine (Architecting Intent)
To solve the "Leaf Node Explosion" (Role x Model x Version), Orket separates **Managerial Intent** from **Model Syntax**.
*   **Atomic Roles:** Role personas are stored as decoupled JSON assets (`model/core/roles/*.json`). This ensures that the *identity* of an Architect or Coder is independent of the underlying code.
*   **Dialects:** We maintain a library of model-specific grammar (Qwen, Llama, Deepseek). At runtime, the engine compiles the **Role Intent** with the **Model Dialect**.
*   **Ethos Injection:** The McElyea vision, branding guidelines, and design "Do's and Don'ts" are automatically injected into every agent turn, ensuring consistency across all generated artifacts.

### 2. iDesign (Architectural Governance)
We utilize **iDesign** principles (Volatility Decomposition) to maintain structural integrity. Instead of designing around volatile features, we design around the areas of change.
*   **The Complexity Gate:** For tactical projects, we allow "Flat and Fast" structures. However, once an Epic exceeds **7 Issues**, the engine enforces a strict **Manager/Engine/Accessor** component model.
*   **Structural Reconciler:** A self-healing background process that ensures every Card belongs to a parent structure. Orphaned epics are automatically adopted by the **"Run the Business"** Rock, ensuring zero board drift.

### 3. The WorkStation
A centralized Command & Control UI providing:
*   **Collapsible Traction Tree:** Deep navigation into the Rock/Epic/Issue hierarchy.
*   **Binocular Preview:** Toggle between file editing and fully-resolved "Compiled Prompts" to see exactly what the LLM sees before execution.
*   **Member HUD:** Real-time metrics on compute (tokens) and traction (lines of code written).

---

## New in v0.3.5

- **Strategic Refactor:** Centralized orchestration into a core `OrchestrationEngine`.
- **Atomic Roles:** Roles are now versionable, interchangeable JSON assets.
- **Model Selector:** Dynamic engine selection based on organizational and user standards.
- **NoteStore:** Deterministic, ephemeral inter-agent communication via notes.
- **Code Review State:** Mandatory audit gate before tasks move to "Done."

---

## Quickstart

1. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2. **Launch the Core:**
    ```bash
    python server.py
    ```

3. **Start the Autonomous Loop:**
    ```bash
    python main.py --loop
    ```

---

## Documentation

- `docs/ARCHITECTURE.md` — iDesign roadmap and Volatility Decomposition.
- `docs/PROJECT.md` — Roadmap and McElyea milestones.
- `docs/SECURITY.md` — Integrity-based security model.
