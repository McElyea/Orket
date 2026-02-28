# RefactorCardEngine Requirements

Last updated: 2026-02-27

## Goal
Make `Cards + engine` the canonical framework and treat `ODR` as a workload mode/executor, while removing the hard `Rock/Epic/Issue` structural constraint.

## Non-Goals
1. No rewrite of ODR semantics.
2. No broad runtime architecture rewrite.
3. No migration that breaks existing published ODR artifacts.

## Problem Statement
1. Cards currently encode a fixed three-level hierarchy that is easy to explain but structurally limiting.
2. ODR currently behaves like a parallel system instead of a mode within one shared engine.
3. Governance/provenance/indexing improvements risk duplication if workloads are not unified behind one contract.

## Decisions (Locked)
1. Framework canonical owner: `Cards + engine`.
2. ODR position: executor/mode under shared workload contract.
3. Card structure direction: parent-tree (`parent_id`) with profile/view conventions for Rock/Epic/Issue.
4. Delivery order: unification seam first, hierarchy migration second.

## Functional Requirements
1. Define one shared `WorkloadContract` shape used by both card workloads and ODR workloads.
2. Ensure both workloads can compile to a deterministic run plan consumed by shared arbiter path.
3. Preserve current ODR stop semantics and trace semantics.
4. Add explicit mode selection so ODR can be enabled/disabled per run without branching framework identity.
5. Support card records with `parent_id` and `kind` without requiring fixed depth.
6. Keep legacy Rock/Epic/Issue views available as profile mappings during migration.

## Contract Requirements
Minimum shared contract fields:
1. `workload_type`
2. `units` (run pairs/work items)
3. `required_materials`
4. `expected_artifacts`
5. `validators`
6. `summary_targets`
7. `provenance_targets`

## Data Model Requirements
Core card/work item fields:
1. `id`
2. `kind`
3. `parent_id` (nullable)
4. `status`
5. `dependencies` (optional DAG edges)
6. `assignee` (optional)
7. `requirements_ref` / `verification_ref` (optional)
8. `metadata`

## Compatibility Requirements
1. Existing CLI/API behavior should remain available until explicit migration cutover.
2. Existing ODR published artifacts remain readable by current index/provenance tooling.
3. Existing card operations continue to function under legacy profile while new profile is introduced.

## Determinism and Safety Requirements
1. Deterministic artifacts remain mandatory for both workloads.
2. Shared arbiter, index, and provenance paths must remain mechanical and non-ambiguous.
3. No silent fallback between contract versions.

## Acceptance Criteria
1. Both ODR and Cards can produce a valid shared workload plan artifact.
2. Engine executes both through a single arbiter/validation shell.
3. Parent-tree card profile can represent 2-level and 3-level views without hard depth constraints.
4. Legacy card profile remains functional during migration period.
5. Regression tests pass for ODR core, ODR indexing/provenance tooling, and core card execution paths.
