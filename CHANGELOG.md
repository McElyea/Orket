# Changelog

All notable changes to Orket will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.8] - 2026-03-14 - "The Packet-1 Lane Cut"

### Added
- **Truthful Runtime Packet-1 Contract**: Added the durable packet-1 runtime truth contract in `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md` covering provenance, truth classification, silent fallback defects, and packet-1 conformance.
- **Truthful Runtime Project Lane**: Added the active truthful-runtime project lane under `docs/projects/truthful-runtime/` with the bounded Phase C packet-1 requirements and active implementation plan plus staged continuation plans for the remaining hardening backlog.

### Changed
- **Roadmap And Project Authority**: Updated the active roadmap and archived truthful-runtime closeout/staging references so the current packet-1 work now points at the new truthful-runtime project paths instead of the old future-lane locations.
- **Root UI Surface Cleanup**: Removed the leftover root `UI/` stub, stale contributor/vendor-tree references, and orphaned dashboard/UI env-template entries now that the UI will live in another codebase.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- None.

## [0.4.7] - 2026-03-14 - "The Claim E Closure Cut"

## [0.4.6] - 2026-03-14 - "The Causal Basis Cut"

### Added
- **Deterministic Drift Remediation Authority**: Added the active `DD03142026` deterministic-drift requirements and remediation plan so Claim E implementation can proceed from a single governed techdebt lane with anti-flake closure gates, explicit compare-surface rules, and a publishable resolution package contract.
- **Live Sandbox Maintenance Baseline Runner**: Added `scripts/techdebt/run_live_maintenance_baseline.py` plus contract coverage so maintenance work now has one canonical live sandbox baseline command with evidence payloads, diff-ledger output, and strict failure behavior.
- **Recurring Maintenance Cycle Report**: Added the `2026-03-14_cycle-a` recurring maintenance report artifact recording gate audit, docs hygiene, and canonical pytest freshness results.

### Changed
- **Roadmap And Staging Authority**: Activated `DD03142026` in `Priority Now`, superseded the older staged Claim E future plan as a staging ancestor, and kept the future lane scoped to the remaining staged truthful-runtime work only.
- **Maintenance Workflow Guidance**: Updated contributor and recurring-maintenance authority so live sandbox baseline proof now has a canonical command and checklist section instead of ad hoc maintenance handling.
- **Deterministic Test Fixtures**: Updated prompt-compiler monkeypatches to accept keyword arguments across orchestrator tests and fixed sandbox recovery tests to pin lifecycle timestamps deterministically.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use `python scripts/techdebt/run_live_maintenance_baseline.py --baseline-id <baseline_id> --strict` when maintenance work needs canonical live sandbox baseline proof.

## [0.4.5] - 2026-03-13 - "The Archived Recovery Cut"

### Added
- **Claim E Drift Diff Summary**: Added a published operator-surface diff summary for the fresh append-only live Claim E rerun so the remaining nondeterminism is shareable without referring back to hidden proof roots.
- **Staged Claim E Hardening Lane**: Added a dedicated staged follow-on plan for runtime-stability live deterministic-compare hardening after the recovery lane was truthfully closed.

### Changed
- **Governed Prompt Contract**: Updated governed prompt compilation, message building, corrective prompts, and strict response parsing so protocol-governed turns require a single JSON envelope without false `E_MARKDOWN_FENCE` hits from fenced content inside JSON strings.
- **Governed Read Cardinality**: Relaxed governed `read_file` cardinality to required-path coverage while keeping single-shot required tools fail-closed, and aligned the corresponding runtime contract/error-code authority.
- **Runtime Retry and Policy Enforcement**: Allowed system retry requeues from `in_progress` back to `ready`, tightened governance handling after corrective reprompts, and removed the stale `reforger_inspect` requirement from the requirements-analyst governed seat.
- **Live Proof Closeout Truthfulness**: Archived the runtime-stability live recovery lane, refreshed the accepted published proof with fresh append-only Claim E drift evidence plus Claim G success evidence, and moved the remaining Claim E work into a staged hardening lane instead of leaving it as fake active closeout work.
- **Release Tag Range Enforcement**: Tightened the core release guard and workflow so pushed `main` ranges require matching annotated release tags on each governed post-`0.4.0` commit, not just the branch head.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Continue pushing each `main` release commit with its matching annotated `v<version>` tag.

