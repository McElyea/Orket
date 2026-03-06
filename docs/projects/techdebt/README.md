# Tech Debt Folder Governance

Last updated: 2026-03-06  
Status: Active  
Owner: Orket Core

## Purpose

Define closure semantics for `docs/projects/techdebt/` so the folder can remain a permanent maintenance lane without making every document inside permanently active.

## Folder Semantics

1. `docs/projects/techdebt/` is a permanent project folder and is not expected to be archived as a whole.
2. Recurring maintenance remains active in this folder.
3. Most cycle-specific remediation documents are finite and should be archived after closeout.

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

## Closeout Process for a Cycle

1. Verify cycle gates and evidence are green.
2. Add explicit closeout status/date in the cycle plan.
3. Move superseded cycle docs to `docs/projects/archive/techdebt/<cycle_id>/`.
4. Keep only maintenance docs and currently active cycle references in `docs/projects/techdebt/`.
5. Update links in roadmap/checklist docs after any move.

## Anti-Bloat Rule

1. No cycle document should remain in active `techdebt` scope once superseded and archived.
2. New recurring items must be added to `Recurring-Maintenance-Checklist.md` only when they represent ongoing risk boundaries, not one-off incidents.
