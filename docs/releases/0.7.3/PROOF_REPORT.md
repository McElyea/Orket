# PRR-v1 final closeout reconciliation

Date: 2026-10-04 (America/Denver)
Owner: Orket Core
Disposition: PRR-01 through PRR-03 complete (3/3); no executable PRR work remains.

## Change and publication boundary

This documentation-only core checkpoint reconciles the archived PRR plan,
roadmap and active architectural-truth umbrella with completed publication.
Historical checkpoints and failed attempts remain identified as history. The
original 0.7.2 report, walkthrough and all 413 retained evidence files are unchanged.

Core `0.7.3` advances only source version/status documentation under the per-commit
version/tag rule. It introduces no runtime change or SDK increment and publishes
no distribution assets or new core/SDK pairing claim. The operator install target
remains the exact tested **core 0.7.2 + SDK 0.7.2**. No empty GitHub release is needed.
The matching annotated `v0.7.3` identifies this correction when its branch/tag
publication receipt succeeds; that Git checkpoint is separate from completed
PRR distribution publication.

- `compatibility_status`: `preserved`
- `affected_audience`: `operator_only`
- `migration_requirement`: `none`
- Operator action: none; continue using the matched 0.7.2 packages.
- Stability: unchanged bounded Windows behavior and proof limitations.

## Verified publication and preserved state

Fresh live readback found local and remote `main` at
`9cb8a89056c46f0c3633e0c20aaac60d80113236`, with no intervening commits.
This reconciliation advances from that commit without resetting history.
The annotated tags peel to that same accepted commit:

| Tag | Annotated tag object |
| --- | --- |
| `v0.7.2` | `8c176bf557c389865816cb25529c5c321fbba369` |
| `sdk-v0.7.2` | `03994c37aa556a87d417fcfc3c0f1a5aa34ce967` |

Fresh downloads of all seven [core release assets](https://github.com/McElyea/Orket/releases/tag/v0.7.2)
and four [SDK release assets](https://github.com/McElyea/Orket/releases/tag/sdk-v0.7.2)
match accepted SHA-256 values and GitHub digests. Both checksum manifests validate
their entries. The identical public `publication.json` has SHA-256
`56ad191f5a45eb6babedd89c7ef41528d34af945c6cdfdc4ff8dc5f6a200814c` and agrees
with accepted commit, refs, package hashes and final-check receipt identity.
Prior 0.7.0/0.7.1 release asset IDs, names, sizes, digests and tag refs remain intact.

Original local publication and closeout receipts remain unchanged, with hashes
`69d783a29bea64907b96b134adc42a22739c58744103388a49db9bdf8e51e849` and
`c4a76e6e43fb731d11b5eaa98e9f8a4ecb45b151b5e5f6667bcebf260ad80f53`.
Their successful 3/3 result is corroborated by the fresh remote observations.
All 20 retained compressed batch receipts decompress to their exact original
bytes, retaining failed probes and cleanup outcomes. All 413 tracked 0.7.2
evidence files match the accepted Git blobs.

Native process observation finds no prior PRR probe process. The first observer
incorrectly counted its own transport PID 42148 as remaining work; that failed
receipt is preserved. Its native lifetime confirms cleanup, and the corrected
observation excludes only its current ancestor chain. It finds no remaining PRR
processes. All commands launched by this reconciliation confirm native cleanup.

The operator-owned llama.cpp PID 45556, started at 2026-10-04T19:24:07Z, still
owns the 127.0.0.1:8080 listener. Live read-only catalog and template observations
confirm `orcarouter_qwen3.8-27b-uncensored-q4_k_l` and the accepted template digest
`8fc57a9f65eaaaee48e80771aea4775f7d3a8adb466a6193d8de551fa124d578`.
The operator override retains its `S` flag and SHA-256
`14724f69f6712ba8c49370855646e55f5f8cf0c06c3e06e07d24dd259b8252ab`.
All four worktree registrations match the prior closeout. Model selection,
server ownership and retained local evidence/resources are preserved. Proof
commands use `ORKET_DISABLE_SANDBOX=1`; no sandbox or infrastructure work is added.

## Operator handoff and proof scope

Use the [0.7.2 operator walkthrough](../0.7.2/OPERATOR_WALKTHROUGH.md) with both
published wheels and its dependency constraints. The API entrypoint is
`python server.py`; obtain that source launcher from the
[accepted commit](https://github.com/McElyea/Orket/blob/9cb8a89056c46f0c3633e0c20aaac60d80113236/server.py).
It is not a wheel entrypoint or release asset. The walkthrough retains exact
provider settings, authentication, completion/cancellation requests and durable
inspection. `orket runtime` remains the CLI entrypoint; its initialized-board
demonstration and intentionally degraded missing-board path remain documented.

Historical live acceptance on Windows Python 3.11.14 and 3.12.2 remains bound to
the exact 0.7.2 packages: actual llama.cpp completion, cancellation, parser and
profiled-turn effects, initialized CLI startup and owned cleanup. Relevant runtime
inputs are unchanged, so this reconciliation reuses that evidence. Fresh remote
downloads and local process/catalog observations are live; they are not fresh
model inference, CLI execution or full-suite proof.

Targeted validation covers project docs hygiene, generated/source authority,
install-surface convergence, core version/changelog/tag policy, unchanged SDK tag
identity and whitespace checks. These are structural checks. Stable local records
are `.tmp/post-release-reliability/reconciliation/state.json`,
`reconciliation-environment/state.json`, `reconciliation-checks/state.json` and
`reconciliation-publication/state.json`. Retained readback evidence and exact
failed/corrected observer receipts are indexed by
[verification.json](../../../benchmarks/results/releases/0.7.3/verification.json).

## Remaining blockers or drift

No required PRR behavior or distribution-publication blocker remains. PRR-S1 is
**not admitted: time reserved for required goals**. The architectural-truth
umbrella stays active; broader marshaller process ownership, plugin/transitive
architecture claims and compatibility obligations remain deferred.
General current-authority runtime proof is unavailable. Prior coverage capture
and discovery limits remain; this documentation change does not rerun or refresh
the full coverage campaign or alter the 89-percent floor. Missing-board startup
remains intentionally degraded. No new Linux/Mac, hosted CI, Docker, remote Gitea,
arbitrary-card, restartable-session or remote inference-termination proof is claimed.

The conservative cutoff remains **2026-10-06 00:00 America/Denver**, with the final
six hours reserved for verification/publication. Closeout completes before that
reserve. Included Pro/Codex access supplies this work; no credits, API billing or
provider switch is introduced. There is no next executable PRR action.

## Exact files touched

- `pyproject.toml`
- `CHANGELOG.md`
- `docs/ROADMAP.md`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/archive/architectural-truth/PRR10042026/POST_RELEASE_RELIABILITY_PLAN.md`
- `docs/releases/0.7.3/PROOF_REPORT.md`
- `benchmarks/results/releases/0.7.3/verification.json`
- `benchmarks/results/releases/0.7.3/reconciliation.zip`

Task-local helpers, downloaded assets, logs and resumable receipts remain ignored
under `.tmp/post-release-reliability/` and `.tmp/prr_reconcile*.py`; the original
publication/closeout receipts and sealed 0.7.2 release files are not modified.
