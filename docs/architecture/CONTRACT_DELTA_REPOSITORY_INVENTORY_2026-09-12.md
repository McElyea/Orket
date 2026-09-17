# Repository Inventory Authority Delta

## Summary

- Owner: Orket Core. Date: 2026-09-12.
- Affected authority: `docs/CONTRIBUTOR.md`, `CURRENT_AUTHORITY.md` and the platform namespace/review-copy tests.

## Delta

Tracked platform tests imported or dynamically loaded an ignored local
`project_dump.py`, so canonical pytest collection failed in an independent
worktree. Git-visible inventory now belongs to
`scripts/common/git_inventory.py`; tests and the repository-owned review-copy
command import that definition. Discovery uses tracked and nonignored untracked
files, preserves path names and refuses external resolved paths. Git errors
remain errors; there is no filesystem-walk fallback or empty success substitute.

`python -m scripts.governance.export_review_packet` writes a filtered source/config
copy to `Agents/review/project_review_packet.txt` by default. `--output` overrides
that path. The output is review material, not retained execution evidence or a
complete repository export. File/total bounds are disclosed with exit 2; failed
discovery/reading/writing returns exit 1. This text-only command does not create
rerunnable JSON results or modify runtime/provider admission.

## Migration and validation

Replace both test imports with repository-owned modules and rename the review-copy
test to `test_review_packet.py`; classify its real Git/filesystem/CLI checks as
integration. Do not copy the ignored root utility, add a compatibility shim,
inject an import path, skip the tests or weaken collection. Preserve existing
ignore-rule coverage and prove worktree discovery, Git failure, partial output
and old-output preservation on read/discovery failure. Run canonical pytest.

## Additional ignored configuration dependencies

The executable full suite also exposed ignored prompt thresholds and an archived
ODR comparison artifact as test prerequisites. Prompt comparison configuration
now lives beside `scripts/prompt_lab/compare_candidates.py` in the tracked
`prompt_promotion_thresholds.json`; values retain the original local configuration.
The CLI resolves this default independently of its working directory and refuses
an unreadable or non-object override with exit 2 before emitting a report. It
previously omitted four absolute guard criteria when the threshold file was
missing. No thresholds are relaxed, and explicit object overrides keep their
existing semantics.

The archived ODR registry contract test checks the tracked frozen selection.
Separate real-file fixture tests exercise loader resolution and missing source
config/comparison refusal. They do not establish the existence or validity of
historical benchmark outputs. The archived lane is not reopened and the production
loader still refuses missing evidence. No ignored benchmark result is copied or
published to make tests pass.

## Rollback and versioning

Disable the optional review-copy command if its checks fail, while retaining a
tracked shared inventory for namespace enforcement. Never restore an ignored-file
test prerequisite. No persisted runtime state is migrated. This is an unreleased
candidate on the 0.6.2 base; normal contributor release/version policy applies
when a release commit is requested.
