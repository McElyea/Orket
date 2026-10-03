# ATG-09: Windows quality and provider acceptance

Last updated: 2026-10-03 (America/Denver)
Status: Windows evidence accepted; completion requires matching v0.6.143 publication
Queue: ATG-v1 / ATG-09

## What changed

Completed the user-amended Windows acceptance at source base `a6b99e575682d9b721983381e75f80402c8018d2`
(v0.6.142), with only the prelaunch receipt link dirty during source verification.
No runtime/test repair was needed. This checkpoint changes only release, queue and
archival evidence metadata; existing assertions, deadlines, skip declarations,
complete source selection, branch measurement and the 89% floor remain unchanged.

## What was verified

Observed path: **primary**. Observed result: **success** for Windows acceptance.
The canonical native Python 3.11.14 full suite reports **12,987 passed, 0 failed,
93 skipped and 3 pytest warnings** in 5,137.25 pytest seconds. All 13,080 collected items
are represented; strict taxonomy independently reports 13,080. Combined coverage
is **89.21575503742372%**: 71,375/77,475 statements and 17,665/22,328 branches.
All 5,746 frozen inputs stayed unchanged. The recorder joined pytest and observed
zero remaining descendants among 5,820 sampled native identities. Process sampling
is bounded observation, not arbitrary process-isolation proof. Sandbox creation
was disabled. The selection retains individual unit/contract/integration/end-to-end
limits; aggregate counts do not turn every case into live public-path proof.

Fresh structural gates pass: canonical Ruff, dependency direction, strict taxonomy
and critical no-op checks. Canonical Mypy is reused only after exact relevant-source
and configuration validation against its successfully settled native receipt.
Final docs/authority/install-convergence/release validation is linked below and
must pass before publication. These checks do not establish general runtime truth.

Independent structural readback validates retained live proof: Windows 3.11.14
and 3.12.2 each retain 6,215 unaffected passes plus 21 exact reload replacement/addition
passes, giving **6,236 passes / 3 unchanged skips** each. Original 6,231-pass campaigns
are not added wholesale to scoped reruns. Package members, installed origins,
dependencies, raw artifacts and native cleanup match; runtime artifacts are v0.6.136.
The fixture-normalized source selection retains **119 passes / 0 skips**. Actual
llama.cpp public-library completion, interaction cancellation and caller cancellation
retain their observed inference and original iterator/client/response/transport
settlement. No installed/provider campaign was repeated to reconstruct context.

[VERIFICATION.json](VERIFICATION.json) binds exact argv/environment, counts, skips,
warnings, raw artifact hashes, relevant reuse scopes and the frozen source identity.
Raw ignored artifacts are local and are not guaranteed to exist in another checkout.
The three warnings (Starlette/httpx deprecation, low max_tokens and Pydantic field
alias use) remain disclosed; no dependency upgrade is introduced to hide them.
Separately, coverage discarded one malformed child SQLite shard. Its original bytes
and warning are retained alongside the intact merged measurement. The passing
89.215755% is computed only from valid merged data; the lost shard contributes no
invented execution. Complete child-measurement capture is not claimed. The source
selection, branch configuration and gate remain unchanged; the independent audit
records exact configured source inclusion and this measurement limit. Coverage's
unchanged default discovery also omits six unexecuted files in namespace directories
without `__init__.py`; the old and current reports omit the same exact files. Their
paths are recorded in the independent audit. This is a pre-existing measurement
limit, not a new exclusion or evidence that those files executed.
Separate static analysis with the same coverage analyzer adds all six missing files
(133 statements and 38 branches) with zero execution credit: **89,040 / 99,974 =
89.06315642066937%**, still above 89%. This confidence calculation neither changes
the observed report nor claims execution of the missing files or unreadable shard.

## What was not verified

Linux/Mac, the complete hosted Gitea workflow, live Docker sandbox deployment,
API-provider transport, installed-provider execution, optional WatchFiles and remote
inference/server teardown are not established by these accepted scopes. The local
llama.cpp server remains operator-owned. General current-authority runtime proof
is explicitly unavailable. No whole-product, minor-release, main-merge or whole-lane
retirement claim follows.

## Remaining blockers or drift

No required Windows behavior gate remains red. Final metadata validation and
publication must succeed before ATG-10 starts. Their stable receipts are
`.tmp/atg09-windows-closeout-checks.json` and
`.tmp/atg09-windows-closeout-publication.json`; completion requires atomic branch/tag
push, exact remote commit/annotated-tag identities and a clean worktree. The matching
tag is `v0.6.143`. ATG-10 retains the publication readback in its tracked receipt.

Earlier failed/absent outcomes remain in the
[pre-amendment history](../AT10032026-WINDOWS-SCOPE/PLAN_BEFORE_WINDOWS_SCOPE.md)
and unchanged workset history. They are not rewritten as passing. Deferred marshaller
subprocess ownership, grounding residue normalization, broader transitive C/D/E
claims and existing compatibility windows remain outside the fixed queue.

## Exact files touched

- `pyproject.toml`
- `CHANGELOG.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/GOAL_WORKSETS.json`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/archive/architectural-truth/AT10032026-ATG09/CLOSEOUT.md`
- `docs/projects/archive/architectural-truth/AT10032026-ATG09/VERIFICATION.json`
