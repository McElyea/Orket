# Release `0.7.0` Proof Report

Date: `2026-10-03` (America/Denver; observations extend into October 4 UTC)
Owner: `Orket Core`
Git tags: core `v0.7.0`, SDK `sdk-v0.7.0`, on the same release commit.
Completed major project: bounded Windows architectural-truth ATG-v1, **10/10**.
Accepted [ATG-10 closeout](docs/projects/archive/architectural-truth/AT10032026-ATG10/CLOSEOUT.md),
canonical [plan](docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md),
[release policy](docs/specs/CORE_RELEASE_VERSIONING_POLICY.md) and
[gate checklist](docs/specs/CORE_RELEASE_GATE_CHECKLIST.md).

## Summary of Change

Merge the completed 142-commit architectural-truth branch into main, then release
matched core and SDK 0.7.0. The finite roadmap body closes explicit-input and
owned-effect work, truthful completion, bounded orchestration extraction, current
typing, and unchanged-floor Windows coverage. The broader architectural-truth
umbrella remains active with its original limits and deferred debt.

The user explicitly authorized merge, version updates and release after the
bounded queue completed at `0b33356f0e666ec67eb7c386dfaff706820960d6` / v0.6.144.
This release adds version/migration metadata and updates a valid test bundle's
engine range; it does not add runtime capabilities. The existing contract test
still proves that the historical `<0.7.0` range rejects core 0.7.0.

## Stability Statement

Acceptance is Windows-scoped. Fresh installed CLI, HTTP health, local workflow,
SDK isolation, API storage/authentication and owner-cleanup observations pass.
The CLI retains a structural-reconciliation startup warning (`degraded` path).
Earlier Windows installed composites and actual llama.cpp library observations
retain their original scopes; they are not fresh inference or full 0.7.0 runs.

Linux/Mac, hosted Quality, live Docker sandbox acceptance, remote Gitea, arbitrary
plugin purity, API/installed-provider inference, remote inference teardown and
production soak are not established by this release. No such route is newly
admitted. General current-authority runtime proof remains unavailable. The
coverage capture/discovery limits and broader marshaller/grounding debt remain.

## Compatibility Classification

- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`

Core pins `orket-extension-sdk==0.7.0`. The supported SDK pairing is exact core
0.7.0 on Windows; future nominal compatibility is not an admission claim.
The [contract delta](docs/architecture/CONTRACT_DELTA_CORE_SDK_0_7_0_2026-10-03.md)
preserves existing deprecated `main.py` and hidden `--rock` through 0.7.x.

## Required Operator or Extension-Author Action

Install both release wheels together and run `python -m pip check`. When upgrading
a historical core that bundled the SDK, force-reinstall the standalone SDK wheel
last with `--force-reinstall --no-deps`. Validate trusted extension roots with
`orket ext validate EXTENSION_ROOT --strict --json` before intake. Review nullable
latency, explicit timing posture, the `agent_model_use_receipt.v2` host feature,
and explicit-input/async-lifetime requirements for Python embeddings. Historical
v1 receipts remain readable; older feature handshakes refuse before inference.
Exact commands and scope appear in [release notes](docs/releases/0.7.0/RELEASE_NOTES.md).

## Proof Record Index

All fresh artifacts below live under `benchmarks/results/releases/0.7.0/`.

| Surface name | Surface type | Proof mode | Proof result | Reason / observed path | Evidence |
| --- | --- | --- | --- | --- | --- |
| Installed `orket runtime` | default_runtime_entrypoint | live | success | existing startup warning / degraded | [Python 3.11](benchmarks/results/releases/0.7.0/py311-surfaces.json), [Python 3.12](benchmarks/results/releases/0.7.0/py312-surfaces.json) |
| `python server.py`, real HTTP health | api_runtime_entrypoint | live | success | none / primary | same two surface records |
| Governed-run demo and durable evidence | workflow_path | live | success | none / primary | [3.11 evidence](benchmarks/results/releases/0.7.0/py311-workflow-evidence.json), [3.12 evidence](benchmarks/results/releases/0.7.0/py312-workflow-evidence.json) |
| Matched core/SDK artifacts and SDK-only install | integration_route | live | success | none / primary | [verification](benchmarks/results/releases/0.7.0/verification.json) |
| Installed API authentication, SQLite isolation and cleanup | integration_route | live | success | none / primary | [API log](benchmarks/results/releases/0.7.0/installed-api-separate.stdout.log), verification |
| Installed webhook signature gate and client cleanup | integration_route | live | success | local ignored event only / primary | [webhook log](benchmarks/results/releases/0.7.0/installed-webhook.stdout.log), verification |
| Retained llama.cpp public-library completion and cancellations | integration_route | live | success | earlier ATG observation, explicitly reused / primary | [ATG-09 verification](docs/projects/archive/architectural-truth/AT10032026-ATG09/VERIFICATION.json), release verification |

## Detailed Proof Records

**Installed default runtime.** `surface_name: installed orket runtime`;
`surface_type: default_runtime_entrypoint`; `proof_mode: live`;
`proof_result: success`; `reason: none`. Fresh noneditable environments use the
actual 0.7.0 wheels on Windows Python 3.11.14 and 3.12.2. Site-package origins
and both versions are asserted. Each console command starts the interactive
driver, receives `quit`, and exits zero. An unsupported extension command exits
one with its expected refusal. Both retain the existing degraded startup warning.
Evidence: the two surface records and outer owned-process receipts in verification.

**API entrypoint.** `surface_name: server.py HTTP health`;
`surface_type: api_runtime_entrypoint`; `proof_mode: live`;
`proof_result: success`; `reason: none`. Only the canonical source launcher is
copied into a private directory; runtime imports come from the installed wheel.
Both interpreters return HTTP 200 and `{"status":"ok"}`. The health-only servers
are terminated and reaped under native Windows Job ownership. This is not itself
graceful API shutdown proof. Separate installed factory lifespan proof below
observes owner cleanup. Earlier cooperative reload proof remains in ATG evidence.

**Real workflow.** `surface_name: governed-run demo`;
`surface_type: workflow_path`; `proof_mode: live`; `proof_result: success`;
`reason: none`. Both installed console commands exercise allowed observation,
approval-required mutation and refused shell work, then write durable evidence.
The exact evidence bytes and hashes are retained. This deterministic workflow
does not establish model inference or approved external side effects.

**Package integration.** `surface_name: matched SDK and core installation`;
`surface_type: integration_route`; `proof_mode: live`; `proof_result: success`;
`reason: none`. Both fresh core/SDK environments pass `pip check`; a third SDK-only
environment imports SDK 0.7.0 from site-packages with no discoverable `orket`
namespace and passes dependency consistency. The 185-case focused selection
also covers SDK contracts, tag/version rules, bundles, package assets and runtime
entrypoints. These mixed-layer tests are not all end-to-end proof.

**API local integration.** `surface_name: installed API store and lifecycle`;
`surface_type: integration_route`; `proof_mode: live`; `proof_result: success`;
`reason: none`. A fresh Python 3.11 process with `-I` asserts installed origins,
starts two actual app lifespans, observes unauthenticated 403/authenticated 200,
writes/reads cards in separate SQLite stores and gets 404 for both cross-store
reads. Both owners report closed after exit. Real application/storage execution
uses in-process HTTP transport; the separate health probe uses a real socket.

**Webhook local integration.** `surface_name: installed signed webhook gate`;
`surface_type: integration_route`; `proof_mode: live`; `proof_result: success`;
`reason: none`. The installed factory rejects an unsigned request with 401,
accepts a signed ignored ping with 200, closes its HTTP client and releases its
handler. This creates no outbound Gitea request or sandbox deployment.

**Retained provider route.** `surface_name: llama.cpp library model stream`;
`surface_type: integration_route`; `proof_mode: live`; `proof_result: success`;
`reason: earlier accepted observation reused at its stated scope`. ATG-09 retains
real HTTP SSE completion, interaction cancellation and caller cancellation through
`run_builtin_workload(model_stream_v1)`, including iterator/response/client/transport
settlement and fail-closed cancellation publication. The server was borrowed and
left running. Current package comparison finds only core text line-ending changes
and SDK version identity; relevant httpx/pydantic/anyio versions match. That audit
is structural relevance evidence, not new provider execution, exact old artifact
identity, complete third-party byte capture or current server health.

## Source, Artifact and Failure Accounting

The retained full Windows source run reports **12,987 passed, 93 unchanged skips,
0 failed**, with **89.21575503742372%** combined coverage at the unchanged 89 floor.
It belongs to v0.6.142 plus the recorded prelaunch metadata, not a fresh 0.7.0 run.
Three pytest warnings and one discarded malformed child coverage shard remain.
Six pre-existing unreported namespace files remain outside default discovery;
the separate all-six zero-hit calculation is **89.06315642066937%**, not measured
execution. Earlier installed composites retain **6,236 passes / 3 skips each**.

Fresh release source controls finish **185 passed, 0 failed, 0 skipped**, with one
Starlette/httpx deprecation warning. Their first run was **182 passed / 3 failed**:
the valid bundle fixture excluded 0.7.0. The fixture now admits `<0.8.0`; existing
contract tests explicitly preserve rejection by the historical `<0.7.0` range.
The initial failure log/XML and successful rerun remain in verification evidence.
No runtime validator, deadline, assertion or skip policy was weakened.

Fresh canonical Ruff, Mypy (1,223 source files), dependency enforcement (zero
violations), strict taxonomy (13,080 items) and critical no-op checks pass.
SDK Ruff passes. These are structural gates, not live runtime proof. Final
docs/authority/render/install/release checks are separately captured before the
commit in the stable final-check receipt; publication refuses any failure.

Both wheels were built from newly built sdists using the frozen clean snapshot.
Their 1,242 core and 31 SDK namespace members match that snapshot exactly.
Against the accepted v0.6.136 core artifact, **214** files differ only in CRLF/LF;
the SDK's only non-line-ending difference is `0.7.0a1` to `0.7.0` version identity.
The initial overly strict byte-audit refusal and valid CRLF metadata parsing
correction are retained. The old wheel is not claimed byte-identical.

The fixture/test corrections and final release evidence are outside packaged
inputs. Exact published artifact identities are in
[SHA256SUMS](benchmarks/results/releases/0.7.0/SHA256SUMS.txt).
Build/install/probe/check processes have native Windows Job cleanup and complete
capture receipts. `ORKET_DISABLE_SANDBOX=1` was set. The local skip-worktree
operational rock was preserved byte-for-byte and replaced only in the packaging
snapshot by its canonical Git blob; no operator data enters the commit or assets.

## Architecture and Release Acceptance

AC-01 through AC-10 pass for the release increment: it adds no dependency edges,
decision nodes, nondeterministic inputs, effects, adapters, runtime claims, events
or replay behavior. AC-10 updates version, SDK, compatibility and roadmap authority
together. This does not erase pre-existing partial C/D/E conformance or expand the
accepted finite closeout. The architecture exception register remains authoritative
for broader debt; AT-EX-006 now records the explicitly retained 0.7.x alias window.

Orket Core records checklist-backed proof-gate acceptance for this bounded Windows
minor release under the user's explicit release instruction. The finite roadmap
execution body is closed; no broader umbrella retirement is implied. Required
runtime/workflow/material integration records above retain their actual scope.
Canonical source and install commands remain in CONTRIBUTOR/CURRENT_AUTHORITY.

Publication requires passing final checks, the release commit with both matching
annotated tags, atomic main/tag push, remote peeled-identity readback, GitHub asset
publication and downloaded-byte comparison. Stable execution receipts are
`.tmp/release-0.7.0/final-checks.json` and `.tmp/release-0.7.0/publication.json`.
The published `publication.json` release asset binds the actual commit, tag objects
and asset hashes without making a source file attest to its own future hash.
There is no PyPI upload or assertion that hosted CI passed.

## Remaining Blockers or Drift

No required gate for the bounded Windows release remains red. Retained limitations
are the degraded CLI startup, general current-authority proof gap, broader
marshaller/callback/plugin/grounding debt, coverage capture/discovery limits and
unverified platforms/integrations listed above. The original 0.7.0 removal target
for `BT4-FIXTURE-SYNC-RETIRE` was not completed. Its existing refusing tombstones
and deprecated exports remain under the explicit release delta; Orket Core retains
the removal obligation in the plan, with no new version assigned. No functioning
synchronous fallback is added. The historical failed/missing
outcomes are preserved. Exact release-increment paths and merged-history paths
are enumerated in [FILES_TOUCHED](docs/releases/0.7.0/FILES_TOUCHED.md).
