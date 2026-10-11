# 0.8.8: Root and docs accuracy audit

Date: 2026-10-10 (America/Denver)
Status: Scoped documentation audit and corrections complete.
Baseline: `1e48606fb1b7249e48ca3706f462fd6848a4b2cc` (0.8.7).

## What changed

The initial Git-visible inventory covered 1,265 root/docs text documents:
280 current/reference candidates and 985 archive, history, release or contract
delta records. This is a mechanical inventory, not a claim that every paragraph
or historical behavior received new runtime acceptance. Root licenses/notices
were also checked against the package source-copy authority.

Semantic review focused on root user/authority documents and the current docs
index, API catalog, security, testing, contributor, runbook, recovery, installation
and release-proof guidance. References were checked across the broader tree.
Runtime and SDK behavior are unchanged; the core patch metadata follows the
per-commit release policy. Compatibility is `preserved`, audience `all`, migration
`none`.

### Ship-risk debt

- Corrected the authentication recipe: bypass requires the captured security
  profile and local environment posture as well as the flag; configured keys
  still have to match. Documented WebSocket compatibility mode and the distinct
  governed-agent webhook API-key/HMAC boundary.
- Added 17 missing governed-agent method/path entries and aligned outward-history
  parameter names with the mounted schema, including the explanatory notes.
- Replaced advertised legacy canary commands with the tested current security
  selections, while preserving the unresolved wrapper failure explicitly.
- Fixed Bash examples that used Windows `set`/`copy`, including JSON quoting.
  Explained workspace-relative quickstart ledger paths and removed fixed old
  versions from the Mac candidate installation recipe.

### Exploration-safe debt

- Repaired 189 repository-root-relative Markdown links in 27 reference documents
  to resolve from their containing documents. Updated moved ToolBox/test pointers.
- Expanded the documentation index and root Gardener entry point. Marked the
  September Gardener proposal and February volatility/benchmark snapshots as
  historical, with current authority pointers where appropriate.

### Self-deception debt

- Test layer commands now follow collected markers rather than directory names.
  Source inspection, controlled HTTP, native CLI and real model evidence retain
  distinct claim scopes.
- Release policy/template now reuse the existing testing-policy live definition.
  The [recorded clarification](../../architecture/CONTRACT_DELTA_DOCS_PROOF_LABELS_2026-10-10.md)
  preserves historical report bytes and does not convert them to current proof.
- API inventory verification is labeled structural. Historical results and Mac
  candidate instructions do not imply present model or platform acceptance.

## What was verified

**Structural proof: primary / success.** The mounted FastAPI OpenAPI schema was
constructed in an isolated project root without starting its lifespan/services.
All **123 HTTP method/path entries** have matching documentation; no extra
documented HTTP method/path pairs remain. This is not endpoint payload or live
execution coverage. WebSocket authentication was checked in the scoped tests below.

The broader current/reference Markdown scan found **120 distinct local Python
command targets**, all present, with no unresolved local Markdown heading anchors
in that selection. The initial 194 nonhistorical link candidates resolve to 189
repaired links, one deliberate VS Code absolute-path example in `AGENTS.md`, and
four source-era/external-checkout links in three dated llama.cpp verification
records. Archive/history/release links remain historical; the scanner counted
817 such unresolved references. Missing inline code-path candidates were reviewed
as generated outputs, historical paths, removed-path descriptions or symbol/line
notation after correcting the two current source/test references.

Strict taxonomy collection passed for **13,454 tests**: 823 unit, 5,149 contract,
7,369 integration and 113 end-to-end. Collection had no errors or unclassified
items; those totals do not mean the entire suite executed. Install-surface
convergence, canonical license-copy checks, docs-project hygiene, generated
authority equality/validation, core version/changelog policy and whitespace
checks passed. Authority validation still reports `current_proof_established=false`.

Seven edited Bash export lines were executed in Git Bash; the resulting values
preserved the wildcard path and JSON field map. The two Mac install blocks passed
Bash syntax checking only. HTML parsing retained eight presentation slides and
verified all seven local link targets; no visual rendering is claimed.

**Executed contract/integration evidence: primary / success, non-live.** With
`ORKET_DISABLE_SANDBOX=1`:

- `python -m pytest -q tests/interfaces/test_api.py -k "health_check or version or insecure or websocket_events"`:
  **10 passed**, 89 deselected (contract selection).
- `python -m pytest -q tests/interfaces/test_webhook_factory.py`:
  **9 passed** (integration selection).
- `python scripts/governance/run_cli_regression_smoke.py --out <audit-output>`:
  **PASS**, six recorded CLI steps including actual scaffold, apply and no-op
  behavior, plus two explicitly labeled dry-run steps.
- `orket-quickstart --decision approve --workspace <fresh-audit-workspace>` and
  the separate `deny` workspace both succeeded. Approval wrote the expected
  `hello from a governed Orket action` file; denial created no output file.
  The documented verifier accepted both six-event ledgers. This demo uses its
  shipped mock model and is not live model proof.

The test selections emitted the existing Starlette/httpx deprecation warning;
there were no failed or skipped selected tests. No model server or Docker sandbox
was launched, and no new or modified test implementation was needed.

