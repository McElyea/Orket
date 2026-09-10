# Governed Agent Slice 7 Acceptance Reconciliation

Archived on 2026-09-10 after user acceptance and the governed-agent minor-release
closeout. Current release authority: `docs/releases/0.6.0/PROOF_REPORT.md`.
The checkpoint/version/blocker statements below are historical as of their
recorded dates; the accepted closeout supersedes their open release gates.

Date: 2026-09-09
Status: Active acceptance checkpoint; release and user acceptance remain open
Owner: Orket Core
Coordinating authority: `GOVERNED_CONTINUOUS_AGENT_IMPLEMENTATION_PLAN.md`

## Objective

Verify the corrected governed-agent runtime and reconcile its release gates
against installed artifacts without conflating runtime proof with release or
whole-lane acceptance.

## What changed

The acceptance audit found that the earlier two-iteration proof delivered both
fixture batches initially. It also found a non-materialized success reference,
inactive progress counters, incorrect reports reaching effect preparation, and
missing run-control and objective-memory handlers. Those paths now use staged
host context, exact partial-content verification, retained result references,
durable progress decisions, atomic operator controls, and bounded advisory
memory projected from existing accepted iteration records.

The external reference compacts its prior report, counts only newly supplied
sources and optionally queries objective memory. The three fixed cases are
`mixed`, `all-open`, and `empty-first`; both single-model and multi-model paths
use the same fixture, verifier and budgets. Effect proof proposes the final
report at iteration 2, then resumes iteration 3 after approval.

Write resolution now conditionally claims the existing pending approval.
Competing resolvers cannot both execute the mutation. On process loss after
writing but before journaling, exact approval replay can observe matching bytes
and reconcile without writing. Missing/different bytes remain blocked.

Durable semantics and migration boundaries are recorded in
`docs/specs/GOVERNED_AGENT_LOOP_V1.md` and
`docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_ACCEPTANCE_2026-09-09.md`.

## What was verified

Observed path: `primary`. Observed result: `success` for the implementation
acceptance paths. Eleven installed live cases pass in 84.21 seconds including
loading and harness startup. This is not whole-lane release acceptance.

| Proof | Layer / classification | Observed result |
| --- | --- | --- |
| SDK suite, memory authority, SDK tag script and versioning docs | contract + integration | 115 passed |
| Effect authority, competing approvals, objective memory, existing engine approvals | integration, real SQLite/filesystem | 24 passed |
| Pause/stop and resume | integration, API + real child + deterministic provider | Accepted control is consumed before next dispatch; late control refused; pause resumes across app lifespans |
| SDK lint and governed-agent Python lint | structural | pass |
| `check_sdk_tag_version.py --tag sdk-v0.5.0a1 --repo-root .` | structural | pass; this does not create a tag |
| Cache-free core/SDK/external wheel and sdist builds | live package build | pass |
| Fresh three-wheel install and `pip check` | live installed package | pass; no broken requirements |
| Extracted actual external sdist release verifier | contract + installed validation | 1 passed; version/tag alignment passes |
| Installed `orket ext validate <external-sdist-root> --strict --json` | live installed host validation | zero errors, zero warnings, 4 files scanned |
| Core wheel and sdist namespace ownership | structural artifact inspection | zero SDK namespace entries |
| Dependency direction and docs/project hygiene | structural | pass |
| Architectural truth baseline | live CLI/API probes + structural inventory | collection succeeds; release readiness remains false |
| `ORKET_DISABLE_SANDBOX=1 python -m pytest -q` | canonical mixed-layer regression | 4560 passed, 64 skipped, 2 existing warnings; 576.44 seconds |
| Installed live acceptance | end-to-end, real Ollama/API/child/effects | 11 passed; zero skipped; all expected outcomes |
| SDK workflow build/output/smoke commands executed locally | live build + clean SDK-only install | root `dist/` consumed successfully; imported SDK 0.5.0a1; host `orket` absent |
| Final wheel/source Python comparison | structural byte comparison | 862 files match; zero runtime/SDK source mismatches |
| Final authority, effect, run-control and CLI checks | contract + integration | 21 passed in 10.53 seconds |

