# Idea Parking Lot (2026-03-06)

Last updated: 2026-03-06
Status: Future backlog (parked)
Owner: Orket Core

## Purpose

Capture non-active ideas from the recent Orket ideation thread so they are not lost while current focus items are implemented.

Current active focus stays with:
1. Core vs workloads boundary
2. Golden run harness
3. Prompt surface budgets
4. Tool reliability scoreboard
5. Run compression
6. Core tool baseline

Everything below is intentionally parked for later prioritization.

## Parked Runtime / Stability Ideas

1. Deterministic tool replay mode (`orket replay <run_id>`).
2. Tool sandboxing profiles (`safe`, `workspace`, `system`, `dangerous`).
3. Run graph visualization (task -> tool -> artifact flow).
4. Tool timeout governance per tool type.
5. Artifact schema registry for canonical artifact types.

## Parked Local-Model Reliability Ideas

6. Tool intent hints ahead of schema.
7. Tool call validator/normalizer repair layer.
8. Structured machine-readable error payloads.
9. Tool retry policies (deterministic-only auto-retry).
10. Partial-success result state handling.

## Parked Observability Ideas

11. Run telemetry dashboard (run rate, success, duration, token usage).
12. Prompt diff tooling for drift visibility.
13. Model performance profiles by workload/task class.
14. Tool heatmap for usage/failure concentration.

## Parked Experimentation Infrastructure Ideas

15. Experiment flags (`--exp ...`) for scoped behavior.
16. Workload templates/scaffolding command.
17. Model router layer (planning vs execution model split).
18. Workspace snapshot + rollback flow.
19. Run determinism tests (same run twice, compare artifacts).
20. Capability profiles per workload.

## Parked Additional Concept

1. Bonus emphasis from ideation: deterministic replay as the single highest leverage trust primitive.

