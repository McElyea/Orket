# Orket

Orket is a local-first, state-driven execution engine for automated workflows. It uses an asynchronous traction loop to coordinate LLM turns against a structured card system, enforced by a mechanical state machine.

## Core Mechanics

### 1. The Traction Loop
The engine operates on a continuous "traction" cycle:
- **Scan**: Identifies the next priority card in the backlog.
- **Prepare**: Compiles system instructions based on roles and model dialects.
- **Execute**: Runs an asynchronous LLM turn to generate tool calls.
- **Govern**: Validates every tool call and state transition against mechanical boundaries.
- **Persist**: Commits changes to a local SQLite repository and updates the workspace.

### 2. Mechanical Governance
Orket enforces strict operational boundaries to ensure system integrity:
- **State Machine**: Prevents illegal status transitions (e.g., a card cannot jump from `READY` to `DONE` without verification).
- **Tool Gating**: Restricts file operations to specific sandbox directories (`agent_output/`) to prevent unauthorized system access.
- **Directory Isolation**: Separates execution fixtures from agent output to eliminate write-then-execute vulnerabilities.

### 3. Local-First Sovereignty
Orket is designed to run entirely on local hardware:
- **Orchestration**: Asynchronous Python engine (`FastAPI` + `aiosqlite`).
- **Models**: Integration with local `Ollama` instances.
- **Storage**: Local SQLite database and filesystem-based workspaces.

## Current Limitations
- **Orchestration**: Single-threaded rock execution (concurrent rocks not yet supported).
- **Environment**: Requires local Docker for sandbox deployments.
- **Validation**: API inputs currently rely on loose dictionary mapping; Pydantic enforcement is incomplete.

## Quickstart

1. **Install dependencies:**
    ```bash
    pip install .
    ```

2. **Setup Environment:**
    Create a `.env` file from the provided template.

3. **Launch the Core:**
    ```bash
    python server.py
    ```