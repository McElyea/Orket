# Tech Debt Recurring Maintenance Checklist

Last updated: 2026-03-07  
Status: Active (living document)  
Owner: Orket Core

## Purpose

Provide one standing checklist for every techdebt/code-review/maintenance cycle so project lanes can close cleanly while recurring validation work remains explicit and auditable.

## Policy

1. This checklist is intentionally permanent and lives under `docs/projects/techdebt/`.
2. Project implementation plans remain finite and closable; recurring freshness work belongs here.
3. Every cycle must produce machine-readable evidence artifacts.
4. Narrative-only sign-off is not sufficient for closure of any checklist item.
5. Folder-level closure/archiving semantics are defined in:
   - `docs/projects/techdebt/README.md`

## Cycle Triggers

Run this checklist when any of the following occurs:

1. A scheduled techdebt cycle starts.
2. A release candidate is prepared.
3. A major runtime-policy change lands.
4. A provider/model/template change lands.
5. A gate/workflow definition changes (`.gitea/workflows/*`, gate scripts, checklist schema).
6. Post-incident, postmortem, or external critic findings require verification.

## Required Evidence Contract (Per Cycle)

For each executed section, capture:

1. `commands.txt` with exact commands.
2. `environment.json` with OS, Python version, package mode, key env toggles.
3. `result.json` with pass/fail and named assertions.
4. Optional supporting logs:
   1. `stdout.log`
   2. `stderr.log`
   3. targeted runtime logs

Recommended cycle root:
1. `benchmarks/results/techdebt/recurring/<cycle_id>/`

## Section A: Baseline Gate Freshness (Required Every Cycle)

Objective:
1. Ensure TD03052026 readiness gates are still enforced and evidence-linked.

Commands:
1. `python scripts/governance/check_td03052026_gate_audit.py --require-ready --out benchmarks/results/techdebt/td03052026/readiness_checklist.json`
2. `python scripts/governance/check_docs_project_hygiene.py`

Automation helper for Section A + Section D evidence:
1. `python scripts/techdebt/run_recurring_maintenance_cycle.py --cycle-id <cycle_id> --strict`
   - This runner records `commands.txt`, `environment.json`, `result.json`, `stdout.log`, `stderr.log`, and the summarized cycle report.
   - Conditional Sections B and C remain separately triggered by the checklist rules.

Pass criteria:
1. Gate audit status is `PASS`.
2. `G1`-`G7` remain green unless an active, tracked remediation lane exists.
3. Docs hygiene check passes.

## Section B: Protocol Enforce-Phase Freshness (Conditional)

Run when:
1. release candidate or major runtime-policy/protocol behavior change.

Objective:
1. Revalidate staged/replayed enforce-window readiness.

Commands:
1. `python scripts/protocol/run_protocol_enforce_window_capture.py --window-id <window_id_a> --window-date <yyyy-mm-dd> --workspace-root <workspace_root> --run-id <run_id> --retry-spike-status <pass|fail|unknown> --approver <approver> --out-root <window_a_out_root> --strict`
2. `python scripts/protocol/run_protocol_enforce_window_capture.py --window-id <window_id_b> --window-date <yyyy-mm-dd> --workspace-root <workspace_root> --run-id <run_id> --retry-spike-status <pass|fail|unknown> --approver <approver> --out-root <window_b_out_root> --strict`
3. `python scripts/protocol/check_protocol_enforce_cutover_readiness.py --manifest <window_a_manifest> --manifest <window_b_manifest> --min-pass-windows 2 --out <cutover_readiness_out_json> --strict`

Pass criteria:
1. Both window capture manifests are `PASS`.
2. Cutover readiness output is `ready=true`.

## Section C: Local Prompting Promotion Readiness (Conditional)

Run when:
1. provider/model/template/runtime-policy changes affect local prompting behavior, or during release-candidate validation.

Objective:
1. Revalidate promotion thresholds and template/drift gates for active provider profiles.

Commands:
1. `python scripts/protocol/check_local_prompting_promotion_readiness.py --profile-root <profile_root_1> --profile-root <profile_root_2> --drift-report benchmarks/results/protocol/local_prompting/live_verification/drift/profile_delta_report.json --template-audit-root benchmarks/results/protocol/local_prompting/live_verification/template_audit --out benchmarks/results/protocol/local_prompting/promotion_decision/local_prompting_promotion_readiness.json --strict`

Pass criteria:
1. Readiness output is `ready=true`.
2. All listed profiles are `ready=true`.
3. Drift gate remains unchanged unless an intentional upgrade campaign is active.

## Section D: Curation and Anti-Bloat (Required Every Cycle)

Objective:
1. Keep this checklist useful and bounded.

Rules:
1. Remove items that no longer map to an active risk boundary.
2. Merge duplicate checks that validate the same failure class.
3. Any new recurring item must include:
   1. trigger condition
   2. command(s)
   3. pass criteria
   4. retirement criterion
4. Archive superseded recurring items into a dated appendix or PR notes instead of expanding the core checklist indefinitely.

## Handoff Rules

1. If any required section is red, open or update a scoped remediation lane in roadmap with explicit closure criteria.
2. Do not mark a project lane as active solely for recurring freshness checks; recurring checks remain in this checklist.
3. Reference this checklist from runbook/process docs rather than duplicating command blocks across project plans.
4. If a cycle implementation closes during this maintenance pass, archive its cycle docs per:
   - `docs/projects/techdebt/README.md`
