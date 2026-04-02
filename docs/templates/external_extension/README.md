# External Extension Template

This template is the canonical Packet 1 external-extension package surface and publish source surface.

After scaffolding, update:
1. `extension_id`
2. package name in `pyproject.toml`
3. package version and manifest `extension_version` together
3. workload ids and entrypoints
4. script defaults and ports

## Required Layout

```text
extension.yaml
pyproject.toml
src/<extension_pkg>/
tests/
scripts/
```

Package and manifest rules:
1. `project.version` must match manifest `extension_version`
2. `extension_id` is manifest authority and is not derived from `project.name`
3. workload entrypoints must resolve under `src/`

## Bootstrap

Prerequisites:
1. Python 3.11 or newer
2. `ORKET_SDK_INSTALL_SPEC` set to a pip install spec for `orket-extension-sdk`
3. `orket` already available, or `ORKET_HOST_INSTALL_SPEC` set to a pip install spec that provides the `orket` CLI

Activate the Python environment you want the template to use before running bootstrap scripts.

Canonical bootstrap wrappers:
1. Unix: `./scripts/install.sh`
2. PowerShell: `./scripts/install.ps1`

`ORKET_SDK_INSTALL_SPEC` may be a local wheel path or another explicit install spec supplied by Orket Core. SDK distribution authority remains separate from this extension publish surface.

## Validate

Canonical author loop:
1. `python -m orket_extension_sdk.validate . --strict --json`
2. `python -m orket_extension_sdk.import_scan src --json`
3. `orket ext validate . --strict --json`
4. `python -m pytest -q tests/`

Canonical wrappers:
1. Unix: `./scripts/validate.sh`
2. PowerShell: `./scripts/validate.ps1`

Operator meaning:
1. success means admissible for execution consideration only
2. validation success does not grant runtime authority
3. `manifest_version` other than `v0` must fail closed
4. host import scanning stays scoped to extension Python source, using `src/` when present

## Publish

Canonical maintainer publish path:
1. `./scripts/build-release.sh`
2. `./scripts/build-release.ps1`
3. `./scripts/verify-release.sh v<extension_version>`
4. `./scripts/verify-release.ps1 v<extension_version>`

Canonical publish rules:
1. the authoritative published artifact family is one source distribution: `dist/<normalized_project_name>-<version>.tar.gz`
2. `project.version` must match manifest `extension_version`
3. the canonical release tag is `v<extension_version>`
4. the source distribution must preserve the root manifest, `src/`, `tests/`, and `scripts/`
5. publish success does not grant runtime authority

Canonical operator intake path from the published artifact:
1. retrieve the tagged source distribution artifact produced by `.gitea/workflows/release.yml`
2. extract the `.tar.gz` into a local staging directory
3. run `orket ext validate <extracted_root> --strict --json`
4. treat success as admissible for execution consideration only

Companion UI stack (MVP locked):
1. React + Vite + TypeScript
2. SCSS Modules
3. Radix UI primitives
4. Lucide icons
5. Plain `fetch` through a thin typed API client

Build Companion frontend (optional when editing UI source):
1. `npm --prefix src/companion_app/frontend install`
2. `npm --prefix src/companion_app/frontend test`
3. `npm --prefix src/companion_app/frontend run build`

Run local web app:
1. Start Orket host API (`python -m orket.interfaces.api` or your standard host launch path).
2. Set environment:
   - `COMPANION_HOST_BASE_URL` (default `http://127.0.0.1:8082`)
   - `COMPANION_API_KEY` or `ORKET_API_KEY` (one is required; gateway fails closed when neither is set)
   - `COMPANION_EXTENSION_ID` (default `orket.companion`)
   - `COMPANION_UI_HOST` (default `127.0.0.1`)
   - `COMPANION_UI_PORT` (default `3000`; starting port)
   - `COMPANION_TIMEOUT_SECONDS` (default `45`)
   - `COMPANION_GATEWAY_REQUIRE_LOOPBACK` (default `true`)
   - `COMPANION_GATEWAY_REQUIRE_SAME_ORIGIN` (default `true` for mutating routes)
3. Launch template UI:
   - Unix: `./scripts/run.sh`
   - PowerShell: `./scripts/run.ps1`
4. Open `http://127.0.0.1:3000`.
5. The Companion BFF owns outward `/api/*` product routes and calls the host only through `/v1/extensions/{extension_id}/runtime/*`.

Gateway hardening notes:
1. Mutating routes require same-origin requests by default and return `E_COMPANION_GATEWAY_CSRF_BLOCKED` when origin mismatches.
2. Requests from non-loopback clients are rejected by default with `E_COMPANION_GATEWAY_LOOPBACK_REQUIRED`.
3. Payload guardrails return `413` for oversized Companion config/chat/audio payloads.
4. Keep host/API auth strict by setting `ORKET_API_KEY` on the host and `COMPANION_API_KEY` or `ORKET_API_KEY` in the Companion process.

## CI and Release

The template workflow at `.gitea/workflows/ci.yml` expects:
1. `ORKET_SDK_INSTALL_SPEC`
2. `ORKET_HOST_INSTALL_SPEC` unless `orket` is already available on the runner
3. `./scripts/build-release.sh`
4. `./scripts/verify-release.sh`

The tag workflow at `.gitea/workflows/release.yml`:
1. validates and tests the source repo
2. builds the authoritative source distribution
3. verifies `v<extension_version>` tag alignment
4. proves operator intake by extracting the published source distribution and re-running strict host validation
5. uploads `dist/*.tar.gz` as the canonical tagged release artifact
