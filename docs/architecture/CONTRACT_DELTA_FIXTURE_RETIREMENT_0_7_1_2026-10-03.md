# Complete synchronous fixture API retirement

Date: 2026-10-03
Owner: Orket Core
Status: Accepted scope under the user's request to complete remaining release work

## Delta and caller inventory

Close `BT4-FIXTURE-SYNC-RETIRE`, deferred at the published 0.7.0 checkpoint.
Remove `FixtureVerifier` and `VerificationEngine`, their instance/helper methods,
and their deprecated `orket.domain` exports. The legacy fixture/verification module
aliases resolve to the same canonical modules without those classes. No forwarding
shim, replacement synchronous executor or duplicate policy is introduced.

Repository inventory found no production caller of either class: only the legacy
export module, the tombstones themselves and two test files referenced them.
Production consumers of `AGENT_OUTPUT_DIR` retain the same module/value. The
security exception stays canonical in `fixture_verifier` with its existing export.
Unrelated domain aliases and the separately retained CLI/runtime aliases remain.

Installed release review also reproduced a host CLI rendering defect:
`orket sdk --version` printed `OK: None None (None)` despite returning the correct
SDK version in JSON. The text renderer now emits the canonical version alone;
the JSON contract and SDK version source remain unchanged. Exact installed CLI
text/JSON checks and the failed pre-fix observation are retained.

## Migration

Import `FixtureVerificationService` from
`orket.application.services.fixture_verification_service`; provide the workspace
and an explicit aware UTC clock, then await `verify(verification)`. Synchronous
embeddings must enter the application's async lifecycle explicitly. Existing
fixture admission, result interpretation, security events, cancellation and native
process ownership remain unchanged. Old class imports now fail at import/access.

## Verification and rollback

Require canonical/legacy import refusal, actual native fixture success/refusal/
failure/timeout and cancellation controls, unchanged security-error identity,
installed Windows package proof and exact core/SDK pins. A source inspection or
SDK import alone is not execution proof. Release evidence belongs to
`docs/releases/0.7.1/PROOF_REPORT.md`.

If a caller has not migrated, retain the published matched 0.7.0 pair in a separate
environment while migrating it. Preserve durable evidence. Do not recreate a
synchronous executor or retag/replace already published artifacts.

## Versioning

Core 0.7.1 is the policy-required patch completing the previously accepted removal.
Compatibility: breaking; affected audience: all; migration required for retired
imports and matched-package upgrade. SDK 0.7.1 is a packaging/compatibility patch
with unchanged public SDK behavior, paired exactly with Windows core 0.7.1.
Historical 0.7.0 acceptance and its then-overdue record remain immutable.
