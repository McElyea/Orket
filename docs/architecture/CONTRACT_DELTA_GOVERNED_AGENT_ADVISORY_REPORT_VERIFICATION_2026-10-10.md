# Contract Delta: Governed agent advisory-report verification

## Summary
- Change title: Workload-selected advisory-report completion verification
- Owner: Orket Core (proposed by an external contributor; acceptance pending)
- Date: 2026-10-10
- Affected contract(s): `docs/specs/GOVERNED_AGENT_LOOP_V1.md` (completion verifier selection, deterministic fixture provider, submit output)

## Delta
- Current behavior: every governed agent submission is verified by the ticket-report fixture verifier v2. A workload whose objective is not one of the three ticket fixture objectives cannot reach `completion_satisfied` and fails with `E_AGENT_FIXTURE_OBJECTIVE_UNSUPPORTED` or remains unsatisfied. `orket agent submit --json` reports only the accepted result's digest.
- Proposed behavior:
  1. The host additionally supports `agent_advisory_report_verification.v1`. A workload that requires it is verified by `AdvisoryReportVerifier` v1: one returned, effect-free result whose advisory proposal is exactly `{report, source_refs}` with sources drawn from the request's authoritative context. All other workloads keep the ticket-report verifier unchanged.
  2. The deterministic fixture provider answers the advisory-report response schema with a fixed report citing every supplied source.
  3. A successful submission's JSON output adds `authoritative_result` with the `ref`, `result_digest`, and `advisory_proposal` of the result its final truth names. The field is `null` when the run is not successful.
- Why this break is required now: report-only workloads, such as repository audits requested by gardener's `command` harness (McElyea/Orket#1), have no completion path on the governed agent loop.

## Migration Plan
1. Compatibility window: additive. Existing manifests, requests, verifier behavior, and stored state are unchanged; the new submit-output field is additive.
2. Migration steps: none. A workload opts in by adding the feature to `agent.required_host_features`. Hosts that predate this change refuse such a workload with `E_AGENT_HOST_FEATURE_UNSUPPORTED` before child startup.
3. Validation gates: `tests/application/test_governed_agent_advisory_report.py` (unit), `tests/integration/test_gardener_harness_example.py` (integration, real `orket agent submit` with the deterministic fixture), and the existing governed-agent and SDK suites. A live Ollama run is recorded in the pull request.

## Rollback Plan
1. Rollback trigger: the advisory-report verifier admits a result it should refuse, or the feature selection changes a non-opted-in workload's verifier.
2. Rollback steps: remove the feature from `SUPPORTED_GOVERNED_AGENT_HOST_FEATURES` and the verifier selection; opted-in workloads are then refused at admission.
3. Data/state recovery notes: none. Final truth already published by the advisory-report verifier remains as recorded.

## Versioning Decision
- Version bump type: minor (additive host feature).
- Effective version/date: next core release after acceptance.
- Downstream impact: none for existing workloads; the SDK is unchanged.
