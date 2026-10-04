# Release 0.7.1 proof report

Date: 2026-10-03 (America/Denver)
Owner: Orket Core
Scope: complete the release cleanup requested after published 0.7.0.
Base: `43c3650d1a29822b2091a75474902c726bcb5048`; matching final tags
`v0.7.1` and `sdk-v0.7.1` identify the patch commit.

## Changes and compatibility

`BT4-FIXTURE-SYNC-RETIRE` removes `FixtureVerifier`, `VerificationEngine`,
their unused helper/instance methods and all corresponding canonical/deprecated
exports. Repository caller inventory found only the tombstones, their export
module and two tests; no production caller used the classes. Constants, the
security exception, unrelated aliases and async fixture execution retain their
existing authority. The revised failure-interpretation contract test also verifies
that caller scenario inputs are not mutated by pure interpretation.

Installed review reproduced a separate host CLI bug: `orket sdk --version` exited
zero but printed `OK: None None (None)`. A new installed end-to-end check failed on
those exact bytes before the fix. The renderer now emits the canonical SDK version
alone; its JSON payload remains unchanged. Exact text and JSON are both checked.

Core and SDK 0.7.1 have an exact dependency pin. SDK implementation changes only
its version identity; its documentation records the verified Windows pairing.
Existing published 0.7.0 tags/assets remain immutable. Migration and classification
are in [release notes](docs/releases/0.7.1/RELEASE_NOTES.md) and the
[contract delta](docs/architecture/CONTRACT_DELTA_FIXTURE_RETIREMENT_0_7_1_2026-10-03.md).
Core compatibility is breaking, audience all, migration required. Public SDK
behavior is preserved; no new extension protocol or provider is admitted.

## Fresh verification

| Proof | Mode | Observed path / result | Evidence |
| --- | --- | --- | --- |
| 372 source controls, zero failures/skips | Mixed test layers | primary / success | [log](benchmarks/results/releases/0.7.1/controls.stdout.log), [XML](benchmarks/results/releases/0.7.1/controls.xml) |
| Installed native async fixture on Windows Python 3.11.14 and 3.12.2 | live | primary / success | [3.11](benchmarks/results/releases/0.7.1/py311-installed.json), [3.12](benchmarks/results/releases/0.7.1/py312-installed.json) |
| Installed console scaffolding, strict validation, existing-target refusal and exact SDK version text/JSON | end-to-end | primary / success | three cases within the 372 on 3.11; [three additional 3.12 passes](benchmarks/results/releases/0.7.1/py312-sdk-host-validation.stdout.log) |
| Installed default runtime, HTTP health and durable governed-run workflow on both interpreters | live | CLI degraded; HTTP/workflow primary / success | installed records and retained workflow evidence |
| Fresh matched installs plus standalone SDK-only import and `pip check` | live package integration | primary / success | [verification](benchmarks/results/releases/0.7.1/verification.json) |
| Ruff, Mypy, dependency, strict taxonomy and critical no-op gates | structural | primary / success | verification command records and logs |

The 372-case selection includes real native fixture success/failure/timeout,
input/security and cancellation controls, sandbox constant consumers, domain
aliases, SDK/manifest/package/entrypoint and authority/release controls. The five
retired-import checks are contract observations, not runtime execution proof.
Actual installed service execution runs a trusted child fixture, adopts its pass
result and confirms native process cleanup on both interpreters. Site-package
origins and both installed versions are asserted. No editable install supplies
these installed observations.

The installed CLI reaches its interactive driver and exits normally. Its existing
structural-reconciliation startup warning remains a degraded path. API health
uses an actual localhost HTTP request. That health-only server is terminated and
reaped; it does not prove graceful API shutdown. The deterministic workflow writes
durable evidence but does not perform model inference.

The standalone SDK environment has no discoverable `orket` namespace. Matched
environments pass dependency consistency and strict validation of both packaged
extension templates. Mypy reports no issues in 1,223 source files; taxonomy has
13,084 items with no missing/conflicting layers. The source run retains 21 pytest
warnings, including Starlette/httpx deprecation, the intentionally retained domain
namespace warning and JUnit `record_property` format warnings. No assertion,
deadline, coverage threshold or skip policy was weakened.

## Artifact and failed-attempt accounting

Both final wheels were built from new sdists using a frozen Git-visible snapshot.
All 1,242 core and 31 SDK namespace members match its source bytes. Relative to
0.7.0, exactly four core files changed: the three fixture/export modules and the
SDK CLI renderer. The SDK namespace changes only `__version__.py`. Exact artifact
hashes and member comparisons are retained in verification and
[SHA256SUMS](benchmarks/results/releases/0.7.1/SHA256SUMS.txt).

The first unpublished candidate passed 369 selected tests and exit-code-only SDK
commands but failed the added semantic version-output check. Its records are
retained with `initial-` filenames; original receipt log basenames map to those
prefixed files. The final verification explicitly supersedes that candidate.
[Failed installed regression](benchmarks/results/releases/0.7.1/initial-sdk-version-counterexample.stdout.log).
Corrected candidate R02 was rebuilt and reverified; no first-candidate artifact is
published. Initial private artifacts remain under `.tmp/release-0.7.1/candidate-a01/`.

The 0.7.1 evidence directory has a scoped Git attribute preserving raw captured
bytes and diagnostic whitespace. Staged Git blobs are checked against every
retained evidence file; line-ending normalization cannot silently invalidate the
recorded hashes. Historical release tags and their text-normalization behavior
are unchanged.

Commands ran with `ORKET_DISABLE_SANDBOX=1` under native Windows Job ownership,
bounded deadlines/capture, and confirmed process cleanup. The local skip-worktree
operational rock remains byte-identical and excluded from commits/builds; its
canonical Git blob is substituted only in the clean packaging snapshot.

## Acceptance and remaining scope

AC-01 through AC-10 pass for the bounded increment: it removes unused class/export
authority, preserves async execution and pure interpretation, and fixes reporting
of an existing canonical value. It adds no runtime effects, provider selection,
schema, replay or completion policy. Current contracts, generated authority,
versioning and roadmap state are updated together. Broader architectural
exceptions remain unchanged; this is not whole-product conformance.

Orket Core records checklist-backed acceptance under the user's release cleanup
instruction, subject to the final publication witnesses. Stable receipts are
`.tmp/release-0.7.1/r02/state.json`, `.tmp/release-0.7.1/final-checks.json` and
`.tmp/release-0.7.1/publication.json`. Completion requires final docs/authority/
install/release checks, annotated tags on the exact commit, atomic main/tag push,
remote identity checks and downloaded GitHub asset byte verification. The public
`publication.json` release asset binds those actual identities without requiring
a source file to attest to its own future commit hash.

The fixture retirement and SDK text-reporting defects are closed. Full coverage,
actual model inference, Linux/Mac, hosted CI, live Docker, remote Gitea and remote
inference teardown were not rerun. Earlier 0.7.0/ATG evidence stays at its original
versions and scopes; it is not presented as fresh 0.7.1 proof. Existing degraded
startup, general current-authority proof gap, coverage capture/discovery limits
and broader marshaller/grounding/plugin debt remain. No PyPI upload is claimed.
Exact paths are listed in [FILES_TOUCHED](docs/releases/0.7.1/FILES_TOUCHED.md).
