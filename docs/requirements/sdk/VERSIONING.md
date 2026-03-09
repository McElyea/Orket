# SDK Versioning

Last reviewed: 2026-03-01

## Canonical Source of Truth
1. SDK version is defined only in `orket_extension_sdk/__version__.py`.
2. The package export in `orket_extension_sdk/__init__.py` must re-export that value.
3. No other file should hardcode SDK version strings.

## CLI Contract
1. `orket sdk --version` must print version data sourced from `orket_extension_sdk.__version__`.
2. If core engine version is printed elsewhere, it is separate from SDK version and must come from its own canonical source.

## Tag Policy
1. SDK release tags use `sdk-vX.Y.Z`.
2. Core engine tags remain unscoped (for example `v0.4.0`) unless changed by policy.
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
