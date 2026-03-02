# SDK Data Handling Policy

## Goal
SDK/runtime downloaded data is user-local and should not be committed as long-lived repo content.

## Versioned vs Local
- Versioned in git:
  - small deterministic test fixtures
  - data manifests (source URL, expected digest, version)
  - fetch scripts
- Local-only (ignored):
  - downloaded model weights
  - voice packs
  - large datasets and caches

## Local Data Roots
Current ignored roots:
- `data/voices/`
- `data/models/`
- `data/datasets/`
- `sdk_data/`

## Reproducibility Contract
1. Every downloadable asset should have:
   - `id`
   - `url`
   - `sha256`
   - `target_path`
2. Fetch script must verify checksum after download.
3. Artifacts and manifests may reference asset ids/digests, but never embed secrets.

## Suggested Flow
1. Keep a committed example manifest at `scripts/sdk/data_manifest.example.json`.
2. Copy/edit to local manifest if needed.
3. Run `python scripts/sdk/fetch_data.py --manifest scripts/sdk/data_manifest.example.json`.
