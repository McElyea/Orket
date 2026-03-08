# Controller Workload Operator Runbook

Last updated: 2026-03-08
Status: Active
Owner: Orket Core

Runtime contract authority:
`docs/specs/CONTROLLER_WORKLOAD_V1.md`

Observability contract authority:
`docs/specs/CONTROLLER_OBSERVABILITY_V1.md`

## 1. Purpose

Help operators classify controller-workload runs and triage failures without reading runtime source code.

This runbook is scoped to controller workload behavior executed through:
1. `ExtensionManager.run_workload(workload_id="controller_workload_v1", ...)`
2. sequential SDK child dispatch via controller dispatcher

## 2. Path Classification

Use the following path labels for incident handling and evidence reports.

| Path | Operational Meaning | Current Runtime Signal |
|---|---|---|
| `primary` | Controller run completed successfully with no denials or child failures. | `controller_summary.status = "success"` and `error_code = null` |
| `fallback` | Controller run succeeded after clamp/normalization (for example requested caps reduced by runtime policy). | `controller_summary.status = "success"` and requested vs enforced caps differ |
| `degraded` | Controller started, at least one child executed, then run failed and remaining accepted-envelope siblings are `not_attempted`. | `controller_summary.status = "failed"` and at least one child `status = "success"` |
| `blocked` | Controller run was denied before any child success because of contract/guard denial or early validation failure. | `controller_summary.status = "blocked"` and no child `status = "success"` |

Notes:
1. The current run summary status vocabulary is `success|failed|blocked`.
2. `primary|fallback|degraded|blocked` are operator evidence labels derived from summary/provenance, not a replacement for runtime contract fields.

## 3. First-Triage Decision Table

| Error code | Typical path class | First triage action |
|---|---|---|
| `controller.envelope_invalid` | `blocked` | Validate input envelope shape and required fields (`controller_workload_id`, `parent_depth`, `ancestry`, `children`). |
| `controller.child_timeout_invalid` | `blocked` | Fix timeout inputs (`timeout_seconds` and requested cap timeout must be finite and > 0). |
| `controller.max_fanout_exceeded` | `blocked` | Reduce declared child count or raise runtime cap through approved policy settings. |
| `controller.max_depth_exceeded` | `blocked` | Reduce recursion depth or increase max depth via approved policy settings. |
| `controller.recursion_denied` | `blocked` | Remove direct self-reentry (`A -> A`) from child declarations. |
| `controller.cycle_denied` | `blocked` | Remove ancestry cycle (`A -> ... -> A`) in controller-child graph. |
| `controller.disabled_by_policy` | `blocked` | Check rollout controls (`ORKET_CONTROLLER_ENABLED`, `ORKET_CONTROLLER_ALLOWED_DEPARTMENTS`). |
| `controller.child_sdk_required` | `blocked` | Ensure child workload resolves to SDK v0 contract style (`sdk_v0`). |
| `controller.child_execution_failed` | `degraded` or `blocked` | Inspect first failing child summary and child provenance; resolve child runtime failure cause. |

## 4. Observed Runtime Phases

Run classification should identify the failing phase using one of:
1. `envelope_validation`
2. `cap_guard`
3. `recursion_cycle_guard`
4. `child_guard`
5. `child_execution`
6. `controller_summary_finalize`

When reporting failures, capture:
1. path class (`primary|fallback|degraded|blocked`)
2. runtime result (`success|failed|blocked`)
3. exact failing phase
4. exact stable error code

## 5. Provenance and Observability Surfaces

Current authoritative evidence surfaces:
1. top-level workload output:
   - `output.controller_summary`
   - `output.controller_summary_canonical`
2. per-child artifact refs in `controller_summary.child_results[*].artifact_refs`
3. extension run-level provenance path from child run outputs

Current runtime truth:
1. deterministic controller observability batch emission is wired through `orket/extensions/controller_observability.py`.
2. if canonicalization/schema validation/emission preparation fails, run fails closed with `controller.observability_emit_failed` and emits zero events.
3. operator evidence should use both `controller_summary` and emitted observability events, with provenance artifacts for deeper child-level debugging.

Expected observability contract shape once emitted (per `CONTROLLER_OBSERVABILITY_V1.md`):
1. one `controller_run` event first
2. `controller_child` events in accepted child index order
3. zero child events for `controller.envelope_invalid` and `controller.max_fanout_exceeded`

## 6. Path-by-Path Evidence Expectations

### 6.1 `primary`
1. `controller_summary.status = "success"`
2. `controller_summary.error_code = null`
3. all child results are `success`
4. child artifact refs present for executed children

### 6.2 `fallback`
1. same as `primary`, plus requested vs enforced cap clamp evidence
2. clamp is expected and not by itself an incident

### 6.3 `degraded`
1. first failing child has `status = "failed"` with non-null `normalized_error`
2. later siblings in the accepted envelope are `status = "not_attempted"`
3. controller run `error_code` is non-null

### 6.4 `blocked`
1. no successful child execution in the run
2. controller run `error_code` is one of stable denial/validation codes
3. early validation denials may have zero child results

## 7. Fast Triage Checklist

1. Confirm workload path used `ExtensionManager.run_workload`.
2. Record `controller_summary.status`, `error_code`, and child status sequence.
3. Classify path (`primary|fallback|degraded|blocked`).
4. Map stable error code to first action via the triage table.
5. If `degraded` or `blocked`, capture exact failing phase and exact error code in evidence.
6. Escalate only after reproducing with the same canonical input payload where possible.
