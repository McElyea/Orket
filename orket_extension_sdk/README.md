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

## Lifecycle Interceptors

The extension SDK does not register `TurnLifecycleInterceptor` instances.
Host-side Orket runtime interceptors are classified at registration as either
`advisory` or `mandatory`. Advisory interceptor crashes are logged and isolated;
mandatory interceptor crashes fail the affected turn before the governed action
continues.

## Manifest Runtime Declarations

`ExtensionManifest.config_sections` declares additional host config sections an
extension expects the host to preserve and resolve. The host registers these
sections during extension install or catalog listing.

`ExtensionManifest.allowed_stdlib_modules` declares standard-library modules an
SDK extension is allowed to import. SDK workloads are statically scanned and
then run in a host-managed subprocess with a stdlib import hook; undeclared
static or dynamic stdlib imports fail. Safe examples for many extensions include
`json`, `pathlib`, and `dataclasses`. Dangerous or side-effecting modules such
as `os`, `subprocess`, and `socket` should not be declared unless the extension
has explicit host approval for that capability. If the list is empty, SDK
workloads may not import stdlib modules beyond the runtime base allowlist.
Legacy workloads keep compatibility behavior: internal Orket imports remain
blocked, and stdlib allowlist enforcement applies only when the legacy manifest
declares a non-empty allowlist.

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
