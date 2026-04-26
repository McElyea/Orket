# SDK Versioning

Last reviewed: 2026-04-25

## Canonical Source of Truth
1. SDK version is defined only in `orket_extension_sdk/__version__.py`.
2. The package export in `orket_extension_sdk/__init__.py` must re-export that value.
3. No other file should hardcode SDK version strings.
4. The SDK uses its own semantic version. It does not follow the core engine version.

## Core Compatibility SLA
1. SDK `0.Y.Z` is compatible with Orket core `0.Y.*` through `0.(Y+2).*` unless a release note explicitly narrows the window.
2. Compatibility means manifest validation, workload protocol models, capability registry contracts, import scanning, and `orket ext validate <extension_root> --strict --json` remain usable without source changes for extensions that stay inside the public SDK surface.
3. Compatibility does not cover internal `orket.*` imports, host-private control-plane models, or behavior that bypasses the SDK package.
4. When a core release intentionally breaks the SLA, the core release notes must name the affected SDK versions, migration requirement, and replacement path.
5. When an SDK release intentionally breaks compatibility with an admitted core window, the SDK changelog must name the affected core versions and migration requirement.

## CLI Contract
1. `orket sdk --version` must print version data sourced from `orket_extension_sdk.__version__`.
2. If core engine version is printed elsewhere, it is separate from SDK version and must come from its own canonical source.

## Tag Policy
1. SDK release tags use `sdk-vX.Y.Z`.
2. Core engine tag policy is governed separately by `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md`.
3. Release automation should assert:
   - tag version == `orket_extension_sdk.__version__`
   - fail on mismatch to prevent drift.

## Release Automation
1. Canonical SDK release workflow: `.gitea/workflows/sdk-package-release.yml`.
2. Tag/version guard command:
   - `python scripts/sdk/check_sdk_tag_version.py --tag sdk-vX.Y.Z --repo-root .`
3. Workflow scope:
   - run SDK tests and lint
   - build wheel/sdist for `orket_extension_sdk`
   - perform smoke install of built wheel
