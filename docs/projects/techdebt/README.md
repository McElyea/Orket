# Tech Debt Folder Governance

Last updated: 2026-03-08
Status: Active  
Owner: Orket Core

## Purpose

Define closure semantics for `docs/projects/techdebt/` so the folder can remain a permanent maintenance lane without making every document inside permanently active.

## Folder Semantics

1. `docs/projects/techdebt/` is a permanent project folder and is not expected to be archived as a whole.
2. Recurring maintenance remains active in this folder.
3. Most cycle-specific remediation documents are finite and should be archived after closeout.
4. Active-folder rule:
   1. only standing maintenance docs and docs for cycle ids still listed as active in `docs/ROADMAP.md` may remain here
   2. no `Status: Completed` or `Status: Archived` cycle doc may remain here after closeout
   3. preserve discoverability with archive links and closeout references, not by keeping completed docs in the active folder
5. Closure rule (if-statement form):
   1. if implementation requirements for a techdebt cycle are complete and verified, archive the cycle docs
   2. else keep only currently active cycle docs in this folder

## Non-Archivable Maintenance Items

These stay in `docs/projects/techdebt/`:

1. `README.md` (this governance contract)
2. `Recurring-Maintenance-Checklist.md` (standing maintenance runbook)

## Archivable Cycle Items

These are closeable and should move to archive when superseded:

1. cycle-specific implementation plans
2. cycle-specific review reports and source-review notes
3. cycle-specific baseline or phase snapshots
4. cycle-specific temporary planning docs no longer used by the active checklist

Archive destination:
1. `docs/projects/archive/techdebt/<cycle_id>/`

Current archived cycle examples:
1. `docs/projects/archive/techdebt/TD03052026/`
2. `docs/projects/archive/techdebt/OBT03062026/`
3. `docs/projects/archive/techdebt/OBT03072026/`
4. `docs/projects/archive/techdebt/CB03072026/`
5. `docs/projects/archive/techdebt/OBT03082026/`

## Closeout Process for a Cycle

1. Verify cycle gates and evidence are green.
2. Add explicit closeout status/date in the cycle plan.
3. Move superseded cycle docs to `docs/projects/archive/techdebt/<cycle_id>/`.
4. Keep only maintenance docs and currently active cycle references in `docs/projects/techdebt/`.
5. Update links in roadmap/checklist docs after any move.
6. If a completed cycle must stay easy to find, link the archive location from roadmap or closeout docs instead of leaving the cycle doc here.

## Anti-Bloat Rule

1. No cycle document should remain in active `techdebt` scope once superseded and archived.
2. New recurring items must be added to `Recurring-Maintenance-Checklist.md` only when they represent ongoing risk boundaries, not one-off incidents.
3. `python scripts/governance/check_docs_project_hygiene.py` is expected to enforce the active-folder rule mechanically.

## Roadmap Hygiene for Recurring Entry

1. Keep the `techdebt` recurring entry in `docs/ROADMAP.md` static:
   1. checklist source pointer
   2. folder governance pointer
2. Do not add volatile pointers (for example "latest evidence" or "latest completed archive") to the roadmap recurring entry.
3. Put cycle-specific evidence and closeout links in cycle artifacts/closeout docs under `docs/projects/archive/techdebt/<cycle_id>/`, not in the active roadmap line.
