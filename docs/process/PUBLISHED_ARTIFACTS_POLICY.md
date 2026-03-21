# Published Artifacts Policy

Last reviewed: 2026-03-19

## Purpose
Define how benchmark artifacts move from candidate staging to approved publication without drift between files and docs.

## Canonical Sources
1. `benchmarks/staging/index.json` is the source of truth for candidate artifacts awaiting approval.
2. `benchmarks/staging/README.md` is generated from `benchmarks/staging/index.json`.
3. `benchmarks/published/index.json` is the source of truth for approved published artifacts.
4. `benchmarks/published/README.md` is generated from `benchmarks/published/index.json`.

## Structure
1. Candidate artifacts are grouped by category folders under `benchmarks/staging/`.
2. Approved artifacts are grouped by category folders under `benchmarks/published/`.
3. Current categories:
   - `ODR/`
   - `General/`

## Required Metadata
Each artifact row in `index.json` must include:
1. `id`
2. `category`
3. `path`
4. `title`
5. `summary`
6. `signals`
7. `source_path`
8. `publish_reviewed`

Top-level fields for either catalog:
1. `catalog_v`
2. `updated_on`
3. `root`
4. `highlight_id`
5. optional `reading_paths`

Optional governed claim fields for artifact rows:
1. `claim_tier`
2. `compare_scope`
3. `operator_surface`
4. `policy_digest`
5. `control_bundle_ref` or `control_bundle_hash`
6. `artifact_manifest_ref`
7. `provenance_ref`
8. `determinism_class`

When present, these fields are first-class publication consumer surfaces and must stay truthful to the underlying proof bundle. Rows that omit them remain transition-rule debt under [docs/specs/ORKET_DETERMINISM_GATE_POLICY.md](docs/specs/ORKET_DETERMINISM_GATE_POLICY.md).

## Staging Workflow (Mandatory For Agent-Proposed Artifacts)
1. Copy candidate artifact(s) into the right category folder under `benchmarks/staging/`.
2. Update `benchmarks/staging/index.json`.
3. Keep `publish_reviewed=false` until the user explicitly approves publication.
4. Regenerate the staging README:
```bash
python scripts/governance/sync_published_index.py --index benchmarks/staging/index.json --readme benchmarks/staging/README.md --write
```
5. Validate sync before commit:
```bash
python scripts/governance/sync_published_index.py --index benchmarks/staging/index.json --readme benchmarks/staging/README.md --check
```
6. Commit candidate artifact files, `benchmarks/staging/index.json`, and `benchmarks/staging/README.md` together.

## Publish Workflow (Approval Required)
1. Do not add or move artifacts into `benchmarks/published/` without explicit user approval.
2. After approval, copy the approved artifact(s) into the right category folder under `benchmarks/published/`.
3. Update `benchmarks/published/index.json`.
4. Regenerate the published README:
```bash
python scripts/governance/sync_published_index.py --write
```
5. Validate sync before commit:
```bash
python scripts/governance/sync_published_index.py --check
```
6. Commit approved artifact files, `benchmarks/published/index.json`, and `benchmarks/published/README.md` together.

## Retention Rules
1. Published artifacts are treated as permanent records.
2. Do not overwrite existing published evidence files.
3. If superseded, add a new versioned file and mark older item in metadata/commentary instead of deleting by default.
4. Staging artifacts are review candidates and may be revised, replaced, or withdrawn before publication approval.

## Privacy/Safety Rules
1. Do not stage or publish secrets, private tokens, or local machine-sensitive paths.
2. Set `publish_reviewed=true` only after manual review and explicit user approval.
