# Core and SDK 0.7.0 release contract

Status: Accepted release scope and compatibility delta
Date: 2026-10-03
Owner: Orket Core

## Summary

The user authorized main integration and core 0.7.0 after the bounded Windows
ATG-v1 queue completed. This closes the roadmap-tracked remediation execution
body, whose runtime/input/effect and operator contracts materially changed.
The architectural-truth umbrella and separately deferred work remain active.
Affected contracts: core release/versioning, SDK versioning, model timing and
governed-agent receipts, runtime embedding/lifetime, and command compatibility.

## Delta

Release matched core/SDK 0.7.0. SDK behavior is the accepted 0.7.0a1 contract:
`agent_model_use_receipt.v2`, ready-frame negotiation, nullable integer latency
and explicit posture, and `model_generate_response.v1`. The admitted SDK window
is exact core 0.7.0 on Windows; no future core or old published host is certified.
Runtime callers retain explicit captured inputs and owned native/async lifetime.
Internal imports and old implicit construction/ownership defaults are not restored.

Core 0.7.0 preserves the deprecated `python main.py` wrapper and hidden `--rock`
alias through 0.7.x. Their removal requires a separate accepted delta plus passing
installed-root proof; no later removal version is assigned here. This supersedes
the earlier 0.6.x window without adding another implementation or shim.

The release also retains the existing synchronous fixture migration tombstones
and deprecated domain exports. Their planned `BT4-FIXTURE-SYNC-RETIRE` 0.7.0
removal was not completed and remains overdue under Orket Core ownership in the
canonical plan. This release supersedes that cutover date, not the removal
obligation; it assigns no new removal version. `FixtureVerifier.verify` and
`VerificationEngine.verify` still refuse before effects. No executor, forwarding
shim or additional compatibility surface is introduced.

Historical receipts and durable records are not rewritten to imply fresh proof
or authorize new effects. Current-authority runtime proof stays unavailable.
The release admits no new platform, provider, containment or performance claim.

## Migration Plan

1. Install matched core and SDK wheels. On upgrades from old SDK-bundling core,
   reinstall SDK last, then run `pip check` and strict extension validation.
2. Review nullable latency and version/posture fields. New agent manifests declare
   `agent_model_use_receipt.v2`; older ready handshakes refuse before inference.
3. Review direct Python embeddings against current explicit settings/input,
   native-operation and async factory/cleanup contracts. Use `orket runtime`,
   `--card`, `python server.py` and current public interface factories.
4. Validate Windows package identities, SDK isolation, CLI/API/workflow public
   effects, SDK/manifest and release controls. Reuse unchanged source/provider
   proof only with an explicit byte/configuration relevance audit.

## Rollback Plan

Stop new admission and preserve durable evidence before reverting a failed
upgrade. Restore a previously matched core/SDK pair in a fresh environment.
Revalidate extensions for that pair; do not feed new v2 declarations to an old
host or rewrite state to suppress uncertainty. Durable rollback is not automatic.

## Versioning Decision

Minor core and SDK release 0.7.0, October 3, 2026. Compatibility: breaking;
affected audience: all; migration: required. Release acceptance and exact artifact
proof are recorded in `docs/releases/0.7.0/PROOF_REPORT.md`.
