# Orket Extension SDK

`orket_extension_sdk` is the public contract package for external Orket extensions.

## Install

Base install:

```bash
pip install orket-extension-sdk
```

From this monorepo source checkout:

```bash
pip install -e ./orket_extension_sdk
```

Optional extras:

```bash
pip install -e "./orket_extension_sdk[tts,testing]"
```

## Public Surface

- Manifest loading and validation
- Workload protocol and runtime context
- Capability registry and provider protocols
- Standard workload result models
- Extension-focused test helpers

## Data Handling Policy

SDK/runtime downloaded data is user-local and should not be committed as long-lived repo content.

Versioned in git:
- small deterministic test fixtures
- data manifests (source URL, expected digest, version)
- fetch scripts

Local-only (ignored):
- downloaded model weights
- voice packs
- large datasets and caches

Current ignored roots:
- `data/voices/`
- `data/models/`
- `data/datasets/`
- `sdk_data/`

Reproducibility contract:
1. Every downloadable asset should have `id`, `url`, `sha256`, and `target_path`.
2. Fetch scripts must verify checksums after download.
3. Artifacts and manifests may reference asset ids/digests, but never embed secrets.
