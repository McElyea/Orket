# Contributor Guide

## Startup

1. Before substantive work, read in order:
   - `docs/CONTRIBUTOR.md`
   - `docs/ROADMAP.md`
   - `docs/ARCHITECTURE.md`
2. Read `docs/architecture/ARCHITECTURE_COMPLIANCE_CHECKLIST.md` before merge when the change touches runtime, orchestration, adapters, interfaces, or decision nodes.
3. Agents also follow `AGENTS.md`.
4. Do not scan dependency or vendor trees (`node_modules/`, `.venv/`) unless explicitly requested.
5. For `Last updated:` fields, use the local `America/Denver` date.

## Work Selection

1. Default to the highest-priority active roadmap item.
2. If `Priority Now` is empty or contains only a maintenance-only posture marker, take the highest-priority active non-recurring item in `Maintenance (Non-Priority)`.
3. Standing recurring maintenance is fallback work unless the user explicitly asks for it or it is the only active maintenance item.
4. Do not reopen staged, deferred, or paused work without an explicit request.

## Roadmap Discipline

`docs/ROADMAP.md` is the only active roadmap.

1. Keep entries terse, execution-only, and non-journaled.
2. Active lane entries point to the canonical implementation plan path, not requirement docs.
3. Staged / Waiting and Paused / Checkpointed entries include only the canonical lane authority path and the smallest valid reopen trigger.
4. Keep detailed reentry criteria, missing-proof status, and historical execution detail in the canonical lane file, not in separate reentry docs.
5. Do not create parallel active backlog or handoff docs.
6. Update the roadmap at handoff to remove completed or obsolete items.
7. Every non-archive folder in `docs/projects/` must appear in the Project Index.
8. Every active or queued roadmap entry must point to an existing path.
9. When roadmap or `docs/projects/` structure changes, run `python scripts/governance/check_docs_project_hygiene.py` before handoff.
10. Standing recurring maintenance entries stay static and point only to durable authority docs, not volatile evidence.

## Planning and Closeout

1. When creating or revising a staged lane, keep detailed reentry criteria in the lane's canonical plan or authority file.
2. When creating a new active implementation plan, add or update its roadmap entry in the same change.
3. When accepted requirements contain durable contracts or specs, extract them into `docs/specs/` before writing the implementation plan.
4. When a change updates a durable contract, record the contract delta using `docs/architecture/CONTRACT_DELTA_TEMPLATE.md`.
5. When a non-maintenance lane completes, move plan, closeout, and history docs to `docs/projects/archive/<lane>/` in the same change.
6. Move long-lived contracts or specs out of completed lanes into `docs/specs/`.
7. Do not leave `Status: Completed` or `Status: Archived` docs in active `docs/projects/`.
8. When closing a phase in a multi-phase initiative, archive only phase-scoped docs. Keep the initiative mini-roadmap and current canonical plan active while later phases remain.
9. For `docs/projects/techdebt/`, leave only standing maintenance docs and docs for cycle ids still active in the roadmap.

## Repository Rules

1. Keep runtime paths in `orket/` async-safe and governance mechanical.
2. Keep permanent decisions in tracked docs or code.
3. Prefer small, reversible changes.
4. Do not commit secrets, `.env`, or local database files.
5. Keep the repo root clean. Put tool-specific metadata under `Agents/` when practical.
6. Do not add small project-subfolder `README.md` files by default.
7. Workflow changes go in `.gitea/workflows/` only unless explicitly approved otherwise.
8. When changing automation, implement and validate the `.gitea` workflow first.
9. Agent-proposed benchmark artifacts must go to `benchmarks/staging/` until the user explicitly approves publication.
10. After any staging artifact change, run:
   - `python scripts/governance/sync_published_index.py --index benchmarks/staging/index.json --readme benchmarks/staging/README.md --write`
   - `python scripts/governance/sync_published_index.py --index benchmarks/staging/index.json --readme benchmarks/staging/README.md --check`
11. After any published artifact change, run:
   - `python scripts/governance/sync_published_index.py --write`
   - `python scripts/governance/sync_published_index.py --check`
12. Commit staged artifacts, `benchmarks/staging/index.json`, and `benchmarks/staging/README.md` together. Commit published artifacts, `benchmarks/published/index.json`, and `benchmarks/published/README.md` together.

## Canonical Commands

- Install: `python -m pip install --upgrade pip && python -m pip install -e ".[dev]"`
- Default runtime: `python main.py`
- Named card runtime: `python main.py --card <card_id>`
- API runtime: `python server.py`
- Test command: `python -m pytest -q`

Compatibility-only CLI alias:
`python main.py --rock <rock_name>` remains accepted for existing callers, but it is hidden from normal help and routes to the canonical named card runtime.

## Release and Versioning

1. Core engine release/versioning authority lives in `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md`.
2. Core engine version source of truth is `pyproject.toml`.
3. Starting with `0.4.0`, each commit kept on `main` must advance the core engine version, keep `CHANGELOG.md` aligned, and create and push the matching annotated Git tag `v<version>`. The default release step is a patch bump; minor release steps are allowed only as defined in `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md`.
4. Minor version bumps require closure of a roadmap-tracked major project as defined in `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md`.
5. Do not treat UI work as the default reason for `0.4.0`; follow the active release/versioning policy and roadmap instead.
6. Use `docs/specs/CORE_RELEASE_GATE_CHECKLIST.md` when evaluating core release readiness.
7. Use `docs/specs/CORE_RELEASE_PROOF_REPORT.md` for required minor-release proof records and store completed reports under `docs/releases/<version>/PROOF_REPORT.md`.
8. CI now enforces core version/changelog alignment, commit-range version advancement, commit-range tag alignment for pushed `main`, and tagged core release format through `.gitea/workflows/core-release-policy.yml` and `scripts/governance/check_core_release_policy.py`.
9. Final proof-gate acceptance remains checklist-backed and owned by Orket Core.
10. The canonical operator path for release-only core release prep is `python scripts/governance/prepare_core_release.py --tag v<major>.<minor>.<patch>`.
11. Use `--commit-and-tag` only after the matching changelog entry and any required proof report are complete and no unrelated worktree changes remain.
12. For normal non-release-only work, each versioned commit destined for `main` must carry its matching annotated tag on that exact commit, and the branch tip plus those tags must be pushed together. A core version bump is not complete until its matching tag is pushed.

## Testing

1. Prefer real filesystems, databases, and integration paths over mocks when practical.
2. Keep tests deterministic and isolated.
3. For refactors, prove parity with regression tests.
4. Provider-backed runtime selection and local warmup authority live in `orket/runtime/provider_runtime_target.py`. Runtime paths and provider verification scripts must reuse it.
5. The general pytest suite fails closed on Docker sandbox creation through `tests/conftest.py`. Only explicit live sandbox acceptance work may create real `orket-sandbox-*` resources.
6. When maintenance work needs live sandbox baseline proof, run `python scripts/techdebt/run_live_maintenance_baseline.py --baseline-id <baseline_id> --strict`.
7. Provider-backed live proof scripts/tests that are not explicit sandbox acceptance work must set `ORKET_DISABLE_SANDBOX=1`.
8. Any flow that intentionally creates real `orket-sandbox-*` resources must prove teardown in the same execution path before temp-workspace cleanup or handoff. Do not rely on delayed TTL cleanup for routine proof runs.