**Legacy canary: blocked / failure.** Executing
`python scripts/security/security_canary.py` exited 1 before its assertions:
`AttributeError: module 'orket.interfaces.api' has no attribute 'app'`.
The default dependency from `release_smoke.py` was confirmed by source inspection;
the entire release wrapper was not executed. The passing scoped controls above
do not repair those wrappers or establish whole-release readiness.

Retained local evidence is under `benchmarks/results/releases/0.8.8/`:
`docs-audit.json`, the inventory/route/command receipts, taxonomy output,
API/webhook JUnit reports, CLI smoke receipt, quickstart logs and the reproduced
canary traceback. Audit producers/workspaces remain in ignored `.tmp/docs-audit/`.
Receipts use stable paths and the shared diff ledger; they are local evidence,
not published benchmark artifacts.

## What was not verified

No new actual model inference, full runtime/API workflow acceptance, fresh package
installation, native macOS run, external webhook delivery, full test suite or
coverage campaign. The 120 command targets were checked for presence, not all
executed. External websites and every historical/proposed behavior were not
revalidated. No hosted CI, registry publication or HTML visual/print acceptance
is claimed. Existing installation/model reports retain their original candidates.

## Remaining blockers or drift

- **Ship-risk debt:** the legacy security canary and default release-smoke chain
  need migration to application factories and owned lifespans. This docs-only
  change exposes the failure; it does not fix the tooling implementation.
- **Exploration-safe debt:** dated records retain source-era links and historical
  paths. The two externally gated roadmap entries still show review dates of
  2026-04-06. Their owner sign-off/evidence was not supplied, so this audit does
  not invent acceptance, new dates or lane changes.
- **Self-deception debt:** whole-runtime/current-provider and native Mac
  acceptance remain outside this evidence. Older releases using `compatible`
  rather than the canonical `preserved` compatibility token, or broader `live`
  terminology, retain their original text; use the current policies for new work.

## Exact files touched

- `CHANGELOG.md`
- `CURRENT_AUTHORITY.md`
- `README.md`
- `docs/API_FRONTEND_CONTRACT.md`
- `docs/CONTRIBUTOR.md`
- `docs/ORKET_GARDENER_INTEGRATION_BRIEF.html`
- `docs/README.md`
- `docs/RUNBOOK.md`
- `docs/SECURITY.md`
- `docs/TESTING_POLICY.md`
- `docs/architecture/CONTRACT_DELTA_DOCS_PROOF_LABELS_2026-10-10.md`
- `docs/architecture/VOLATILITY_BASELINE.md`
- `docs/architecture/current_authority.json`
- `docs/guides/MACOS_LOCAL_INSTALL.md`
- `docs/observability/BENCHMARK_FAILURE_LEDGER.md`
- `docs/process/FAILURE_RECOVERY.md`
- `docs/process/PUBLISHED_ARTIFACTS_POLICY.md`
- `docs/projects/OrketUI/ORKET_EXTENSION_UI_HOST_SEAM_MAP_V1.md`
- `docs/projects/OrketUI/ORKET_EXTENSION_UI_OBJECT_MODEL_V1.md`
- `docs/projects/OrketUI/ORKET_EXTENSION_UI_REQUIREMENTS_V1.md`
- `docs/projects/OrketUI/ORKET_EXTENSION_UI_WRITE_SEAM_INVENTORY_V1.md`
- `docs/releases/0.8.8/PROOF_REPORT.md`
- `docs/specs/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md`
- `docs/specs/01_EXECUTION_OBJECT_MODEL_REQUIREMENTS.md`
- `docs/specs/02_WORKLOAD_LIFECYCLE_AND_SUPERVISION_REQUIREMENTS.md`
- `docs/specs/03_FAILURE_TAXONOMY_AND_RECOVERY_REQUIREMENTS.md`
- `docs/specs/04_CAPABILITY_AND_EFFECT_MODEL_REQUIREMENTS.md`
- `docs/specs/05_RESOURCE_LEASE_AND_OWNERSHIP_REQUIREMENTS.md`
- `docs/specs/06_RECONCILIATION_AUTHORITY_REQUIREMENTS.md`
- `docs/specs/07_OPERATOR_CONTROL_SURFACE_REQUIREMENTS.md`
- `docs/specs/08_MINIMAL_ADMISSION_AND_SCHEDULING_REQUIREMENTS.md`
- `docs/specs/10_EFFECT_JOURNAL_AND_CHECKPOINT_REQUIREMENTS.md`
- `docs/specs/11_NAMESPACE_AND_WORKLOAD_COMPOSITION_REQUIREMENTS.md`
- `docs/specs/12_SAFE_TOOLING_WORKLOAD_INTEGRATION_REQUIREMENTS.md`
- `docs/specs/CARD_AUTHORING_SURFACE_V1.md`
- `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`
- `docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md`
- `docs/specs/CORE_RELEASE_GATE_CHECKLIST.md`
- `docs/specs/CORE_RELEASE_PROOF_REPORT.md`
- `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md`
- `docs/specs/FLOW_AUTHORING_SURFACE_V1.md`
- `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
- `docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md`
- `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md`
- `docs/specs/TOOL_EXECUTION_GATE_V1.md`
- `docs/specs/TRUTHFUL_RUNTIME_MEMORY_TRUST_CONTRACT.md`
- `pyproject.toml`
