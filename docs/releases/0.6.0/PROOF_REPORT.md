# Release `0.6.0` Proof Report

Date: `2026-09-10`
Owner: `Orket Core`
Git tags: core `v0.6.0`, SDK `sdk-v0.6.0`; external repository `v0.2.0`.
Completed major project: governed continuous-agent implementation.
Accepted closeout: [implementation archive](docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_CONTINUOUS_AGENT_IMPLEMENTATION_PLAN.md).
Release policy: [CORE_RELEASE_VERSIONING_POLICY.md](docs/specs/CORE_RELEASE_VERSIONING_POLICY.md).
Release checklist: [CORE_RELEASE_GATE_CHECKLIST.md](docs/specs/CORE_RELEASE_GATE_CHECKLIST.md).

## Summary of Change

Complete Slices 0–7 of the governed continuous-agent lane. A separately packaged
public SDK and trusted external reference workload use fixed local-model roles
while the host owns admission, staged context, budgets, continuation, objective
memory, durable wakes, schedules, authenticated webhooks, pause/stop, effects,
approval, checkpointing, recovery and final truth. The release includes the
per-app API composition isolation and packaged prompt registry required by the
installed agent path.

The user accepted the live proof and author/operator experience on 2026-09-10,
selected `C:/Source/OrketExtensions/GoverenedAgentLoop`, and authorized all release
work with minor bumps. Orket Core records checklist-backed acceptance of this
bounded release scope. Historical candidate reports retain their original
versions and dated blocker statements; this record supersedes those open gates.

## Stability Statement

Supported scope is bounded trusted-extension execution with the verified local
Ollama profiles. Agent output is advisory until the host verifies and publishes
it. The subprocess is not hostile-code containment. Single/multiple-model
capability is demonstrated without a comparative quality or production-soak
claim. Profile-memory writes, cross-run memory, unrestricted autonomy and new
cloud-provider routes are outside this release's admitted scope.

## Compatibility Classification

- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`

Core 0.6.0 pins standalone SDK 0.6.0. The reference extension is 0.2.0.
The SDK 0.6.0 nominal core 0.6–0.8 window is explicitly narrowed to verified
core 0.6.0. The starter template also advances to 0.2.0. The existing source
wrapper and hidden `--rock` alias remain deprecated but supported through 0.6.x;
removal is tracked for an explicit 0.7.0 delta. See the
[release contract delta](docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_RELEASE_2026-09-10.md).

## Required Operator or Extension-Author Action

Supply both pinned wheels when upgrading a historical bundling core, then
reinstall SDK last to restore files removed by the old core's uninstall:

```bash
python -m pip install --upgrade orket-0.6.0-py3-none-any.whl orket_extension_sdk-0.6.0-py3-none-any.whl
python -m pip install --force-reinstall --no-deps orket_extension_sdk-0.6.0-py3-none-any.whl
python -m pip check
```

Extract the external 0.2.0 source distribution and run `orket ext validate`
against its directory with `--strict --json` before host intake. Select exact
installed Ollama models. Use `orket runtime --card` for new runtime callers and
`orket.runtime.create_api_app(...)` for API composition, retaining the returned
app; the old module-default API owner is removed by the included B2 change.
Preserve durable records: uncertain effects require observation before retry.

## Proof Record Index

| Surface | Surface Type | Proof Mode | Proof Result | Reason / Observed Path | Evidence |
| --- | --- | --- | --- | --- | --- |
| Installed `orket runtime` | default_runtime_entrypoint | live | success | degraded startup warning retained | [surfaces](benchmarks/results/releases/0.6.0/surfaces.json) |
| `python server.py`, real HTTP health request | api_runtime_entrypoint | live | success | none / primary | [surfaces](benchmarks/results/releases/0.6.0/surfaces.json) |
| Packaged governed-run demo and durable evidence | workflow_path | live | success | none / primary | [surfaces](benchmarks/results/releases/0.6.0/surfaces.json) |
| Installed staged agent and approved/denied effects | workflow_path | live | success | none / primary | [acceptance](benchmarks/results/releases/0.6.0/acceptance.json), [log](benchmarks/results/releases/0.6.0/acceptance.log) |
| Ollama, framed subprocess broker, SQLite, filesystem effects | integration_route | live | success | none / primary | [acceptance](benchmarks/results/releases/0.6.0/acceptance.json) |
| Bundled-to-standalone SDK upgrade | integration_route | live | success | matrix collection, not universal admission | [compatibility](benchmarks/results/releases/0.6.0/compatibility.json) |

## Detailed Proof Records

**Default runtime entrypoint** — `surface_type: default_runtime_entrypoint`,
`proof_mode: live`, `proof_result: success`. The native installed console command
constructs the interactive driver in an isolated workspace, receives `quit`,
and exits zero. This exercises startup beyond help text. Its existing
structural-reconciliation warning is retained: observed path `degraded`, result
`success`. An unsupported extension command separately exits 1 with the expected
fatal diagnostic. Evidence: release `surfaces.json`.

**API runtime entrypoint** — `surface_type: api_runtime_entrypoint`,
`proof_mode: live`, `proof_result: success`, `reason: none`. The source launcher
alone is copied into an isolated directory and run with the installed artifact
interpreter. A real loopback HTTP request returns 200 and `status=ok`. The
health-only process is terminated and reaped. Agent acceptance separately proves
app-lifespan teardown with zero tracked tasks. Evidence: release `surfaces.json`.

**Real workflows and material integrations** — `surface_type: workflow_path`
and `integration_route`, `proof_mode: live`, `proof_result: success`, `reason: none`.
Eleven installed live cases passed with zero skips in 79.090 seconds including
loading: three staged report cases in each model mode, objective memory under
API supervision, approved and denied effects, and fresh-process recovery after
injected exits immediately before/after a real write. After-write recovery
reconciles matching bytes without repeat writes; before-write recovery remains
operator-blocked, and denial retains unsuccessful terminal truth. These expected
outcomes are successful safety proofs, not successful objective completion.

Imports of core, SDK and the external package are asserted to come from the clean
environment's site-packages. Strict validation uses the extracted external sdist.
The host verifier checks partial counts, report contents, completeness and source
references. Ollama server 0.33.3 uses `qwen2.5:7b` and `qwen2.5-coder:7b`; exact
inventory digests, receipt provider version, tokens, calls, repairs, configuration,
durable bindings and final truth are retained. Inventory observations do not
independently attest loaded weight bytes inside provider receipts. The packaged
demo also writes a real evidence bundle for allowed observation,
approval-required write and blocked shell behavior. Evidence: release
`acceptance.json`, `acceptance.log`, and `surfaces.json`.

**Compatibility** — `surface_type: integration_route`, `proof_mode: live`,
`proof_result: success`. Reason: success means truthful matrix collection.
Tagged core v0.5.9 bundles SDK 0.1.0 and has an undeclared `packaging` dependency;
its clean CLI baseline is an environment blocker. Diagnostic validation after
supplying that dependency is separate. Overlaying SDK 0.6.0 creates two namespace
owners and is unsupported even when author validation passes. Core upgrade plus
SDK reinstall restores sole ownership, passes `pip check`, strictly validates
legacy and agent extensions, and runs the installed legacy echo workload.
Evidence: release `compatibility.json`.

## Artifact Identity and Release Binding

The six exact artifacts used by acceptance have SHA-256 hashes in
[artifacts.json](benchmarks/results/releases/0.6.0/artifacts.json). Inspection
compared 867 packaged Python/schema/resource files with source bytes, with zero
mismatches. Core wheel and sdist contain no SDK namespace entries. A clean
SDK-only environment imports SDK 0.6.0 and contains no host package.

Artifacts were built from the uncommitted release candidate based on
`bc3fc138ebce32b21d0a0467165784fb906b8625`; this base is not the release commit.
Final annotated core/SDK tags bind the release commit, and the external tag binds
its separate source commit `e3ec44fe0a63901ba92ea445fa2999a819deee17`.
Publication receipts retain observed tag commits and
artifact hashes without a self-referential commit hash in source. Rebuilds may
change archive metadata; the retained acceptance artifacts are the release bytes.

External source/local destination: `C:/Source/OrketExtensions/GoverenedAgentLoop`.
Its `dist/` holds the authoritative sdist and wheel. Core/SDK artifacts accompany
them in `wheelhouse/0.6.0/`. The old hyphenated-root copy is historical development
source. Local distribution does not claim PyPI or a hosted external repository.

## Reproduction

Routine proof sets `ORKET_DISABLE_SANDBOX=1`. Commands:

```text
python -m pytest -q
python scripts/proof/run_governed_agent_release_surfaces.py --python .tmp/governed-agent-release-0.6.0/venv/Scripts/python.exe
python scripts/proof/run_governed_agent_compatibility.py --core .tmp/governed-agent-release-0.6.0/core-dist/orket-0.6.0-py3-none-any.whl --sdk .tmp/governed-agent-release-0.6.0/sdk-dist/orket_extension_sdk-0.6.0-py3-none-any.whl --extension-root .tmp/governed-agent-release-0.6.0/external-extracted/orket_governed_local_agent-0.2.0
python scripts/proof/collect_governed_agent_release.py --artifacts-root .tmp/governed-agent-release-0.6.0 --extension-root C:/Source/OrketExtensions/GoverenedAgentLoop
python scripts/sdk/check_sdk_tag_version.py --tag sdk-v0.6.0 --repo-root .
python scripts/governance/check_docs_project_hygiene.py
python scripts/governance/check_dependency_direction.py
```

Installed acceptance uses `run_governed_agent_acceptance.py` with that same
interpreter, extracted external root and six repeated `--artifact` arguments;
the exact executed command is retained in its JSON. All rerunnable JSON
producers use stable output paths and diff-ledger history.

## Regression Verification

The first full run reported 4557 passed, 64 skipped and four failures. Three
bundle success tests used a fixture range excluding the new core 0.6.0; the
valid fixture now admits core 0.6.x without changing runtime compatibility
checks. One existing lease-expiry test allowed only 20 ms between the worker's
minimum renewal interval and work completion. It now waits for the injected
renewal event, retaining all durable recovery assertions. No runtime code changed
for these repairs. Both affected modules passed: 32 tests. The first-run log is
retained as `benchmarks/results/releases/0.6.0/regression-initial.log`.
The small growth in the oversized lease-test file is required to remove this
scheduler-dependent proof race; its existing integration classification remains.

The next full run reported 4560 passed, 64 skipped and one failure: a core
manifest test still asserted the valid fixture's old literal range. That
assertion now uses the new range and explicitly checks that 0.6.0 is admitted
and 0.7.0 is refused. All three affected modules pass: 39 tests. The second-run
log is retained as `benchmarks/results/releases/0.6.0/regression-second.log`.

Final canonical full-suite result: **4561 passed, 64 skipped, 2 warnings in 481.02s (0:08:01)**. No failures remain. Evidence: [regression.log](benchmarks/results/releases/0.6.0/regression.log).
After that suite, one extra final blank line was removed from
`orket/application/services/governed_agent_effect_control_support.py`; no
executable behavior changed. Core artifacts were rebuilt and installed proofs
repeated against their final bytes. The retained PowerShell transcripts are
decoded to UTF-8 and trailing whitespace normalized for publication; the earlier failures remain visible. SDK/package lint, dependency direction, release version checks, authority contracts and project hygiene also pass.

## Architecture Checklist and Remaining Drift

AC-01, AC-02, AC-03, AC-05, AC-07, AC-08, AC-09 and AC-10 pass for affected agent
paths under the declared transition rules: application-owned effects/decisions,
explicit inputs, retained replay evidence, negative outcomes and updated
contracts. AC-04 and AC-06 remain partial at existing clock/helper and adapter
classification boundaries. The release does not widen those exceptions;
remediation authority is the active architectural-truth plan and register.

The architecture baseline remains `collection_ok=true`, `release_ready=false`,
with 15 tracked exceptions and 128 broad Ruff findings. Its false-success
command blocker is clear. This does not claim repository-wide architecture
conformance or retire that lane. The transition-aware checklist scopes review
to affected behavior. The fresh-workspace CLI reconciliation warning remains
explicitly degraded proof.

SDK workflow build, lint, test and isolated-import steps were exercised locally;
no hosted Gitea CI execution or package-index publication is claimed.

No production soak, hostile-code containment, new cloud-provider route, future
SDK/core window, or arbitrary crash-window completion is verified. Routine runs
disable sandbox creation; they require no sandbox-resource teardown claim.

## Exact Files Touched

See [FILES_TOUCHED.md](docs/releases/0.6.0/FILES_TOUCHED.md) for the complete release
path inventory. The unrelated untracked `docs/ORKET_GARDENER_INTEGRATION_BRIEF.html`
is excluded from the release.
