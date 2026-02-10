# Orket Architecture

Orket follows an **iDesign-inspired architectural pattern** designed to support autonomous agent orchestration with deterministic governance.

## Component Roles & Boundaries

To ensure clear separation of concerns and maintainability, all code must fit into one of the following four categories:

### 1. Managers (The Orchestrators)
- **Role**: Entry points and high-level coordinators. They "know how" but don't "do".
- **Responsibilities**: 
    - Handling external requests (CLI, API).
    - Coordinating multiple Engines to achieve a task.
    - Managing session state and persistence transitions.
- **Example**: `OrchestrationEngine` (despite the name, it acts as a Manager), `PriceDiscoveryManager`.

### 2. Engines (The Doers)
- **Role**: Pure logic and state machines. They "do" but don't "command".
- **Responsibilities**: 
    - Executing specific algorithmic tasks.
    - Handling LLM interactions (via Providers).
    - Computing results without knowing about "sessions" or "external APIs".
- **Example**: `PriceDiscoveryEngine`, `TractionLoop` logic.

### 3. Accessors (The Data Gatekeepers)
- **Role**: Wrappers around external systems (Databases, File I/O, Third-party APIs).
- **Responsibilities**: 
    - Providing a clean, typed interface to messy external data.
    - Enforcing data invariants.
- **Example**: `AsyncCardRepository`, `SQLiteSessionRepository`.

### 4. Utilities (The Helpers)
- **Role**: Stateless, side-effect-free helper functions.
- **Responsibilities**: 
    - String manipulation, date calculations, price normalization.
    - Must be easily testable in isolation.
- **Example**: `price_utils.py`, `naming.py`.

## Directory Structure

```text
orket/
├── orchestration/      # Managers and Orchestration Engines
├── services/           # Governance and Gating (iDesignValidator, ToolGate)
├── infrastructure/     # Accessors (Repositories, DB logic)
├── domain/             # Business logic, Records, and Enums
└── interfaces/         # Entry points (CLI, API)
```

## Governance (iDesign)

The `iDesignValidator` enforces these boundaries at runtime. Any tool execution (like `write_file`) is intercepted to ensure:
1. Files are placed in the correct category directory.
2. Naming conventions match the category (e.g., `*Manager.py`, `*Engine.py`).
3. Complexity thresholds are respected.
