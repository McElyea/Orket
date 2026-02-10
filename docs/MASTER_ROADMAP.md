# Orket Master Roadmap: The Path to v1.0

This is the unified source of truth for the Orket platform, combining the original roadmap vision with the February 2026 reconstruction requirements.

---

## Current Phase: v0.4.0 Reconstruction (Week 1-2)
**Goal**: Stabilize the core, fix critical security vulnerabilities, and reach "Functioning" status.

### 1. Immediate Next Steps (Day 1-2)
- [x] **Fix Path Traversal**: Replace string-based checks in orket/tools.py with Path.is_relative_to().
- [x] **Async File Tools**: Implement orket/infrastructure/async_file_tools.py using aiofiles.
- [x] **Wire TurnExecutor**: Replace the old _traction_loop in orket/orket.py with the new async-native executor.
- [x] **Async Card Repository**: Switch all card operations to the new AsyncCardRepository (aiosqlite).

### 2. Critical Consolidation (Week 1)
- [x] **Fix RCE Vulnerability**: Separate agent-writable workspace directories from the read-only verification fixture paths. [DONE]
- [x] **Async Native Migration**: Replace all remaining requests calls with httpx and sqlite3 with aiosqlite. [DONE]
- [x] **Exception Cleanup**: Remove all bare except: clauses across the core package. [DONE]
- [x] **Datetime Update**: Global search/replace of datetime.utcnow() with datetime.now(UTC). [DONE]
- [x] **Coordination Hub**: Established Agents/ for sovereign communication protocols. [DONE]
- [x] **Documentation Honesty Pass**: Scrubbed marketing claims; focused on execution loop mechanics. [DONE]

### 3. Integration & Loop Recovery (Week 2)
- [x] **Sandbox Orchestrator**: Fully integrated sandbox creation and cleanup into the TurnExecutor flow. [DONE]
- [x] **Dependency Management**: Consolidated into pyproject.toml with strict version pins. [DONE]
- [x] **Gitea Webhook**: Launched webhook_server.py and connected it to Gitea for PR-driven automation. [DONE]

---

## Phase 3: Elegant Failure & Recovery (COMPLETE)
**Goal**: The autonomous loop runs with high-fidelity telemetry and recovery.

- [x] **Bug Fix Phase**: Integrated the BugFixPhaseManager to trigger automatically upon Rock completion. [DONE]
- [x] **Empirical Verification (FIT)**: Expanded the VerificationEngine to test running sandboxes via HTTP. [DONE]
- [x] **Memory Hygiene**: Implemented context clearing and session checkpointing to prevent LLM drift. [DONE]
- [x] **Policy Reports**: Generated PolicyViolationReport artifacts when the engine stops due to governance failures. [DONE]
- [x] **Boundary Verification**: Automated test suite for State Machine and Tool Gate enforcement. [DONE]

---

## Phase 4: UI Readiness (COMPLETE)
**Goal**: Backend stable and feature-rich for the next-generation UI.

- [x] **Unified API Layer**: Completed the FastAPI structure for monitoring, board management, and session transcripts. [DONE]
- [x] **WebSocket Streaming**: Live-stream execution telemetry and tool calls to the UI. [DONE]
- [x] **Observability**: Implemented structured JSON logging and metrics collection. [DONE]

---

## Phase 5: Production Readiness (COMPLETE)
**Goal**: Battle-tested, documented, and multi-user capable.

- [x] **Comprehensive Testing**: Reach 150+ tests with successful Golden Flow. [DONE]
- [x] **User Onboarding**: Implemented the orket init wizard in setup_wizard.py. [DONE]
- [x] **Multi-User/Auth**: Added JWT authentication and hashing in auth_service.py. [DONE]
- [x] **Deployment**: Sandbox Orchestrator now uses async-native Docker Compose. [DONE]

---

## v1.0 MILESTONE REACHED
**Status**: All roadmap items from the February 2026 reconstruction plan are COMPLETE.
**Date**: 2026-02-09

| Milestone | Target | Metric |
| :--- | :--- | :--- |
| **v0.4.0** | 2 Weeks | All async/security tests passing; PR-to-Sandbox loop active. |
| **v0.5.0** | 6 Weeks | 100+ tests; API stable for UI development. |
| **v1.0** | 10 Weeks | 150+ tests; Production-ready for multi-user teams. |

---

## Key References
- `Agents/Gemini/VISION.md` — Gemini's specific lens on implementation quality and reconstruction.
- `RECONSTRUCTION_STATUS.md` — Active session progress tracker (The Kanban).
- `docs/ARCHITECTURE.md` — iDesign and Volatility Decomposition principles.