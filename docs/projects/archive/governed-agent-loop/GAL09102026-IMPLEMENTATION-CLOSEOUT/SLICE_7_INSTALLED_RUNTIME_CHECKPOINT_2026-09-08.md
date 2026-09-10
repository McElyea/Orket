# Slice 7 Installed Runtime Checkpoint

Archived on 2026-09-10 after user acceptance and the governed-agent minor-release
closeout. Current release authority: `docs/releases/0.6.0/PROOF_REPORT.md`.
The checkpoint/version/blocker statements below are historical as of their
recorded dates; the accepted closeout supersedes their open release gates.

Date: 2026-09-08
Status: Active Slice 7 evidence; release reconciliation remains open
Observed path: `primary`
Observed result: `success` after correcting the recorded initial failure
Proof classification: live installed runtime plus structural regression gates

## Objective

Prove that built core/SDK/external artifacts execute the existing governed live
path outside a source checkout, including effect decisions and replay.

## What Changed

The first five installed-artifact live tests failed in 9.55 seconds. The first
planner call could not find `model/core/contracts/local_prompt_profiles.json`
under the harness working directory. Runs stayed recovery-pending and API
wakes required recovery; none was reported as completed.

The canonical registry moved, with unchanged contents, to
`orket/runtime/config/local_prompt_profiles.json`. Core package data now owns
it and the loader's default is module-relative. No second copy or missing-file
fallback exists. Explicit context/environment overrides retain precedence.
The migration is recorded in
`docs/architecture/CONTRACT_DELTA_PACKAGED_PROMPT_REGISTRY_2026-09-08.md`.

New live tests cover approval and denial across three application lifespans.
Regression tests cover arbitrary working directories, invalid explicit
overrides, and real clean core wheel/source builds retaining the exact registry.
The canonical suite also exposed a legacy namespace scan traversing ignored
build/venv trees. Both namespace checks now reuse the existing Git-visible
inventory from `project_dump.git_list_files`, retaining tracked and untracked
source coverage while excluding ignored copies and dependencies. That scan
and the existing ignore-rule regression pass together in 1.74 seconds.

## Artifact and Environment Identity

Core remains unreleased worktree version `0.5.10`, based on Git HEAD
`bc3fc138`; these artifacts include uncommitted prior slices and this fix.
This is not a claim that HEAD alone reproduces them.

| Rebuilt artifact | SHA-256 |
| --- | --- |
| Core wheel | `9FC5827A5BEC7F938502F56B5F6B85CE9CD786807780BCFD4D73417CBBDA0329` |
| Core source distribution | `0C9197864FCDC0C237AA902FF28734371C01B5FA57FA030C25BE384E146A4DF4` |
| Canonical registry bytes | `cda6c63bd6301e151846aa1b10ee671de47eb98a02b71328e7d5f22aadc7977c` |

SDK `0.5.0a1` and starter `0.1.0` artifacts retain the hashes in
`SLICE_7_PACKAGING_CHECKPOINT_2026-09-07.md`. Both rebuilt core artifacts contain
the exact registry bytes and zero SDK namespace entries. The core wheel was
reinstalled without dependency changes into the retained clean-install venv;
`pip check` reported no broken requirements. Test-only pytest and pytest-asyncio
were installed separately.

Ollama server/CLI version: `0.33.3`; Python client receipts: `0.6.2`.
The exact installed targets were:

| Role | Model | Inventory digest |
| --- | --- | --- |
| Planner / critic | `qwen2.5:7b` | `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` |
| Actor | `qwen2.5-coder:7b` | `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364` |

Digests above are observed inventory evidence, not a claim that runtime
receipts bind them: receipt `model_digest` remains null.

## Live Verification

The harness copied only the three live test modules and their runtime fixture
helper, not host sources or repository conftest. Its session guard asserted
that `orket`, `orket_extension_sdk`, and installed `governed_agent` imports
resolved under the venv's `Lib/site-packages`. Python isolated mode and pytest
importlib mode prevented checkout import fallback. The catalog pointed to the
extracted final starter sdist, so child execution used that external artifact.

From `.tmp/governed-agent-slice7-20260907-1/live-harness`, with
`ORKET_DISABLE_SANDBOX=1`, `ORKET_RUN_LIVE_AGENT_OLLAMA=1`, and
`ORKET_GOVERNED_AGENT_EXTENSION_ROOT` pointing to the extracted starter:

```powershell
../final-venv/Scripts/python.exe -I -m pytest -q -s --confcutdir=. --import-mode=importlib tests/e2e/test_governed_agent_effect_ollama.py tests/e2e/test_governed_agent_ollama.py tests/e2e/test_governed_agent_supervisor_ollama.py
```

Observed: **5 passed, 2 warnings in 39.00s**. Warnings concern installed
Starlette test-client HTTPX support and an AnyIO portal alias; they are not
provider failures.

1. Single-model CLI and fixed multi-model CLI each completed two iterations
   with verifier-backed truth and measured receipt assertions.
2. API-owned live supervisor completed its two-iteration objective and closed
   with zero tracked background tasks.
