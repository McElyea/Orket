# ODR Project

Date: 2026-02-26
Status: active

## Purpose
Define and implement ODR v1 (Orket Distillation Reactor) as a deterministic steel-thread state machine.

## Canonical Docs
1. `docs/projects/odr/01-REQUIREMENTS.md`
2. `docs/projects/odr/02-IMPLEMENTATION-PLAN.md`
3. `docs/projects/odr/03-MILESTONES.md`

## Scope (v1)
1. Deterministic round runner with strict parsing, stop logic, and in-memory trace.
2. Locked parser/metric/trace contracts and acceptance suite.
3. No model invocation, no retry orchestration, no filesystem writes.
