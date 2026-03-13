# Contributor Guide

## Startup

1. Before substantive work, read in order:
   - `docs/CONTRIBUTOR.md`
   - `docs/ROADMAP.md`
   - `docs/ARCHITECTURE.md`
2. Read `docs/architecture/ARCHITECTURE_COMPLIANCE_CHECKLIST.md` before merge when the change touches runtime, orchestration, adapters, interfaces, or decision nodes.
3. Agents also follow `AGENTS.md`.
4. Do not scan dependency or vendor trees (`node_modules/`, `ui/node_modules/`, `.venv/`) unless explicitly requested.
5. For `Last updated:` fields, use the local `America/Denver` date.

## Work Selection

1. Default to the highest-priority active roadmap item.
2. If `Priority Now` is empty, take the highest-priority active non-recurring item in `Maintenance (Non-Priority)`.
3. Standing recurring maintenance is fallback work unless the user explicitly asks for it or it is the only active maintenance item.
4. Do not reopen staged, deferred, or paused work without an explicit request.

## Roadmap Discipline

`docs/ROADMAP.md` is the only active roadmap.

1. Keep entries terse, execution-only, and non-journaled.
2. Active lane entries point to the canonical implementation plan path, not requirement docs.
3. Do not create parallel active backlog or handoff docs.
4. Update the roadmap at handoff to remove completed or obsolete items.
5. Every non-archive folder in `docs/projects/` must appear in the Project Index.
6. Every active or queued roadmap entry must point to an existing path.
7. When roadmap or `docs/projects/` structure changes, run `python scripts/governance/check_docs_project_hygiene.py` before handoff.
8. Standing recurring maintenance entries stay static and point only to durable authority docs, not volatile evidence.

## Planning and Closeout

1. When creating a new active implementation plan, add or update its roadmap entry in the same change.
2. When accepted requirements contain durable contracts or specs, extract them into `docs/specs/` before writing the implementation plan.
3. When a non-maintenance lane completes, move plan, closeout, and history docs to `docs/projects/archive/<lane>/` in the same change.
4. Move long-lived contracts or specs out of completed lanes into `docs/specs/`.
5. Do not leave `Status: Completed` or `Status: Archived` docs in active `docs/projects/`.
6. When closing a phase in a multi-phase initiative, archive only phase-scoped docs. Keep the initiative mini-roadmap and current canonical plan active while later phases remain.
7. For `docs/projects/techdebt/`, leave only standing maintenance docs and docs for cycle ids still active in the roadmap.

## Repository Rules

1. Keep runtime paths in `orket/` async-safe and governance mechanical.
2. Keep permanent decisions in tracked docs or code.
3. Prefer small, reversible changes.
4. Do not commit secrets, `.env`, or local database files.
5. Keep the repo root clean. Put tool-specific metadata under `Agents/` when practical.
6. Do not add small project-subfolder `README.md` files by default.
7. Workflow changes go in `.gitea/workflows/` only unless explicitly approved otherwise.
8. When changing automation, implement and validate the `.gitea` workflow first.
9. After any published artifact change, run:
   - `python scripts/governance/sync_published_index.py --write`
   - `python scripts/governance/sync_published_index.py --check`
10. Commit published artifacts, `benchmarks/published/index.json`, and `benchmarks/published/README.md` together.

## Canonical Commands

- Install: `python -m pip install --upgrade pip && python -m pip install -e ".[dev]"`
- Default runtime: `python main.py`
- Named rock runtime: `python main.py --rock <rock_name>`
- API runtime: `python server.py`
- Test command: `python -m pytest -q`

## Release and Versioning

1. Core engine release/versioning authority lives in `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md`.
2. Core engine version source of truth is `pyproject.toml`.
3. Starting with `0.4.0`, each non-exempt commit kept on `main` must bump the core engine patch version and keep `CHANGELOG.md` aligned. Docs-only commits may be exempt as defined in `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md`.
4. Minor version bumps require closure of a roadmap-tracked major project as defined in `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md`.
5. Do not treat UI work as the default reason for `0.4.0`; follow the active release/versioning policy and roadmap instead.
6. Use `docs/specs/CORE_RELEASE_GATE_CHECKLIST.md` when evaluating core release readiness.
7. Use `docs/specs/CORE_RELEASE_PROOF_REPORT.md` for required minor-release proof records and store completed reports under `docs/releases/<version>/PROOF_REPORT.md`.
8. Until a dedicated core release workflow or tag/version guard is explicitly adopted, treat core release/versioning enforcement as manual and checklist-backed. Do not imply CI enforcement that does not exist.

## Testing

1. Prefer real filesystems, databases, and integration paths over mocks when practical.
2. Keep tests deterministic and isolated.
3. For refactors, prove parity with regression tests.
4. Provider-backed runtime selection and local warmup authority live in `orket/runtime/provider_runtime_target.py`. Runtime paths and provider verification scripts must reuse it.
