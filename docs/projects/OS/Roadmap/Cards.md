# OS v1 Cards (Normative Execution Plan)

This is the authoritative card list and dependency order for OS v1.

## Dependency order (hard)
001 -> 002 -> 003 -> 004 -> 005 -> 006 -> 007 -> 008

## Cards

### 001 - Kernel Boundary
Deliverables:
- `orket/kernel/v1/` package created
- sentinel becomes adapter or remains separate CI-only tool
Acceptance:
- No executable code under docs/
- imports resolve

### 002 - Canonicalization
Deliverables:
- canonical JSON + structural digest utilities
Acceptance:
- canonical bytes match schema examples
- deterministic digest stable

### 003 - LSI Core
Deliverables:
- `state/lsi.py` staging/committed layout
- visibility shadowing implemented
Acceptance:
- Self > Staging > Committed tests pass
- orphan failure pointer-rooted

### 004 - Promotion Atomicity
Deliverables:
- `state/promotion.py` atomic swap and stem-scoped pruning
Acceptance:
- crash simulation results in old-or-new, never partial
- pruning removes prior stem sources only

### 005 - Run Lifecycle
Deliverables:
- run + turn sequencing enforcement
Acceptance:
- reject skipped turn promotion
- fortress invariant enforced

### 006 - Replay Engine
Deliverables:
- replay contract implemented
Acceptance:
- 100/100 replay stability

### 007 - Capability Jail
Deliverables:
- deny-by-default capability enforcement + audit
Acceptance:
- undeclared tool call fails deterministically
- module-off emits I_CAPABILITY_SKIPPED

### 008 - Contract Tests
Deliverables:
- schema validation tests
- scenario constitution tests
Acceptance:
- PR gates enforce test-policy.md
