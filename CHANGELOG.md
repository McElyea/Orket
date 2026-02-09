# Changelog

All notable changes to Orket will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

- **v0.3.x**: Backend stabilization and improvements
- **v0.4.0**: Will mark transition to frontend focus (when backend is solid)
