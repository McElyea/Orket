# Supervisor Runtime Foundations Implementation Plan
Last updated: 2026-03-31
Status: Active lane authority (requirements phase)
Owner: Orket Core
Lane type: Supervisor runtime foundations / requirements phase

## Authority posture

This file is the canonical active lane authority recorded in `docs/ROADMAP.md`.

This lane is requirements-first.
No executable implementation slice is accepted yet.
The paired requirements companion is `docs/projects/SupervisorRuntime/SUPERVISOR_RUNTIME_FOUNDATIONS_REQUIREMENTS.md`.

During this phase:
1. the roadmap continues to point here as the canonical active lane path
2. the requirements companion remains the scoped requirements authority
3. no runtime behavior is implied merely because it appears in brainstorming material
4. any durable contract accepted from this lane must move into `docs/specs/` before direct implementation begins

Planning input only:
1. `docs/projects/future/brainstorm/orket_brainstorm_runtime_os_extensions_2026-03-31_v5.md`
2. the archived Companion gap and planning packet under `docs/projects/archive/Companion/CP03092026-MVP-CLOSEOUT/`

## Purpose

Open the next bounded non-recurring lane around host-owned supervised runtime foundations.

This requirements phase is intentionally limited to four coupled contract areas:
1. approval-checkpoint runtime slice
2. sessions plus context-provider pipeline
3. operator control surface contract
4. host-owned extension contract and validation path

These four items fit together because they share one authority question:
how the host owns runtime truth while operators, sessions, and extensions interact under one policy and evidence model.

## Source authorities

This lane is bounded by:
1. `docs/ROADMAP.md`
2. `docs/ARCHITECTURE.md`
3. `CURRENT_AUTHORITY.md`
4. `README.md`
5. `pyproject.toml`
6. `docs/projects/SupervisorRuntime/SUPERVISOR_RUNTIME_FOUNDATIONS_REQUIREMENTS.md`

Planning inputs may inform scope selection, but they do not override these authority surfaces.

## Non-goals

This lane does not:
1. reopen Graphs work
2. treat frontend or client repos as authority centers
3. broaden into marketplace, cloud-hosting, or monetization scope
4. make refactor debt, repo identity drift, or large-module decomposition the primary deliverable
5. claim implementation truth for any runtime seam not explicitly proved and recorded later

## Decision locks

The following stay frozen during this requirements phase:
1. the host remains the sole runtime authority
2. checkpoint existence alone never authorizes resume
3. operator command, risk acceptance, and attestation remain distinct surfaces
4. extension installability must not create a second hidden runtime authority center
5. session identity must remain distinct from invocation identity
6. this lane must stay bounded enough that one direct implementation packet can begin without reopening basic scope questions

## Packet 1 cold-start lock

When this lane moves from requirements into direct implementation, Packet 1 must stay intentionally small.

Packet 1 may choose exactly:
1. one approval-required capability class
2. one interrupt / pending / approve-or-reject / resume lifecycle
3. one checkpoint-backed continuation rule
4. one canonical operator action path
5. one canonical operator inspection path
6. one canonical runtime projection source
7. one canonical session identity boundary
8. one canonical extension manifest shape
9. one canonical validation path
10. one operator-visible diagnostic path
11. one unsupported-host-version failure rule

Packet 1 must reuse the terminology lock from `docs/projects/SupervisorRuntime/SUPERVISOR_RUNTIME_FOUNDATIONS_REQUIREMENTS.md`.
It must not introduce competing meanings of `session`, `invocation`, `lineage`, `replay`, or `reconstruction boundary`.

## Packet 1 admitted behavior families

For Packet 1, the phrase `admitted behavior family` is intentionally narrow.
It means only:
1. the chosen approval-checkpoint behavior for the selected capability class
2. the chosen operator action and projection behavior attached to that same runtime slice
3. the chosen session identity boundary needed for that slice
4. the chosen extension manifest and validation behavior for one installable surface

Packet 1 must not silently expand `admitted behavior family` into a broad proof matrix over multiple capability classes, multiple operator surfaces, multiple session boundaries, or multiple extension surfaces.

## Packet 1 explicit non-goals

Packet 1 must not:
1. implement broad session cleanup policy, retention policy, or automated lifecycle retirement
2. implement general replay infrastructure beyond the chosen reconstruction boundary needed for the selected runtime slice
3. broaden from one operator action path into a general operator platform
4. broaden from one manifest and validation path into marketplace, package-backend plurality, or cloud distribution work
5. treat `install / validate / update` as permission to support multiple installable surface types in parallel