3. Approved effect: first lifespan paused with one safe read and a pending
   write approval, without a report file. A second, supervisor-disabled app
   rejected unauthenticated resolution, approved one write, accepted the
   aggregate checkpoint, and idempotently queued one resume wake. The run
   remained operator-blocked until the third app claimed that wake. Final
   state was completed with two effect journals and two wakes. Report JSON
   equaled the SDK fixture's expected counts and source references both before
   and after resumed inference.
4. Denied effect: retained state survived restart, no write or resume wake was
   published, and terminal state was failed-terminal as intended.
5. Both effect paths used exact planner/actor/critic models with measured,
   returned receipts. Replay matched and the entire API inspection before and
   after replay was equal. Every tested lifespan closed with zero tracked tasks.

Each isolated database uses `run-1`, `attempt-1`, and initial `invocation-1`;
these are fixture identities, not globally unique production references.
Test databases are disposable pytest artifacts, not a published evidence store.
No sandbox resources were created.

## Regression and Structural Verification

- Profile loader, async prompting policy, conformance and audit scripts:
  `41 passed in 0.59s`.
- Clean core artifact regression: `1 passed in 14.42s`.
- Runtime-state fixture, workload authority and package-boundary checks:
  `37 passed in 15.87s`.
- Changed-path Ruff and dependency direction: pass.
- Authority and architectural-baseline contracts: `9 passed in 1.87s`.
- Documentation lint: governed-agent lane 18 files and architectural-truth lane
  6 files, zero violations; project hygiene and `git diff --check`: pass
  (existing line-ending notices only).
- Regenerated architecture baseline: `collection_ok=true`,
  `release_ready=false`, retaining 15 exceptions and 128 package Ruff findings.
- Final canonical command, `ORKET_DISABLE_SANDBOX=1 python -m pytest -q`:
  **4543 passed, 58 skipped, 2 warnings in 462.43s**. The warnings are the
  existing deprecated `orket.domain` import and governed-output low-token
  warning. The skips include opt-in live tests, separately executed above.

Architecture checklist: AC-01 through AC-10 pass for this bounded change.
No new dependency edges, decision semantics, timing inputs, effect authority,
or event schemas were added. Registry authority and migration are explicit;
live effect/replay claims follow observed state. The pre-existing oversized
profile module is changed by one replacement line and is not enlarged.

## Not Verified

No publishing, versioned commit/tag, abrupt OS-process kill, hostile-code
containment, comparative model-quality benefit, or production concurrency soak
was performed. Restart here means application lifespan teardown/recreation
with the same SQLite database, not a machine crash. API receipt projections
redact token-count fields; numeric measured usage is asserted on the CLI path.
The extracted external starter is not the separately maintained
`GovernedLocalAgent` release. Full fixed-case acceptance reconciliation and
user acceptance remain required; five passing flows do not close the lane.

## Remaining Blockers or Drift

1. Reconcile all Slice 7/component acceptance gates and obtain user acceptance.
2. Perform core/SDK/external release actions under their respective policies.
3. Existing `AT-EX-003` and wider architectural release-readiness debt remain;
   no architecture exception was waived by installed runtime success.
4. Initial interrupted proof runs were not automatically retried or repaired.
   The successful tests admitted new isolated runs after the package fix.
5. The shared live fixture in `tests/runtime/governed_agent_test_support.py`
   supplies both ticket batches in the initial request. The coordinating plan
   requires batch A first and batch B with prior output on continuation. This
   staged-input acceptance gap is not closed by the two-iteration proof or by
   the correct final report; core owns its reconciliation in the next slice.

## Exact Files Touched in This Slice

1. `model/core/contracts/local_prompt_profiles.json` moved to
   `orket/runtime/config/local_prompt_profiles.json` (no duplicate retained).
2. `orket/runtime/config/local_prompt_profiles.py`
3. `pyproject.toml`
4. `tests/runtime/test_local_prompt_profiles.py`
5. `tests/adapters/test_local_prompting_policy.py`
6. `tests/integration/test_packaged_local_prompt_registry.py`
7. `tests/e2e/test_governed_agent_effect_ollama.py`
8. `CURRENT_AUTHORITY.md`
9. `docs/RUNBOOK.md`
10. `docs/ROADMAP.md`
11. `docs/architecture/CONTRACT_DELTA_PACKAGED_PROMPT_REGISTRY_2026-09-08.md`
12. `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_CONTINUOUS_AGENT_IMPLEMENTATION_PLAN.md`
13. `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/README.md`
14. `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_7_PACKAGING_CHECKPOINT_2026-09-07.md`
15. `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_7_INSTALLED_RUNTIME_CHECKPOINT_2026-09-08.md`
16. `docs/projects/architectural-truth/architectural_truth_baseline.json`
17. `tests/platform/test_no_old_namespaces.py`

Ignored local outputs: clean build stage and rebuilt core distributions,
installed test dependencies/replacement core wheel, and isolated live harness
under `.tmp/governed-agent-slice7-20260907-1`; the dependency checker updated its
canonical `benchmarks/results/dependency_direction_check.json`. Prior unrelated
worktree changes were preserved. No commit, tag, push, or manual filesystem
cleanup ran. The first canonical suite was interrupted during the unbounded
namespace scan, then restarted after the inventory correction. Its earlier
authority-date mismatch was corrected and passed the focused contract checks.
