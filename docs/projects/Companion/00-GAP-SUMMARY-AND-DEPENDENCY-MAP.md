# Companion Initiative: Gap Summary and Dependency Map

**Date**: 2026-03-08
**Auditor**: Claude Opus 4.6
**Source**: 01-COMPANION-EXTERNAL-EXTENSION-PLAN.md vs current codebase state

## Foundational Decision: Backend Authority Model

**Before coding, resolve this once**: Companion's backend logic (prompt assembly, memory retrieval, generation orchestration, session state) lives in the **host**, behind the host API seam. The Companion external repo is a **thin client** that consumes public host API endpoints. Extension workload entrypoints exist for installability and manifest compatibility, not as a second hidden product authority.

This decision flows through every plan. No product-significant runtime authority may live in frontend code. No Companion-repo module may duplicate host-owned orchestration.

## Executive Summary

The Companion plan defines a 4-phase initiative with ~35 discrete requirements across SDK packaging, capabilities, memory, voice, config, API, repo structure, product UI, and isolation. Against the current codebase:

- **Fully built**: 6 requirements (import static scan, TTS protocol, manifest parsing, workload execution, artifact validation, test utilities)
- **Partially built**: 5 requirements (capability registry, memory store, config loading, extension template, provider dispatch)
- **Not built**: 24 requirements (everything Companion-specific)

## Dependency Graph

```
Phase 0 (parallel):
  [02] SDK Package Hardening ─────────────────────────┐
  [08] External Repo Bootstrap ───────────────────────┤
                                                      │
Phase 1 (sequential after Phase 0):                   │
  [03] Capability Wiring ←────────────────────────────┘
  [06] Config & Mode Schema ←─────────────────────────┘
  [10] Import Isolation Hardening ←───────────────────┘
  [04] Memory Subsystem Split ←── [03]
  [05] Voice/STT Turn Control ←── [03]
  [07] Host API Seam ←── [03] [04] [05] [06]
                                                      │
Phase 2 (after Phase 1):                              │
  [09] Companion MVP Product ←── [07] [08]
```

## Gap Inventory by Severity

### BLOCKING (must fix before MVP)

| # | Gap | Plan | Current State |
|---|-----|------|---------------|
| 1 | SDK not independently installable | 02 | Bundled in monorepo, no pyproject.toml |
| 2 | `model.generate` not wired | 03 | LLMProvider protocol exists, no capability registration |
| 3 | `memory.write` / `memory.query` missing | 03, 04 | No capability, no protocol, no models |
| 4 | `speech.transcribe` missing | 03, 05 | Nothing exists |
| 5 | No session_memory / profile_memory split | 04 | Single `project_memory` table |
| 6 | No voice turn lifecycle FSM | 05 | Nothing exists |
| 7 | No silence-delay parameter | 05 | Nothing exists |
| 8 | No role/style mode schema | 06 | Nothing exists |
| 9 | No config precedence chain | 06 | File-based only, no session/turn override |
| 10 | No chat/generation API endpoint | 07 | API serves internal orchestration only |
| 11 | No CORS for local web app | 07 | Not configured |
| 12 | No Companion repo | 08 | Nothing exists |
| 13 | No Companion web UI | 09 | Nothing exists |

### HIGH (should fix before MVP)

| # | Gap | Plan |
|---|-----|------|
| 14 | No runtime import guard | 10 |
| 15 | No voice.turn_control capability | 03, 05 |
| 16 | No write policy for profile memory | 04 |
| 17 | No memory toggle controls | 04 |
| 18 | No validation CLI command (`orket ext validate`) | 08 |
| 19 | No API client package for Companion | 07 |
| 20 | No structured error codes for API | 07 |
| 21 | No STT provider implementation | 05 |
| 22 | SDK version/SemVer contract | 02 |
| 23 | No publish/release workflow for SDK | 02 |

### MEDIUM

| # | Gap | Plan |
|---|-----|------|
| 24 | No declared dependency allowlist in manifest | 10 |
| 25 | No CI template for external repos | 08 |
| 26 | No runbook for extension authoring | 08 |
| 27 | Silence-delay bounds not in config | 06 |
| 28 | No invalid combination blocking matrix | 06 |
| 29 | PiperTTS pulls heavy ONNX dep unconditionally | 02 |
| 30 | No mode change timing enforcement | 06 |

### LOW

| # | Gap | Plan |
|---|-----|------|
| 31 | No partial transcript support | 05 |
| 32 | Commit buffer not scope-aware | 04 |
| 33 | No declared_imports manifest field | 10 |

## Estimated Work by Phase

| Phase | Plans | Est. Lines | Key Deliverable |
|-------|-------|------------|-----------------|
| 0 | 02, 08 | ~1000 | SDK pip-installable, Companion repo exists |
| 1 | 03, 04, 05, 06, 07, 10 | ~3250 | Host API seam complete with all capabilities |
| 2 | 09 | ~2000 | Companion MVP ships (web UI + chat + voice + memory) |

**Total estimated new code**: ~6250 lines across both repos.

## Critical Path

The longest sequential dependency chain is:

**02 (SDK) -> 03 (Capabilities) -> 04 (Memory) -> 07 (Host API) -> 09 (MVP Product)**

Plans 05 (Voice), 06 (Config), and 10 (Isolation) can run in parallel with 04 once 03 is complete. Plan 08 (Repo Bootstrap) is parallel with everything in Phase 0-1.

## Composition Classification (per plan requirement)

| Subsystem | Classification | Rationale |
|-----------|---------------|-----------|
| STT engine | **wrap** | Use faster-whisper behind SDK STTProvider adapter |
| Future TTS engine | **reuse** | PiperTTSProvider already exists in SDK |
| Semantic retrieval | **build** | ScopedMemoryStore is Companion-specific |
| Chat UI primitives | **reuse** | Vanilla JS/lightweight framework, direct frontend dep |
| Avatar/expression | **defer** | Excluded from MVP |
| Lip-sync | **defer** | Excluded from MVP |
| Config validation | **build** | Pydantic models, ownership TBD (SDK vs Companion repo) |
| Provider dispatch | **reuse** | Existing LocalModelProvider behind model.generate |

## Plans Index

| # | Plan | Phase | File |
|---|------|-------|------|
| 00 | Gap Summary (this file) | -- | `00-GAP-SUMMARY-AND-DEPENDENCY-MAP.md` |
| 01 | Parent Plan | -- | `01-COMPANION-EXTERNAL-EXTENSION-PLAN.md` |
| 02 | SDK Package Hardening | 0 | `02-SDK-PACKAGE-HARDENING.md` |
| 03 | Capability Wiring | 1 | `03-CAPABILITY-WIRING.md` |
| 04 | Memory Subsystem Split | 1 | `04-MEMORY-SUBSYSTEM-SPLIT.md` |
| 05 | Voice/STT Turn Control | 1 | `05-VOICE-STT-TURN-CONTROL.md` |
| 06 | Config & Mode Schema | 1 | `06-CONFIG-AND-MODE-SCHEMA.md` |
| 07 | Host API Seam | 1-2 | `07-HOST-API-SEAM.md` |
| 08 | External Repo Bootstrap | 0 | `08-EXTERNAL-REPO-BOOTSTRAP.md` |
| 09 | Companion MVP Product | 2 | `09-COMPANION-MVP-PRODUCT.md` |
| 10 | Import Isolation Hardening | 1 | `10-IMPORT-ISOLATION-HARDENING.md` |
