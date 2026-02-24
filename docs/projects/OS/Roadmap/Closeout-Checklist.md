# OS Closeout Checklist

Last updated: 2026-02-24
Status: Closeout-ready

## Objective
Move OS from `closeout-ready` to owner-approved closeout/archive state.

## Preconditions (Complete)
1. Card closure evidence exists:
- `Roadmap/Card-Closure-Checklist.md`
- `Roadmap/ClosurePass-2026-02-24.md`
2. Deterministic gates are green:
- `python scripts/audit_registry.py`
- `python -m pytest -q tests/kernel/v1`
- `python -m pytest -q tests/interfaces/test_api_kernel_lifecycle.py`
- `python scripts/run_kernel_fire_drill.py`
3. CI architecture gate enforces kernel sovereign + interface + fire-drill checks.

## Owner Sign-Off Items
1. Confirm OS v1 card acceptance (Cards 001-008) is sufficient for closure.
2. Confirm no additional normative requirements are pending outside `contract-index.md`.
3. Confirm closeout timing (immediate closeout vs hold in closeout-ready state).

## Closeout Actions (After Sign-Off)
1. Update `docs/ROADMAP.md`:
- set OS status from `closeout-ready` to `completed`
- update notes to archived path
2. Move active OS planning docs to archive as needed:
- follow `docs/CONTRIBUTOR.md` archive rule
3. Keep normative OS contracts and operational docs in place if still canonical.
4. Run anti-orphan checks:
- every non-archive `docs/projects/` entry appears in roadmap index
- every active/queued roadmap path exists

## Completion Signal
1. `docs/ROADMAP.md` reflects OS as completed or explicitly held.
2. Archive move (if performed) is committed.
3. Closeout commit references this checklist.
