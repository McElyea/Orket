# Orket Security & Governance (v0.3.8)

This document defines the Vibe Rail integrity model.

## Integrity-Based Security
At Vibe Rail, security is a subset of system integrity. We ensure that every agent turn is traceable and constrained by organizational rules.

### 1. Environment-Based Credentials
*   **Environment Management:** All sensitive credentials (passwords, API keys, secret keys) are stored in a local `.env` file.
*   **Git Guards:** The `.gitignore` policy strictly excludes `.env`, `*.db`, and `user_settings.json` from version control.

### 2. Hardware & Path Sandboxing
The refactored `FileSystemTools` enforces strict workspace boundaries:
*   **Access Control:** Agents are strictly forbidden from traversing outside the `workspace/` and approved `references/` domains.
*   **Write Restriction:** Write operations are limited exclusively to the active workspace.
*   **Hardware Awareness:** Vision tools detect hardware capabilities (CUDA) to prevent system crashes on non-GPU environments.

### 3. LLM Resiliency & Error Handling
*   **Exponential Backoff:** The `LocalModelProvider` implements retry logic for transient connection or timeout errors, preventing partial execution failures.
*   **Bubbling Errors:** We no longer swallow exceptions as model text. Critical failures (timeouts, connection drops) are raised as specific `OrketError` types for the orchestrator to handle.

### 4. Prompt Injection Hardening
The `PromptCompiler` service acts as a grammar-level sandbox. By separating **Intent (Role)** from **Syntax (Dialect)**, we ensure that an agent's identity and constraints are injected at compile-time and cannot be overridden by user or model input.

### 5. Code Review Gate
No Card can move to `Done` without entering the `CODE_REVIEW` state. This creates a "Logical Freezer" that prevents unverified code from being considered functional.

## Audit Trails
The `NoteStore` and root `orket.log` provide a high-fidelity audit trail of exactly who (Seat), said what (Prompt), and did what (Tool Call) during every session.
