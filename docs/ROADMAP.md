# Orket Roadmap

Last updated: 2026-03-05

## Priority Plan Pointer
1. techdebt hardening implementation plan: `docs/projects/techdebt/TD03052026-Plan.md`

## Canonical Rule
`docs/ROADMAP.md` is the only active roadmap source.

## Process Source
All process and workflow rules live in `docs/CONTRIBUTOR.md`.

## Invocation Rule
If the user requests "follow roadmap" without naming a project, execute the highest-priority active (non-paused) item in **Priority Now**.
Current default target: techdebt.

## Priority Now
1. techdebt -- TD03052026 boundary-hardening program (`docs/projects/techdebt/TD03052026-Plan.md`).
2. protocol-governed -- Runtime protocol determinism hardening (requirements v5.1 + implementation plan).
3. marshaller -- Marshaller v0 scaffolding lane aligned to protocol-governed runtime decisions.
4. NervousSystem -- v1 complete; hold for review and next-phase planning.

## Active Execution
1. techdebt -- Execute TD03052026 from `docs/projects/techdebt/TD03052026-Plan.md` (in progress: WS-4 through WS-7 boundary-seam hardening; landed: phase-0 baseline recorder automation at `scripts/techdebt/record_td03052026_phase0_baseline.py`, WS-1 install-surface convergence with CI drift gate at `scripts/governance/check_install_surface_convergence.py`, WS-2 launcher safety hardening via `orket/interfaces/server_launcher.py` and `tests/interfaces/test_server_launcher.py`, WS-3 lifecycle subscriber symmetry via `tests/interfaces/test_api_lifecycle_subscribers.py`, evidence sets under `benchmarks/results/techdebt/td03052026/phase0_baseline/`, `benchmarks/results/techdebt/td03052026/ws1_install_surface_convergence/`, `benchmarks/results/techdebt/td03052026/ws2_server_mode_hardening/`, and `benchmarks/results/techdebt/td03052026/ws3_lifecycle_subscriber_correctness/`, hardening dashboard at `benchmarks/results/techdebt/td03052026/hardening_dashboard.json`, and sustained `G1`-`G3` green state).
2. protocol-governed -- Keep enforce-phase staged/replayed pre-production validation windows fresh per release candidate and major runtime-policy change.
3. marshaller -- Treat current implementation as scaffolding and only adjust where protocol-governed contracts require alignment.

## Project Index
Every non-archive project under `docs/projects/` must appear here.

| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| NervousSystem | active | P2-review | `docs/projects/future/NervousSystem/` | Orket Core | Locked v1 action-path plan implemented with live evidence at `benchmarks/results/nervous_system_live_evidence.json` and verification notes in `docs/projects/future/NervousSystem/LIVE_VERIFICATION.md`. |
| marshaller | active | P2-scaffolding | `docs/projects/marshaller/` | Orket Core | Current Marshaller implementation is scaffolding and will be refit to finalized protocol-governed runtime decisions. |
| techdebt | active | P1-active | `docs/projects/techdebt/` | Orket Core | TD03052026 hardening program is active with promotion-blocking P0 seams and mandatory machine-readable evidence gates. |
| protocol-governed | active | P1-active | `docs/projects/protocol-governed/` | Orket Core | Primary overhaul lane; strict parser/preflight and hash/idempotency slices are landed, with append-only ledger, replay comparator, and ledger parity cutover scaffolding actively progressing against v5.1. |
| future | backlog-root | P3-backlog | `docs/projects/future/` | Orket Core | Incubation container for deferred project lanes (for example `UIForge`, `NervousSystem`). |
| LieDetector | completed-archive | complete | `docs/projects/archive/LieDetector/` | Orket Core | Archived project lane; v1 completed and moved to archive. |
| SDK-2026-03-01-Audio | completed-archive | complete | `docs/projects/archive/SDK-2026-03-01-Audio/` | Orket Core | SDK typed audio capabilities, Piper/audio backend wiring, bridge integration, and reforger voice-profile validation completed in-repo. |
| core-pillars | completed | P1-complete | `docs/projects/core-pillars/` | Orket Core | CP-1 through CP-4 complete; non-OS/non-ideas roadmap execution is closed out. |
| RuleSim-2026-03-01 | completed-archive | complete | `docs/projects/archive/RuleSim-2026-03-01/` | Orket Core | RuleSim v0 implemented; docs archived after completion. |
| archive | archive-root | n/a | `docs/projects/archive/` | Orket Core | Completed projects only. |
