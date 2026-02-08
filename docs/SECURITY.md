# Orket Security & Governance (v0.3.5)

This document defines the McElyea integrity model.

## Integrity-Based Security
At McElyea, security is a subset of system integrity. We ensure that every agent turn is traceable and constrained by organizational rules.

### 1. Code Review Gate
No Card can move to `Done` without entering the `CODE_REVIEW` state. This creates a "Logical Freezer" that prevents unverified code from being considered functional.

### 2. Prompt Injection Hardening
The separation of **Skill (Intent)** and **Dialect (Syntax)** acts as a grammar-level sandbox. Agents cannot "escape" their persona because their identity is injected at compile-time by the `OrchestrationEngine`.

### 3. Local-First Sovereignty
*   **Zero-Cloud Defaults:** All orchestration and model execution (Ollama) happen on local hardware.
*   **Filesystem Policy:** Agents are strictly forbidden from traversing outside the `workspace/` and `product/` domains.

## Audit Trails
The `NoteStore` and root `orket.log` provide a high-fidelity audit trail of exactly who (Seat), said what (Prompt), and did what (Tool Call) during every session.
