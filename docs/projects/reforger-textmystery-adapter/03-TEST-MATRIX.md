# Reforger v0 - Test Matrix

Date: 2026-02-28  
Status: planned  
Project: `docs/projects/reforger-textmystery-adapter/`

| Requirement | Test Name | Artifact | Pass Condition |
|---|---|---|---|
| Canonical serialization byte stability | `test_canonical_json_bytes_stable` | `canonical_blob.json` | Byte-for-byte identical across reruns |
| Canonical digest rule | `test_canonical_digest_matches_json_bytes_hash` | `canonical_digest.txt` | Digest equals `sha256(canonical_json_bytes)` |
| Deterministic tie-break order | `test_candidate_selection_tie_break_locked` | `candidates.jsonl`, `final_score_report.json` | Winner matches frozen priority order |
| Stable issue codes | `test_issue_codes_exact_catalog` | `validation_report.normalize.json` | Codes only from frozen catalog |
| Route ambiguity fail | `test_route_ambiguous_returns_code` | `route_plan.json` | Non-zero + `ROUTE_AMBIGUOUS` |
| Route missing fail | `test_route_not_found_returns_code` | `route_plan.json` | Non-zero + `ROUTE_NOT_FOUND` |
| Inspect mode-less behavior | `test_inspect_without_mode_suite_ready_null` | `route_plan.json` | `suite_ready == null` |
| Inspect with mode readiness | `test_inspect_truth_only_sets_suite_ready` | `route_plan.json` | `suite_ready` is bool, no scoring run |
| Patch surface data-driven enforcement | `test_patch_surface_loaded_from_route_metadata` | `route_plan.json` or route metadata | Validator uses metadata-defined surface |
| Patch outside surface rejection | `test_patch_outside_surface_rejected` | `candidates/*` / validation report | `PATCH_OUT_OF_SURFACE` |
| Patch schema-break rejection | `test_patch_schema_break_rejected` | validation report | `PATCH_SCHEMA_BREAK` |
| Patch ref-break rejection | `test_patch_ref_break_rejected` | validation report | `PATCH_REF_BREAK` |
| Schema/reference integrity | `test_invalid_reference_detected` | `validation_report.normalize.json` | Deterministic `REF_INVALID` or `SCHEMA_INVALID` |
| Materialize atomicity on failure | `test_materialize_atomic_no_partial_outputs` | `validation_report.materialize.json`, output dir | No partial files written |
| Round-trip idempotence | `test_normalize_materialize_normalize_digest_idempotent` | `canonical_digest.txt` | Digest unchanged |
| Deterministic run bundle digests | `test_run_artifact_digests_reproducible` | `bundle_digests.json` | Identical across reruns |
| Deterministic run id | `test_run_id_deterministic_from_locked_inputs` | `run_meta.json` | Same config => same run id |
| Scenario pack strict loader | `test_scenario_pack_requires_fields` | `scenario_report.json` | Missing fields fail deterministically |
| Scenario mode mismatch fail | `test_scenario_mode_mismatch_fails` | validation report | Deterministic mode mismatch error |
| truth_only baseline pass | `test_truth_only_fixture_baseline_passes` | `scenario_report.json` | No hard violations |
| truth_only no-regression gate | `test_reforge_does_not_regress_truth_constraints` | `final_score_report.json` | Candidate selection never worsens hard constraints |
| Artifact schema versions present | `test_artifact_schema_versions_emitted` | all required artifacts | Correct version fields emitted |
| Operator integration non-authority | `test_operator_proposals_require_core_validation` | `operator_proposed_patches.json`, candidates | Operator cannot bypass core checks |
| Operator inspect diagnostics rendering path | `test_operator_renders_suite_requirements` | `operator_session.json` | Missing fields surfaced deterministically |

## Notes

- Test names are normative; exact module filenames may vary.
- Every test must be deterministic and rerunnable in CI.
- Failures must include machine-readable diagnostics and frozen issue codes.
