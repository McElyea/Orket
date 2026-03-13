# SPC-06 Core Tool Baseline Closeout Requirements

Last updated: 2026-03-13
Status: Archived
Owner: Orket Core
Parent lane: `docs/projects/archive/runtime-stability-green-requirements/02-IMPLEMENTATION-PLAN.md`
Closeout source: `docs/projects/archive/runtime-stability-closeout/IMPLEMENTATION-PLAN.md`

Archive note: Historical requirements packet preserved after direct SPC-06 closeout completed on 2026-03-13.

## 1. Purpose

Define a bounded, truthful closeout target for the removed `core tool baseline + capability profiles per workload` item.

This packet exists because capability-profile enforcement and compatibility governance are shipped, but the active baseline-tool requirements still promise richer per-tool registry metadata and a broader breadth target than the current runtime snapshot proves.

## 2. Scope

In scope:
1. honest baseline breadth target for closeout
2. required per-tool contract metadata for closeout
3. relationship between capability-profile enforcement and baseline-tool closeout
4. exact proof needed for honest closeout

Out of scope:
1. unrelated replay/golden-harness scope
2. unrelated run-summary/run-graph closeout work
3. speculative expansion of every compatibility tool into `core`

## 3. Current Structural Evidence

Current shipped evidence already covers:
1. minimal core-tool snapshot in `core/tools/tool_registry.yaml`
2. tool-registry loading and validation in `orket/runtime/contract_bootstrap.py`
3. capability-profile enforcement in:
   1. `orket/application/workflows/turn_tool_dispatcher_support.py`
   2. `orket/application/workflows/tool_invocation_contracts.py`
4. per-invocation manifest capture including ring, schema version, determinism class, capability profile, and `tool_contract_version`
5. compatibility governance and pilot parity proof in:
   1. `tests/reports/compat_mapping_governance_report.json`
   2. `tests/reports/compat_pilot_parity_report.json`

Current active requirement text still claims additional coverage for:
1. per-tool `input_schema`
2. per-tool `output_schema`
3. per-tool `error_schema`
4. per-tool `side_effect_class`
5. per-tool timeout policy
6. per-tool retry policy
7. a baseline broad enough to support OpenClaw-class workflows through compatibility rings

## 4. Closeout Requirements

### 4.1 Baseline Breadth Must Be Chosen Explicitly

The direct implementation plan must choose one honest breadth target:
1. `minimal baseline closeout`
   - current small core baseline is the closeout target
   - broader OpenClaw-class breadth remains compatibility-layer scope
2. `expanded baseline closeout`
   - additional core tools are required before closeout

Recommended default:
1. choose `minimal baseline closeout` unless there is an explicit request to broaden the core baseline now

Acceptance:
1. the chosen baseline breadth is explicit
2. the non-chosen breadth is excluded from the closeout claim
3. the source requirement text does not imply both at once

### 4.2 Registry Contract Must Be Resolved

The direct implementation plan must decide whether the active tool registry itself remains the canonical source for the richer per-tool contract fields:
1. `schema_version`
2. `input_schema`
3. `output_schema`
4. `error_schema`
5. `side_effect_class`
6. timeout policy
7. retry policy

Required rule:
1. if these fields remain part of the closeout claim, they must be:
   1. represented in canonical runtime contract sources
   2. validated fail-closed at load time
   3. covered by contract tests
2. if the closeout target is smaller, the active spec text must be narrowed in the same closeout change

Acceptance:
1. registry-field expectations are explicit
2. no active spec claims metadata the canonical registry path does not carry

### 4.3 Capability Profiles Must Be Positioned Correctly

The direct implementation plan must make the role of capability profiles explicit:
1. already completed sub-part of SPC-06
2. necessary but insufficient part of SPC-06

Required rule:
1. capability-profile enforcement must not be presented as proof that the whole richer baseline-tool contract is complete unless the metadata contract is also satisfied

Acceptance:
1. capability-profile coverage is credited accurately
2. baseline-tool closeout does not overclaim based on partial enforcement

### 4.4 Observability Contract Must Stay Consistent

The closeout target must keep the registry, tool invocation manifest, and artifact expectations aligned.

Required rule:
1. if richer per-tool metadata becomes canonical, emitted invocation or artifact surfaces must reference or preserve that metadata consistently

Acceptance:
1. registry and invocation artifacts do not silently diverge
2. emitted proof surfaces match the declared baseline-tool contract

## 5. Source-of-Truth Docs To Update On Closeout

Potentially affected docs:
1. `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md`
2. `docs/specs/CORE_TOOL_RINGS_COMPATIBILITY_REQUIREMENTS.md`
3. `docs/specs/TOOL_CONTRACT_TEMPLATE.md`
4. `docs/specs/RUNTIME_INVARIANTS.md`

Minimum required update set:
1. every active spec that names baseline-tool breadth or per-tool required metadata

## 6. Likely Runtime/Test Files To Change

Likely runtime or contract paths:
1. `core/tools/tool_registry.yaml`
2. `orket/runtime/contract_bootstrap.py`
3. `orket/application/workflows/tool_invocation_contracts.py`
4. `orket/application/workflows/turn_artifact_writer.py`
5. `orket/application/workflows/turn_tool_dispatcher.py`
6. `orket/application/workflows/turn_tool_dispatcher_support.py`

Likely proof paths:
1. `tests/runtime/test_contract_bootstrap.py`
2. `tests/application/test_turn_tool_dispatcher_policy_enforcement.py`
3. `tests/application/test_turn_artifact_writer.py`
4. `tests/application/test_compatibility_pilot_parity.py`

## 7. Verification Requirements

Required eventual proof layers:
1. `contract`
   - registry-schema and bootstrap validation tests
2. `integration`
   - dispatcher and artifact emission tests for enforced metadata
3. `end-to-end`
   - only required if the chosen closeout target expands the core baseline breadth beyond the currently shipped minimal set

Required governance proof:
1. `python scripts/governance/check_docs_project_hygiene.py`

## 8. Completion Criteria

This requirements packet is complete when:
1. baseline breadth is narrowed to one explicit target
2. required per-tool metadata is explicit
3. capability-profile coverage is correctly positioned as complete or partial
4. exact source-of-truth docs and likely runtime files are identified
5. the direct implementation plan can begin without reopening registry-contract scope questions

## 9. Next Artifact

After acceptance, create a direct implementation plan for SPC-06 closeout or a source-of-truth narrowing change if the smaller `minimal baseline closeout` target is chosen.