## [0.4.4] - 2026-03-13 - "The Tag Truth Cut"

### Added
- **Head Tag Enforcement**: Added release-policy enforcement for matching annotated `v<version>` tags on pushed `main` `HEAD` commits, with targeted guard coverage for the required head-tag path.

### Changed
- **Release Workflow Truthfulness**: Clarified contributor and release-policy authority so a core version bump is not complete until the matching annotated tag is created and pushed.
- **Commit Discipline Enforcement**: Removed the stale docs-only exemption from the core release policy guard so docs-only `main` commits must advance version and tag just like any other release step.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Ensure each `main` commit is pushed with its matching annotated `v<version>` tag.

## [0.4.3] - 2026-03-13 - "The Published Proof Bundle"

### Added
- **Published Live Proof Support Bundle**: Added the published support folder for the `2026-03-13` live runtime-stability proof so the curated artifact now ships with its referenced evidence files.

### Changed
- **Published Artifact Self-Containment**: Repointed the published live runtime-stability proof JSON away from `benchmarks/results/...` and into `benchmarks/published/General/...` so the published lane no longer depends on non-exposed result paths.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- None.

## [0.4.2] - 2026-03-13 - "The Live Proof Cut"

### Added
- **Live Runtime Proof Coverage**: Added provider-backed live runtime-stability proof nodes for illegal state transitions, path traversal, and strict replay compatibility on missing workspace snapshots.
- **Published Live Runtime Proof Artifact**: Added a curated published artifact for the 2026-03-13 Ollama `qwen2.5-coder:7b` runtime-stability proof package.

### Changed
- **Live Acceptance Truthfulness**: Tightened the live acceptance fixture and assertions so provider-backed runs must emit fresh run roots, protocol-capable artifacts, and runtime verification payloads before claiming success.
- **Testing Authority**: Updated the testing policy so live provider-backed proof is the highest-authority evidence, unit tests are minimal support proof, and non-live lanes cannot be presented as live proof.
- **Live Proof Recovery Tracking**: Reduced the active runtime-stability recovery plan to the actual remaining work only, with closed claims moved to canonical evidence references and open claims limited to B, E, and G.
- **Release Discipline**: Removed the docs-only version-bump exemption from contributor and release-versioning policy so every commit on `main` must advance the core version and changelog.
- **Repository Hygiene**: Collapsed pytest temp ignore rules to `.pytest_*` to reduce git noise from live proof runs.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- None.

## [0.4.1] - 2026-03-13 - "The Structural Closeout"

### Added
- **Canonical Run Summary Contract**: Added the runtime `run_summary.json` implementation, schema, deterministic reconstruction proof, and replay-parity coverage for finalized runs.
- **Runtime-Stability Archive Summary**: Added the archived closeout summary for the completed runtime-stability structural lane and archived its supporting requirements packets.
- **Recurring Maintenance Evidence**: Recorded the `2026-03-13_cycle-a` techdebt maintenance cycle evidence with gate audit, docs hygiene, and full-suite pytest results.

### Changed
- **Boundary and Replay Truth**: Narrowed the active runtime-stability requirements to the shipped v0 boundary and protocol-replay operator surfaces, and fixed replay compatibility handling so missing workspace snapshots fail closed instead of scanning the current repo.
- **Minimal Tool Baseline Authority**: Narrowed the active core-tool baseline contract to the shipped minimal registry and invocation-manifest surfaces, added the matching contract delta, and aligned proof accordingly.
- **Roadmap State**: Archived the completed runtime-stability closeout and green-requirements projects, removed the lane from `Priority Now`, and left only active maintenance plus staged/future items in the roadmap.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- None.

## [0.4.0] - 2026-03-13 - "The Semantic Gate"

