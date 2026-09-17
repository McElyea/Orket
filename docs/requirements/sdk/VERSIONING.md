# SDK Versioning

Last reviewed: 2026-09-16

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

The architectural-truth core `0.6.6` branch candidate uses SDK `0.7.0a1`, with a new
required `agent_model_use_receipt.v2` host feature. Its compatibility scope is
the matched remediation host checkpoint only, with scoped installed-artifact
proof recorded in the canonical plan; it does not extend to other core versions
or the nominal future window.
Published core 0.6.0/0.6.2 packages retain their SDK 0.6.0 pins. New extension
admissions must review nullable latency handling and explicitly declare v2;
canonical historical v1 receipt reads remain supported without rewriting them.
Candidate hashes, results and unverified surfaces belong to the active
architectural-truth plan. The core branch checkpoint does not publish an SDK
release or establish whole-lane or general release readiness.

The same development candidate also versions generic `GenerateResponse` as
`model_generate_response.v1`, with nullable latency and explicit posture.
Generic `model.generate`/host-API consumers must handle null and preserve those
fields. Its provider/aggregate timing authority is
`docs/specs/MODEL_PROVIDER_TIMING.md`; it does not widen published compatibility.

SDK `0.6.0` admission is explicitly narrowed to verified core `0.6.0` and
`0.6.2`, using the matched artifacts recorded in
`docs/releases/0.6.0/PROOF_REPORT.md` and `docs/releases/0.6.2/PROOF_REPORT.md`.
Tagged core `0.5.9` bundles SDK `0.1.0`; a standalone SDK overlay is not an
admitted configuration. Its historical missing `packaging` dependency is
recorded separately from the namespace conflict. No future core version is
certified by the current matrix.

For a wheel upgrade from a bundling core, install the new core first and then
force-reinstall the pinned standalone SDK. The old core's uninstall removes
SDK files it owned, even when another distribution also claims them. Verify
`pip check`, sole namespace ownership and strict extension validation after
the upgrade. Reproducible matrix producer:
`scripts/proof/run_governed_agent_compatibility.py`; stable local output:
`benchmarks/results/governed_agent/compatibility.json`.

Supply both pinned wheels during the core upgrade so dependency resolution does
not need an unpublished SDK from an index, then restore SDK ownership last:

```bash
python -m pip install --upgrade <core-wheel> <sdk-wheel>
python -m pip install --force-reinstall --no-deps <sdk-wheel>
python -m pip check
orket ext validate <extension-root> --strict --json
```

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
4. The canonical workflow builds with
   `python -m build --sdist --wheel --outdir dist ./orket_extension_sdk`.
   Build, smoke install, and optional wheelhouse copy all use repository-root
   `dist/`; the SDK project-relative default must not silently change that path.
