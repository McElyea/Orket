# Orket

Orket is a local-first, state-driven execution engine for automated workflows. It uses an asynchronous traction loop to coordinate LLM turns against a structured card system, enforced by a mechanical state machine.

## Core Mechanics

### 1. The Traction Loop
The engine operates on a continuous traction cycle:
- Scan: Identifies the next priority card in the backlog.
- Prepare: Compiles system instructions based on roles and model dialects.
- Execute: Runs an asynchronous LLM turn to generate tool calls.
- Govern: Validates every tool call and state transition against mechanical boundaries.
- Persist: Commits changes to a local SQLite repository and updates the workspace.

### 2. Mechanical Governance
Orket enforces strict operational boundaries to ensure system integrity:
- State Machine: Prevents illegal status transitions.
- Tool Gating: Restricts file operations to approved boundaries.
- Directory Isolation: Separates execution fixtures from agent output.

### 3. Local-First Sovereignty
Orket is designed to run entirely on local hardware:
- Orchestration: Asynchronous Python engine (`FastAPI` + `aiosqlite`).
- Models: Integration with local `Ollama` instances.
- Storage: Local SQLite database and filesystem-based workspaces.

## Quickstart

1. Install dependencies:
```bash
pip install .
```

2. Set up environment:
Create a `.env` file from `.env.example`.

3. Launch the core:
```bash
python server.py
```