### Added
- **Core Release Governance**: Added canonical core release/versioning policy, release gate checklist, proof report template, release policy CI workflow, and release preparation tooling for governed core releases.
- **Release Authority Indexing**: Added explicit release authority references in current workflow and authority docs so release prep, proof storage, and tag discipline now have canonical paths.
- **Runtime Stability Closeout Plans**: Added direct closeout implementation plans for the currently active runtime-stability slices, including decision locks for SPC-01, SPC-02, SPC-05, and SPC-06.

### Changed
- **Core Version Baseline**: Promoted the core engine to `0.4.0` as the first process-backed semantic release milestone.
- **Semantic Versioning Start**: Core release discipline now starts at `0.4.0`; subsequent non-exempt commits on `main` are governed by the release/versioning policy rather than the previous ad hoc cut pattern.
- **Roadmap and Requirements Authority**: Kept runtime-stability closeout and supporting requirements lanes active under `docs/projects/` while direct closeout plans iterate, instead of treating decision packets as automatically archive-ready.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- None.

## [0.3.18] - 2026-03-12 - "The License Cut"

### Added
- **Source-Available Licensing**: Added the Orket Business Source License 1.1 bundle, including the root license text and companion commercial licensing guidance.

### Changed
- **Package Metadata**: Updated package metadata and repository docs to point to the canonical license files.

## [0.3.17] - 2026-03-12 - "Runner Lifecycle Truth"

### Added
- **Local Runner Lifecycle Proof**: Added local Gitea runner lifecycle inspection and proof scripts plus contract tests for cleanup classification and proof output.

### Changed
- **Governance Guidance**: Tightened CI/process guidance around self-hosted runner lifecycle boundaries and corrected Docker closeout scope so sandbox cleanup is not overclaimed.
- **Archive Evidence**: Archived the local Gitea runner lifecycle implementation and closeout documents with live-proof references.

## [0.3.16] - 2026-02-11 - "The Dogfood Cut"

### Added
- **Decision Node Architecture**: Introduced planner, router, prompt-strategy, and evaluator decision-node contracts with plugin registry and default built-ins.
- **Contract Tests**: Added decision-node contract/registry tests and expanded policy + webhook DB test coverage.
- **Load Evidence Artifacts**: Archived benchmark evidence under `benchmarks/results/`.

### Changed
- **Orchestrator Decomposition**: Candidate planning, seat routing, model/dialect strategy, and success/failure evaluation now route through decision-node boundaries.
- **Governance Hardening**: Replaced broad exception handling across the main `orket/` runtime paths with typed handling where practical; true CLI/API entry boundaries still retain top-level crash logging handlers by policy.
- **Release Pipeline**: Added CI Docker smoke and migration smoke jobs, plus runbook release checklist alignment.

### Removed
- **Legacy Review Doc**: Deleted `CODE_REVIEW.md` from tracked repository during cleanup.

## [0.3.11] - 2026-02-10 - "The Clean Sweep"

### Changed
- **Repository Cleanup**: Removed obsolete roadmaps and internal agent logs from the tracked repository.
- **Documentation**: Established `docs/ROADMAP.md` as the single source of truth.
- **Security**: Hardened webhook secret handling (fails fast if secret is missing).
- **API**: Added Pydantic models for better request validation.

## [0.3.9] - 2026-02-09 - "The Async Sovereignty"

### Added
- **Async Native Core**: Migrated all I/O to `aiofiles`, `aiosqlite`, and `httpx`.
- **Security Sovereignty**: Implemented strict `Path.is_relative_to()` checks and directory isolation (`agent_output/` vs `verification/`).
- **TurnExecutor**: Decomposed the monolithic loop into a specialized async executor.
- **PolicyViolationReport**: Mechanical reporting for governance failures.
- **Gitea Webhook**: Fully functional webhook server for PR automation.

### Changed
- **Dependency Management**: Consolidated all versions into `pyproject.toml`.
- **Datetime**: Replaced `datetime.utcnow()` with `datetime.now(UTC)` globally.
- **Exception Handling**: Removed all bare `except:` clauses.

## [0.3.8] - 2025-02-09 - "The Diagnostic Intelligence"