## Requirements-phase workstreams

### Workstream 1 - Approval-checkpoint runtime contract

Objective:
1. define one approval-required runtime slice that is explicit, interruptible, resumable, and fail-closed

Requirements authority:
1. Section A of `docs/projects/SupervisorRuntime/SUPERVISOR_RUNTIME_FOUNDATIONS_REQUIREMENTS.md`

Required outputs:
1. one canonical approval-required capability-class contract
2. one explicit interrupt / approve / reject / resume lifecycle
3. one checkpoint-backed continuation model with same-attempt vs new-attempt semantics
4. one evidence story that shows approval and resume lineage without inventing parallel truth

### Workstream 2 - Session and context-provider contract

Objective:
1. promote turn continuity from ad hoc glue into an explicit runtime primitive

Requirements authority:
1. Section B of `docs/projects/SupervisorRuntime/SUPERVISOR_RUNTIME_FOUNDATIONS_REQUIREMENTS.md`

Required outputs:
1. one canonical session model
2. explicit memory-scope boundaries
3. one context-provider injection model
4. minimum session lineage, inspection, summary, and cleanup boundary rules required for the selected slice

### Workstream 3 - Operator control surface contract

Objective:
1. define the smallest operator surface that can supervise approval, resume, and inspection without becoming a shadow authority

Requirements authority:
1. Section C of `docs/projects/SupervisorRuntime/SUPERVISOR_RUNTIME_FOUNDATIONS_REQUIREMENTS.md`

Required outputs:
1. one stable operator event and action surface for the lane
2. explicit hold / resume / approve / reject semantics
3. the inspection classes the lane requires, with Packet 1 selecting exactly one canonical operator inspection path for the chosen slice
4. explicit rules that operator surfaces project truth rather than author it

### Workstream 4 - Host-owned extension contract

Objective:
1. define extensions as governed installable surfaces without moving runtime authority out of the host

Requirements authority:
1. Section D of `docs/projects/SupervisorRuntime/SUPERVISOR_RUNTIME_FOUNDATIONS_REQUIREMENTS.md`

Required outputs:
1. one manifest and permission declaration shape
2. one canonical install / validate / update operator path
3. one host-owned execution and validation rule
4. explicit compatibility, failure, and audit expectations

## Recommended sequencing after requirements acceptance

If this lane advances beyond requirements:
1. open one cold Packet 1 using the exact Packet 1 lock above
2. implement the chosen approval-checkpoint runtime slice first
3. land the chosen operator control surface in that same packet
4. keep the session work in Packet 1 limited to one identity boundary, not broad cleanup or replay policy
5. keep the extension work in Packet 1 limited to one manifest and validation path, not broader install-surface expansion
6. move broader sessions plus context-provider work next only if Packet 1 closes without reopening scope
7. harden the host-owned extension contract after the runtime and operator seams are colder

Graphs remain out of scope unless explicitly reopened by a later roadmap decision.

## Packet 1 readiness gate

Direct Packet 1 planning is ready only when:
1. the selected capability class, lifecycle, checkpoint rule, operator paths, session boundary, and extension manifest path are named explicitly
2. the selected runtime projection source is named explicitly
3. source-of-truth update targets are named for the selected slice
4. proof paths are named only for the admitted behavior families above
5. Packet 1 does not rely on undefined session cleanup policy or undefined broad replay semantics
6. Packet 1 does not rely on multiple extension manifest shapes or multiple validation paths

## Requirements-phase completion gate

This phase is complete only when:
1. the four requirement families remain bounded and non-overlapping enough to hand off directly
2. one first executable packet can begin without reopening basic scope questions
3. proof expectations are explicit for each requirement family
4. required source-of-truth update targets are identified before execution begins
5. roadmap, project index, this plan, and the paired requirements companion tell one authority story

## Stop conditions

Stop and narrow scope if:
1. the lane starts turning into a generic runtime-OS wishlist
2. the extension work grows into marketplace or cloud-platform work
3. the session work grows into broad product UX planning
4. the operator surface starts claiming authority that belongs in runtime records
5. a proposed implementation packet cannot name one bounded approval path, one bounded session seam, or one bounded extension seam
