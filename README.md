# McElyea Orket EOS (v0.3.6)

Orket is a professional‑grade, multi‑agent orchestration engine for autonomous engineering operations.  
Owned and operated by **McElyea**, it utilizes a high‑precision **Prompt Engine** and **iDesign architectural governance** to manage complexity through volatility decomposition.

---

## The McElyea Standard
*Excellence through iteration, transparency in process, and local-first sovereignty.*

Orket v0.3.6 (The Integrity Release) marks the transition from a monolithic core to a decoupled, data‑driven engine aligned with modern enterprise standards.

---

## Core Pillars

### 1. The Prompt Engine (Architecting Intent)
To solve the "Leaf Node Explosion" (Role x Model x Version), Orket separates **Managerial Intent** from **Model Syntax**.
*   **PromptCompiler:** At runtime, the engine compiles the **Role Intent** with the **Model Dialect** using a centralized compiler service.
*   **Atomic Roles:** Role personas are stored as decoupled JSON assets (`model/core/roles/*.json`).
*   **Dialects:** We maintain a library of model-specific grammar (Qwen, Llama, Deepseek). 
*   **Ethos Injection:** The McElyea vision, branding guidelines, and design "Do's and Don'ts" are automatically injected into every agent turn.

### 2. iDesign (Architectural Governance)
We utilize **iDesign** principles (Volatility Decomposition) to maintain structural integrity.
*   **Single Responsibility Principle (SRP):** Issues are refactored into focused models for `metrics` and `verification`, separating operational state from assessment data.
*   **The Complexity Gate:** For tactical projects, we allow "Flat and Fast" structures. However, once an Epic exceeds **7 Issues**, the engine enforces a strict **Manager/Engine/Accessor** component model.
*   **Structural Reconciler:** A self-healing background process that ensures every Card belongs to a parent structure.

### 3. Decoupled Tooling (ToolBox)
The v0.3.6 update introduced a refactored `ToolBox`, splitting monolithic tool logic into specialized, secure services:
*   **FileSystemTools:** Secure, path-sandboxed file operations.
*   **VisionTools:** Multi-modal support including local Stable Diffusion with CPU fallback and hardware detection.
*   **CardManagementTools:** Direct interaction with the Universal Card System.

---

## Security & Sovereignty
*   **Secret Sovereignty:** All sensitive credentials (passwords, API keys) are managed via `.env` files and strictly excluded from version control.
*   **Local-First Execution:** Orchestration and model execution (Ollama) happen entirely on local hardware.
*   **LLM Resiliency:** Built-in exponential backoff and specific error handling for transient model failures.

---

## Quickstart

1. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2. **Setup Environment:**
    Create a `.env` file from the provided template and fill in your secrets.

3. **Launch the Core:**
    ```bash
    python server.py
    ```

4. **Start the Autonomous Loop:**
    ```bash
    python main.py --loop
    ```

---

## Documentation

- `docs/ARCHITECTURE.md` — iDesign roadmap and Volatility Decomposition.
- `docs/PROJECT.md` — Roadmap and McElyea milestones.
- `docs/SECURITY.md` — Integrity-based security model.