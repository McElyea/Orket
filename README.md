# Orket EOS (v0.3.0)

Orket is a local‑first, multi‑agent orchestration engine for professional engineering operations.  
It coordinates a team of AI agents through an iDesign-aligned hierarchy (Rocks, Epics, Cards) and utilizes a dynamic Prompt Engine to separate role intent from model-specific syntax.

Orket emphasizes **Structural Integrity**, **Volatility Decomposition**, and **Traceability**. It is designed for production-grade engineering work where architectural standards and local execution are paramount.

---

## What's New in v0.3.0

- **Card-Based Hierarchy** — Track work through **Cards** (The generic polymorphic type).
    - **Rock** (Strategic Card) — High-level goals.
    - **Epic** (Tactical Card) — Thematic groups.
    - **Issue** (Operational Card) — The atomic unit of execution (e.g., `COR26-0001`).
- **The Prompt Engine** — Separation of **Skills** (Managerial intent) and **Dialects** (Model-specific syntax) to solve the leaf-node explosion problem.
- **iDesign Training** — Injected constraints forcing models to follow strict structural patterns: Managers, Engines, Accessors, and Utilities.
- **Vendor Abstraction** — Unified interface for Gitea, ADO, and Jira integrations.
- **Reforge System** — Automated model optimization loop to ensure 10/10 tool-calling precision.

---

## Why Orket

Modern AI tools often operate as opaque, single‑shot systems. Orket provides the **Engine of Operations**:

- **Volatility-Based Decomposition** — Encapsulates change within specific components.
- **Local execution** — Run models on your machine using Ollama.
- **Strict Contracts** — Models interact via strictly validated JSON and DSL contracts.
- **Full Traceability** — Every action is a logged event, move through Kanban stages, and a persisted artifact.

---

## Core concepts

- **Card** — The base polymorphic type for all tracked work.
- **Rock** — A strategic Card (milestone).
- **Epic** — A tactical Card (group of related issues).
- **Issue** — An operational Card (atomic work unit, e.g. `COR26-0001`).
- **Skill** — The "Manager" intent of a role (Platform-agnostic).
- **Dialect** — The "Utility" syntax for a specific model (e.g., Qwen vs. Llama).
- **Workstation** — The Command & Control UI for managing the Project Board and File Explorer.

---

## iDesign Directory Structure

Orket enforces a professional directory structure for all generated code:
- `/controllers` — External API and entry points.
- `/managers` — Use-case coordination and workflow logic.
- `/engines` — Business rules and computational algorithms.
- `/accessors` — External tool and data interaction.
- `/utils` — Cross-cutting logic.
- `/tests` — Unit and integration tests.

---

## Quickstart

1. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2. **Orkestrate the Engine (First Run):**
    ```bash
    python main.py --rock initialize_orket
    ```

3. **View the Board:**
    ```bash
    python main.py --board
    ```

4. **Run a Standalone Card:**
    ```bash
    python main.py --card "Generate system status report"
    ```

---

## Documentation

- `docs/ARCHITECTURE.md` — The iDesign roadmap and system relationships.
- `docs/PROJECT.md` — Roadmap and v0.3.0 milestones.
- `docs/SECURITY.md` — Local execution and safety notes.
- `CONTRIBUTING.md` — Contributor guidelines.