### Added
- **WaitReason Enum**: Explicit diagnostic tracking for blocked/waiting cards (RESOURCE, DEPENDENCY, REVIEW, INPUT)
- **BottleneckThresholds Configuration**: Configurable thresholds for bottleneck detection to prevent alert fatigue
- **Priority Migration**: Automatic conversion from legacy string priorities ("High"/"Medium"/"Low") to numeric values (3.0/2.0/1.0)
- **Multi-Role State Validation**: State machine now supports validating transitions against multiple roles
- **Golden Flow Test**: Comprehensive end-to-end sanity test for orchestration engine (`tests/test_golden_flow.py`)
- **Wait Reason Enforcement**: State machine now requires explicit wait_reason when transitioning to BLOCKED or WAITING_FOR_DEVELOPER states
- **iDesign Validator Service**: New service for enforcing architectural boundaries (`orket/services/idesign_validator.py`)

### Changed
- **Priority System**: Migrated from string-based ("High"/"Medium"/"Low") to float-based (3.0/2.0/1.0) for precise sorting
- **Schema Field Validation**: Improved alias handling in verification fields using AliasChoices
- **State Machine Governance**: Enhanced role-based enforcement with multi-role support (allows agents with multiple roles)
- **Verification System**: Refactored verification logic for better diagnostics and error handling
- **Agent Factory**: Improved agent creation with better role resolution
- **Tool Parser**: Enhanced tool extraction and validation logic
- **Critical Path**: Improved priority-based sorting and dependency resolution
- **Test Suite**: Cleaned up test files, removed obsolete examples

### Fixed
- **Schema Migration**: Fixed backward compatibility issues with legacy priority strings
- **Verification Aliases**: Corrected field alias mappings for verification fixtures
- **Line Ending Warnings**: Normalized line endings across core modules (LF → CRLF on Windows)

### Removed
- **Obsolete Tests**: Removed deprecated test files (`test_examples_tictactoe.py`, `test_flow_loads.py`)

## [0.3.7] - 2025-02-08 - "The Stabilization Recovery"

### Added
- Critical Path sorting implementation
- Audit Ledger (Transactions) tracking
- Mechanical Failure Reporting

### Changed
- Hardened React UI against runtime crashes
- Fixed backend schema mismatches
- Optimized Epic mapping with AliasChoices for robust data hydration

### Fixed
- WorkStation stability issues

## [0.3.6] - 2025-02-08 - "The Enforcement Pivot" / "The Integrity Release"

### Added
- Core StateMachine for mechanical governance
- Atomic Roles implementation
- Exponential backoff retry logic for LLM calls
- Hardware-aware multi-modal support (CUDA/CPU auto-detection)

### Changed
- Merged Skills into atomic Roles
- Simplified project structure
- Ignored local dev scripts
- **Tool Decomposition:** Refactored monolithic ToolBox into specialized toolsets (FileSystem, Vision, Cards)
- **SRP-Based Schema:** Decoupled metrics from verification logic in IssueConfig
- Pivoted from descriptive orchestration to mechanical enforcement model

### Security
- Environment-based credential management with `.env` files
- `.gitignore` guards for sensitive files

### Removed
- Legacy Skills system (consolidated into Roles)

## [0.3.5] - 2025-02-08 - "The McElyea Reforge"

### Added
- Centralized orchestration engine
- Atomic Roles system
- NoteStore for session state
- Structural Reconciler for data consistency
- Collapsible tree view in WorkStation
- Binocular Preview feature

### Changed
- Strategic refactor into decoupled, data-driven architecture
- Restored WorkStation with improved UI

## [0.3.1] - 2025-02-07

### Changed
- Polymorphic refactor for Orket EOS
- Market Edge Suite integration

## [0.3.0] - 2025-02-07 - "iDesign Victory"

### Added
- iDesign enforcement framework
- Prompt Engine updates
- Book → Card terminology migration

### Changed
- Major architectural alignment with iDesign principles
- Venue interface for Traction integration

---

## Version Strategy

- **v0.3.x**: Internal runtime, governance, and release-process hardening.
- **v0.4.x**: Governed semantic-release era beginning with the first process-backed core release milestone. Runtime closeout lanes continue under normal roadmap control instead of blocking semantic versioning from starting.
