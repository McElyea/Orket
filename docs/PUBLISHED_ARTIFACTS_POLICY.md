# Published Artifacts Policy

Last reviewed: 2026-02-27

## Purpose
Define how curated benchmark artifacts are published without drift between files and docs.

## Canonical Source
1. `benchmarks/published/index.json` is the source of truth.
2. `benchmarks/published/README.md` is generated from `index.json`.

## Structure
1. Published artifacts are grouped by category folders under `benchmarks/published/`.
2. Current categories:
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

Top-level fields:
1. `catalog_v`
2. `updated_on`
3. `root`
4. `highlight_id`
5. optional `reading_paths`

## Publish Workflow (Mandatory)
1. Copy artifact(s) into the right category folder.
2. Update `benchmarks/published/index.json`.
3. Regenerate README:
```bash
python scripts/sync_published_index.py --write
```
4. Validate sync before commit:
```bash
python scripts/sync_published_index.py --check
```
5. Commit artifact files, `index.json`, and `README.md` together.

## Retention Rules
1. Published artifacts are treated as permanent records.
2. Do not overwrite existing published evidence files.
3. If superseded, add a new versioned file and mark older item in metadata/commentary instead of deleting by default.

## Privacy/Safety Rules
1. Do not publish secrets, private tokens, or local machine-sensitive paths.
2. Set `publish_reviewed=true` only after manual review.
