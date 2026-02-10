# Orket

Orket is a professional-grade orchestration engine for autonomous engineering operations.
It utilizes a high-precision **Prompt Engine** and **iDesign architectural governance** to manage complexity through volatility decomposition.

---

## Core Philosophy
*Excellence through iteration, transparency in process, and local-first sovereignty.*

Orket v0.3.8 continues the backend stabilization phase with enhanced diagnostics, priority-based scheduling, and robust state machine governance.

---

## Core Pillars

### 1. The Prompt Engine (Architecting Intent)
To solve the "Leaf Node Explosion" (Role x Model x Version), Orket separates **Managerial Intent** from **Model Syntax**.
*   **PromptCompiler:** At runtime, the engine compiles the **Role Intent** with the **Model Dialect** using a centralized compiler service.
*   **Atomic Roles:** Role personas are stored as decoupled JSON assets (`model/core/roles/*.json`).
*   **Dialects:** We maintain a library of model-specific grammar (Qwen, Llama, Deepseek). 
*   **Ethos Injection:** Organizational vision, branding guidelines, and design "Do's and Don'ts" are automatically injected into every system turn.

### 2. iDesign (Architectural Governance)
We utilize **iDesign** principles (Volatility Decomposition) to maintain structural integrity.
*   **Single Responsibility Principle (SRP):** Issues are refactored into focused models for `metrics` and `verification`, separating operational state from assessment data.
*   **The Complexity Gate:** For tactical projects, we allow "Flat and Fast" structures. However, once an Epic exceeds **7 Issues**, the engine enforces a strict **Manager/Engine/Accessor** component model.
*   **Structural Reconciler:** A self-healing background process that ensures every Card belongs to a parent structure.

### 3. Decoupled Tooling (ToolBox)
The v0.3.x series introduced a refactored `ToolBox`, splitting monolithic tool logic into specialized, secure services:
*   **FileSystemTools:** Secure, path-sandboxed file operations.
*   **VisionTools:** Multi-modal support including local Stable Diffusion with CPU fallback and hardware detection.
*   **CardManagementTools:** Direct interaction with the Universal Card System.

### 4. State Machine with Diagnostic Intelligence
The v0.3.8 update enhances governance with explicit wait reason tracking:
*   **WaitReason Enforcement:** Cards entering BLOCKED or WAITING_FOR_DEVELOPER states must specify why (RESOURCE, DEPENDENCY, REVIEW, INPUT).
*   **Bottleneck Detection:** Configurable thresholds prevent alert fatigue while catching real bottlenecks.
*   **Multi-Role Validation:** System actors can hold multiple roles, enabling flexible yet secure state transitions.

---

## Security & Sovereignty
*   **Environment Management:** All sensitive credentials (passwords, API keys) are managed via `.env` files and strictly excluded from version control.
*   **Local-First Execution:** Orchestration and model execution (Ollama) happen entirely on local hardware.
*   **LLM Resiliency:** Built-in exponential backoff and specific error handling for transient model failures.

---

## Documentation

- `CHANGELOG.md` — Version history and release notes.
- `docs/ARCHITECTURE.md` — iDesign roadmap and Volatility Decomposition.
- `docs/PROJECT.md` — Project roadmap and development milestones.
- `docs/SECURITY.md` — Integrity-based security model.
- `docs/bottleneck_thresholds.md` — Bottleneck detection configuration.