The concurrent approval CAS change landed after full-suite collection and is
covered by the subsequent 24-test targeted run above. The live memory assertion
was corrected to the existing broker-record status `completed` before the final
11-case rerun. No production change was made to manufacture that status.

| Installed case | Model calls | Repairs | Measured input/output tokens | Expected / observed state |
| --- | ---: | ---: | ---: | --- |
| Single-model mixed | 6 | 0 | 730 / 368 | completed |
| Single-model all-open | 6 | 0 | 702 / 312 | completed |
| Single-model empty-first | 6 | 0 | 671 / 286 | completed |
| Multi-model mixed | 6 | 0 | 730 / 368 | completed |
| Multi-model all-open | 6 | 0 | 702 / 312 | completed |
| Multi-model empty-first | 6 | 0 | 671 / 286 | completed |
| API supervisor with objective memory | 6 | 0 | 774 / 369 | completed |
| Approved effect and resume | 9 | 0 | 1103 / 570 | completed |
| Denied effect | 6 | 0 | 730 / 368 | failed_terminal, no write |
| Process exit before write | 6 | 0 | 730 / 368 | operator_blocked, no write on retry |
| Process exit after write | 9 | 0 | 1103 / 570 | completed, original write retained |

Peak admitted inference concurrency is 1. The provider server reports Ollama
`0.33.3`; receipt provider version is client `0.6.2`. Single-model uses
`qwen2.5:7b`; multi-model uses it for planner/critic and `qwen2.5-coder:7b`
for actor. Inventory digests are respectively
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` and
`dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`.

The final cache-free candidate is retained at
`.tmp/governed-agent-final-20260909-3/`. It contains core `0.5.10`, SDK
`0.5.0a1`, and actual `orket-governed-local-agent` `0.1.0`, built from the
uncommitted working tree based on `bc3fc138`. These version labels do not
identify a new released commit. Exact artifact digests and per-case bindings are
retained by the acceptance producer.

| Artifact | SHA-256 |
| --- | --- |
| Core wheel | `48a5f7e481f162cd9b1c9380d840f4f292c41ce3f537f373808d77e0bfbfa343` |
| Core sdist | `fbe1305c9ada9ef9a9c5efc3a3e15b90f7923fefb803209059e8a0fe928c3ee1` |
| SDK wheel | `6f7dba393a9a5647c449cdede7703a95e0a06024405a364d3b040c35a649da4f` |
| SDK sdist | `e3ef5924693649c3c3401b1ba9dde9e3ed03029b18ab3a3f62e9efcfd1ad6c0c` |
| External reference wheel | `e95c74831e5b5562f50b6ff3ffcc931b66b16db4285c153662323d6b6ac5dc44` |
| External reference sdist | `f3129da39da09afe3f046dd834d3b0a30de46c3b8533b0dc160243d9c529b599` |

Canonical installed proof command:

```powershell
$stage = 'C:/Source/Orket/.tmp/governed-agent-final-20260909-3'
$proofArgs = @('scripts/proof/run_governed_agent_acceptance.py', '--python', "$stage/venv/Scripts/python.exe", '--extension-root', "$stage/external-extracted/orket_governed_local_agent-0.1.0")
Get-ChildItem -Path "$stage/core-dist/*", "$stage/external-dist/*", 'C:/Source/Orket/.tmp/governed-agent-sdk-compatibility-final/dist/*' -File | ForEach-Object { $proofArgs += @('--artifact', $_.FullName) }
python @proofArgs
```

The producer sets `ORKET_DISABLE_SANDBOX=1`, copies only test modules into an
isolated harness, asserts installed core/SDK/reference imports, and records
artifact hashes, versions, dirty source posture, provider inventory, model
receipts, token usage, repair calls, wall time, decision inputs and durable run
references. Stable output:
`benchmarks/results/governed_agent/acceptance.json`. Reruns append diff-ledger
history. This is local acceptance evidence, not a published benchmark.
The successful log is retained at
`.tmp/governed-agent-acceptance/execution-tqqic0fj/pytest.log`; each case's
SQLite evidence remains under that execution's `runs/` directory. The earlier
10-pass/one-assertion-failure run remains in the ledger and in
`execution-6otustn3/`; it is superseded by the complete final run.
The earlier successful `execution-bjs5spc7/` run retains proof for the previous
SDK documentation artifact; the current run includes the corrected metadata.

Meaningful prior failures are retained: source live attempts exposed arithmetic
and duplicate-batch counting errors before compact prior-report handling was
corrected. The earlier canonical suite reported 4552 passed, 62 skipped and
one authority-date mismatch; the mismatch was corrected. A real post-write
process exit exposed approval replay's missing reconciliation path. These
historical failures are not evidence against the corrected candidate, and their
earlier artifacts are not promoted to current proof.

## Built compatibility and upgrade follow-through

`scripts/proof/run_governed_agent_compatibility.py` builds tagged pre-agent
core `v0.5.9` and its historical external template, then probes actual installed
combinations and upgrades the same isolated environment. Stable evidence is
`benchmarks/results/governed_agent/compatibility.json` with diff-ledger history.

The clean historical host bundles SDK `0.1.0` and fails CLI startup because its
declared dependencies omit `packaging`. Supplying that dependency as an explicit
diagnostic step permits strict validation of its own extracted template; this
is a degraded historical path, not a green clean-install claim.
With that diagnostic dependency supplied, the old host and bundled SDK refuse
the new agent manifest with unknown-capability diagnostics, including the required
`agent.iteration.v1` marker. Final matrix evidence is retained under
`.tmp/governed-agent-compatibility/execution-8384alur/`.
The historical tag resolves to commit `eb250d0efa1bbd394e2b337e84d892e361e08e96`.

Installing SDK `0.5.0a1` over that old host produces two SDK namespace owners.
The old CLI then reports successful agent author validation despite lacking the
agent runtime. This combination is explicitly unsupported: validation success
cannot be treated as runtime admission, and the current prerelease's compatibility
window is narrowed in the SDK README, changelog and versioning authority.

Upgrading to the current core and reinstalling the standalone SDK last restores
one SDK owner, passes `pip check`, validates both historical and current
extensions, and runs the historical installed echo workload. Matching governed
agent execution is covered separately by the eleven live cases above. The
producer's success means its matrix observations and current upgrade checks
pass; it does not erase the historical clean-install blocker.

Command:

```powershell
python scripts/proof/run_governed_agent_compatibility.py --core .tmp/governed-agent-final-20260909-3/core-dist/orket-0.5.10-py3-none-any.whl --sdk .tmp/governed-agent-final-20260909-3/sdk-dist/orket_extension_sdk-0.5.0a1-py3-none-any.whl --extension-root .tmp/governed-agent-final-20260909-3/external-extracted/orket_governed_local_agent-0.1.0
```

The SDK compatibility documentation was corrected after the initial artifact
build. Runtime/schema bytes are unchanged. The rebuilt SDK at
`.tmp/governed-agent-sdk-compatibility-final/dist/` includes the corrected
README; the aligned changelog remains in the source release authority. Its
installed live acceptance supersedes the earlier SDK
metadata artifact. The matrix's earlier SDK hash remains valid for its historical
code/protocol observations and is not relabeled as the rebuilt distribution.
Strict project docs lint passes across 19 files; the eight focused SDK-versioning
and authority tests pass. No production runtime code changed in this follow-through.

## What was not verified

1. No hosted CI execution, external hosted repository, package publication,
   core release commit, or core/SDK/external release tag has been produced.
2. Model inventory digests are observed separately from call receipts; receipts
   do not attest which weight bytes were loaded for each request.
3. This proves bounded sequential capability, not comparative model quality,
   production soak, hostile-extension containment, or arbitrary crash recovery.
4. Memory scopes other than the admitted objective projection remain
   explicitly unavailable; no profile-memory mutation is enabled.
5. Whole-lane user acceptance and retirement have not been recorded.

## Release contract draft

The next core commit would use the default patch step `0.5.11` unless a later
accepted whole-project closeout qualifies for a minor release. No version bump
or tag is asserted here. Proposed SDK tag: `sdk-v0.5.0a1`; proposed external
reference tag: `v0.1.0`, each under its own distribution policy.

- Summary: continuous governed wake execution plus corrected staged reporting,
  operator controls, objective memory and recoverable approved file effects.
- Stability: bounded local-model reference capability with host-owned authority;
  broader production and hostile-code guarantees remain outside the proof.
- `compatibility_status`: `breaking` for governed-agent clients that depended on
  undeclared memory writes or the former unmaterialized success reference;
  existing non-agent workloads retain their current contracts.
- `affected_audience`: `all`.
- `migration_requirement`: `required` for affected governed-agent authors.
- Operator/author action: install the matched artifacts; explicitly declare
  memory capabilities; stage batch B via continuation inputs; consume retained
  `agent-result:*` success refs; inspect control decisions and preserve the same
  approval intent on recovery. Do not resume staged runs on an older host.

The core destination is the existing `McElyea/Orket` origin. The external
reference has no selected hosted destination. Release publication and lane
retirement remain blocked by the gates below, rather than being inferred from
these proposed version names.

## Remaining blockers or drift

1. **Ship-risk debt:** the architectural-truth baseline remains
   `release_ready=false`, with 15 existing exceptions. The canonical checker
   passes under the current transition rules; it does not establish the target
   architecture. Broader remediation remains owned by the existing
   architectural-truth lane, not silently waived by this checkpoint.
2. **Self-deception debt:** repository Ruff still reports 128 existing findings
   (`AT-EX-015`). Governed-agent and SDK lint pass, but those scoped results
   cannot be reported as a fully green release envelope.
3. **Exploration-safe debt:** the separate external reference is a local
   package with no selected hosted release destination. SDK `0.5.0a1` is a
   development prerelease. The substantial pre-existing dirty worktree also
   contains architectural-truth work outside this lane; it must not be silently
   included in a lane release commit.
4. Release/version actions follow their separate policies. Final live-proof
   acceptance is owned by the user; whole-lane retirement requires explicit
   acceptance under `docs/CONTRIBUTOR.md`. The lane therefore stays at
   Priority Now position 1 and remains active.

Architecture review: AC-02 through AC-09 pass for the changed boundaries:
structured pure policy inputs, explicit time, application-owned effects,
side-effecting storage classification, verifier-first claims, versioned
decision fields and read-only replay. AC-01 is partial under the existing
dependency-policy exceptions. AC-10 is satisfied for the changed semantics;
the broader authority-snapshot debt remains `AT-EX-016`.

## Exact files touched in this acceptance reconciliation

Runtime and SDK:

- `orket/adapters/storage/async_repositories.py`
- `orket/adapters/storage/async_governed_agent_run_control_repository.py`
- `orket/adapters/storage/governed_agent_decision_store.py`
- `orket/adapters/storage/governed_agent_repository_support.py`
- `orket/application/services/governed_agent_api_composition.py`
- `orket/application/services/governed_agent_broker_service.py`
- `orket/application/services/governed_agent_context_plan.py`
- `orket/application/services/governed_agent_effect_control_service.py`
- `orket/application/services/governed_agent_effect_records.py`
- `orket/application/services/governed_agent_effect_resume_service.py`
- `orket/application/services/governed_agent_effect_service.py`
- `orket/application/services/governed_agent_execution_composition.py`
- `orket/application/services/governed_agent_fixture.py`
- `orket/application/services/governed_agent_inspection_service.py`
- `orket/application/services/governed_agent_iteration_policy.py`
- `orket/application/services/governed_agent_loop_service.py`
- `orket/application/services/governed_agent_memory_service.py`
- `orket/application/services/governed_agent_operator_service.py`
- `orket/application/services/governed_agent_ports.py`
- `orket/application/services/governed_agent_progress_policy.py`
- `orket/application/services/governed_agent_run_control_service.py`
- `orket/application/services/governed_agent_runtime.py`
- `orket/application/services/governed_agent_request_builder.py`
- `orket/application/services/governed_agent_terminal_service.py`
- `orket/application/services/governed_agent_wake_dispatcher.py`
- `orket/core/domain/governed_agent_continuation.py`
- `orket/interfaces/governed_agent_cli.py`
- `orket/interfaces/routers/governed_agents.py`
- `orket_extension_sdk/agent_fixtures.py`
- `orket_extension_sdk/agent_testing.py`
- `orket_extension_sdk/agent_validation.py`
- `orket_extension_sdk/CHANGELOG.md`

Tests and proof automation:

- `.gitea/workflows/sdk-package-release.yml`
- `scripts/proof/run_governed_agent_acceptance.py`
- `scripts/proof/run_governed_agent_compatibility.py`
- `tests/e2e/governed_agent_process_worker.py`
- `tests/e2e/test_governed_agent_ollama.py`
- `tests/e2e/test_governed_agent_effect_ollama.py`
- `tests/e2e/test_governed_agent_supervisor_ollama.py`
- `tests/e2e/test_governed_agent_process_recovery.py`
- `tests/integration/test_governed_agent_acceptance_failures.py`
- `tests/integration/test_governed_agent_continuation_context.py`
- `tests/integration/test_governed_agent_effect_service.py`
- `tests/integration/test_governed_agent_memory_authority.py`
- `tests/interfaces/test_governed_agent_cli.py`
- `tests/interfaces/test_governed_agent_run_controls.py`
- `tests/runtime/governed_agent_test_support.py`
- `tests/runtime/test_governed_agent_loop.py`
- `tests/sdk/test_governed_agent_schema.py`

Documentation and reference:

- `CURRENT_AUTHORITY.md`
- `docs/ROADMAP.md`
- `docs/RUNBOOK.md`
- `docs/specs/GOVERNED_AGENT_LOOP_V1.md`
- `docs/requirements/sdk/VERSIONING.md`
- `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_ACCEPTANCE_2026-09-09.md`
- `docs/projects/architectural-truth/architectural_truth_baseline.json` (regenerated evidence only)
- `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/README.md`
- `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_0_CONFORMANCE_MATRIX.md`
- `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_CONTINUOUS_AGENT_IMPLEMENTATION_PLAN.md`
- `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_AGENT_CORE_RUNTIME_PLAN.md`
- `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_AGENT_SDK_ENABLEMENT_PLAN.md`
- `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/GOVERNED_LOCAL_AGENT_EXTENSION_PLAN.md`
- `docs/projects/archive/governed-agent-loop/GAL09102026-IMPLEMENTATION-CLOSEOUT/SLICE_7_ACCEPTANCE_PROOF_2026-09-09.md`
- `docs/templates/governed_agent_external/governed_agent.py`
- `docs/templates/governed_agent_external/extension.yaml`
- `orket_extension_sdk/README.md`
- `C:/Source/Orket-Extensions/GovernedLocalAgent/orket_governed_local_agent/workload.py`
- `C:/Source/Orket-Extensions/GovernedLocalAgent/extension.yaml`
- `C:/Source/Orket-Extensions/GovernedLocalAgent/README.md`
- `C:/Source/Orket-Extensions/GovernedLocalAgent/MANIFEST.in`
- `C:/Source/Orket-Extensions/GovernedLocalAgent/scripts/release.py`

Ignored build stages, local SQLite/log evidence and stable local producer JSON
are retained separately. Pre-existing modifications outside this list have been
preserved; the full dirty worktree is not claimed as this reconciliation's diff.
