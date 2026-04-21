# Staged Benchmark Candidates

Last updated: 2026-04-19

This directory is the review lane for benchmark artifacts awaiting explicit publication approval.

## Folder Layout
1. `General/`
2. `index.json`
   - Machine-readable catalog for automation and dashboards.

## Current Review Highlight
1. `General/prompt_reforger_guide_model_comparison.json` (`STAGE-GEN-017`)
   - Candidate live guide-model comparison checkpoint for the frozen Gemma tool-use corpus, showing degraded Qwen guide generation, blocked LM Studio Gemma guide warmup, and an environment blocker on target-side quality comparison because the portability baseline target did not produce a score report.

## Artifact Directory

| ID | Category | File | Title | What it proves | Governed Claim | Key signals |
|---|---|---|---|---|---|---|
| STAGE-GEN-001 | General | `General/truthful_runtime_packet1_example_2026-03-14.json` | Truthful Runtime Packet-1 Example | Candidate packet-1 example run summary showing provenance, degraded classification, defect reporting, and packet-1 non-conformance on a fallback path. |  | `truthful_runtime_packet1`, `execution_profile`, `truth_classification`, `defect_families`, `packet1_conformance` |
| STAGE-GEN-002 | General | `General/truthful_runtime_packet1_live_proof_qwen2_5_coder_7b_2026-03-14.json` | Truthful Runtime Packet-1 Live Proof (Qwen2.5 Coder 7B) | Candidate packet-1 live proof for the original March 14 packet-1 contract and live-boundary subset. |  | `end-to-end_live`, `truthful_runtime_packet1`, `truth_classification`, `packet1_conformance`, `protocol_ledger_finalize` |
| STAGE-GEN-003 | General | `General/truthful_runtime_phase_c_cycle1_live_closure_qwen2_5_coder_7b_2026-03-14.json` | Truthful Runtime Phase C Cycle-1 Live Closure (Qwen2.5 Coder 7B) | Candidate closure packet for the bounded truthful-runtime Phase C live-proof subset frozen on March 14. |  | `phase_c_cycle1`, `packet1_live_subset`, `cancellation_truth`, `voice_truth_without_avatars`, `carry_forward_packet2` |
| STAGE-GEN-004 | General | `General/truthful_runtime_packet2_repair_live_proof_qwen2_5_coder_7b_2026-03-14.json` | Truthful Runtime Packet-2 Repair-Ledger Live Proof (Qwen2.5 Coder 7B) | Candidate repaired-path proof for the March 14 packet-2 repair-ledger slice before the packet-1 boundary cleanup. |  | `truthful_runtime_packet2`, `repair_ledger`, `accepted_with_repair`, `packet2_fact`, `corrective_reprompt` |
| STAGE-GEN-005 | General | `General/truthful_runtime_artifact_provenance_live_proof_qwen2_5_coder_7b_2026-03-14.json` | Truthful Runtime Artifact-Provenance Live Proof (Qwen2.5 Coder 7B) | Candidate live proof showing artifact-level provenance for generated requirements, design, and code files plus ledger reconstruction. |  | `truthful_runtime_artifact_provenance`, `artifact_generation_provenance`, `artifact_provenance_fact`, `write_file_effects`, `live_acceptance` |
| STAGE-GEN-006 | General | `General/truthful_runtime_packet1_boundary_cleanup_live_proof_qwen2_5_coder_7b_2026-03-15.json` | Truthful Runtime Packet-1 Boundary-Cleanup Live Proof (Qwen2.5 Coder 7B) | Candidate live proof for the corrected packet-1 boundary contract, showing agent_output/main.py as the primary boundary on a real fallback-profile run. |  | `truthful_runtime_packet1`, `primary_output_main_py`, `boundary_cleanup`, `fallback_profile_live`, `artifact_provenance_alignment` |
| STAGE-GEN-007 | General | `General/truthful_runtime_packet2_repair_live_proof_qwen2_5_coder_7b_2026-03-15.json` | Truthful Runtime Packet-2 Repair-Ledger Live Proof (Qwen2.5 Coder 7B, Boundary-Fixed) | Candidate repaired-path proof under the corrected packet-1 contract, including agent_output/main.py as the primary boundary and preserved intended-path provenance values. |  | `truthful_runtime_packet2`, `repair_ledger`, `primary_output_main_py`, `intended_path_preserved`, `corrective_reprompt` |
| STAGE-GEN-008 | General | `General/dg03192026_governed_evidence_bundle_2026-03-19.json` | DG03192026 Governed Evidence Bundle (Runtime Family + S-04) | Candidate governed evidence bundle tying the upgraded extension workload provenance family to the live S-04 code-review probe on a single staging consumer surface. | `non_deterministic_lab_only` on `workload_s04_fixture_v1`<br>surface `workload_answer_key_scoring_verdict_v1`<br>class `workspace` | `governed_evidence`, `extension_workload_provenance_family`, `s04_code_review_probe`, `deterministic_detector_primary`, `staging_governed_claim` |
| STAGE-GEN-009 | General | `General/reforger_service_run_phase0-baseline-run-0001.json` | Prompt Reforger Phase 0 Baseline Generic Service Run | Candidate structural proof of the frozen Phase 0 baseline request envelope on the bounded LocalClaw-style textmystery slice, ending truthfully in an unsupported result with blocked live-runtime bookkeeping. |  | `prompt_reforger`, `generic_service_surface`, `baseline_evaluate`, `unsupported`, `live_proof_blocked` |
| STAGE-GEN-010 | General | `General/reforger_service_run_phase0-adapt-run-0007.json` | Prompt Reforger Phase 0 Adapt Generic Service Run | Candidate structural proof of the bounded generic Prompt Reforger adapt path, including deterministic candidate scoring, a certified_with_limits bundle section, and an external-consumer verdict recorded as service_adopted. |  | `prompt_reforger`, `generic_service_surface`, `bounded_adapt`, `certified_with_limits`, `external_consumer_verdict_source` |
| STAGE-GEN-011 | General | `General/local_model_coding_challenge_report.json` | Local Model Coding Challenge Repeatability Report | Candidate live benchmark report for repeating the challenge_workflow_runtime coding challenge against a local provider-model lane, including turns-to-first-write, turns-to-first-code, repair counts, deepest issue reached, deterministic program hashes, and final blocker families. |  | `local_model_benchmark`, `coding_challenge`, `repeatability`, `turns_to_first_code`, `blocker_family` |
| STAGE-GEN-012 | General | `General/prompt_reforger_gemma_tool_use_inventory.json` | Prompt Reforger Gemma Tool-Use Inventory Checkpoint | Candidate live inventory checkpoint freezing the admitted Gemma proposer and FunctionGemma judge surfaces, explicit alias resolution, and the now-ready primary inventory state including the admitted Ollama alias candidate `functiongemma:latest`. |  | `prompt_reforger`, `gemma_tool_use`, `runtime_inventory`, `alias_resolution`, `primary_judge_ready` |
| STAGE-GEN-013 | General | `General/prompt_reforger_gemma_tool_use_cycle.json` | Prompt Reforger Gemma Tool-Use Cycle Checkpoint | Candidate live bounded Gemma-only cycle comparing baseline and prompt-patch candidates across quality and portability targets after the judge blocker cleared, ending in a truthful pause because 12B clears the frozen corpus while 4B portability remains partial. |  | `prompt_reforger`, `gemma_tool_use`, `cycle`, `judge_blocker_cleared`, `portability_blocker`, `promotion_pause` |
| STAGE-GEN-014 | General | `General/prompt_reforger_gemma_tool_use_judge.json` | Prompt Reforger FunctionGemma Judge Checkpoint | Candidate live advisory judge report showing that the admitted native-tool judge contract now yields usable LM Studio fallback verdicts while the Ollama `functiongemma:latest` path remains all-inconclusive on this machine. |  | `prompt_reforger`, `functiongemma`, `tool_call_judge`, `fallback_path`, `native_tool_contract` |
| STAGE-GEN-015 | General | `General/prompt_reforger_qwen25_coder_7b_probe.json` | Prompt Reforger Qwen2.5-Coder-7B Probe Run | Candidate live cross-family probe on Ollama `qwen2.5-coder:7b` against `challenge_workflow_runtime`, reaching CWR-04 with partial success before a runtime stdout assertion failure. |  | `prompt_reforger`, `cross_family_probe`, `qwen25_coder_7b`, `live_run`, `partial_success` |
| STAGE-GEN-016 | General | `General/prompt_reforger_qwen25_coder_7b_probe_score.json` | Prompt Reforger Qwen2.5-Coder-7B Probe Score | Candidate structural score for the exploratory Ollama `qwen2.5-coder:7b` probe, clearing all 5 frozen bootstrap slices and outperforming the current Gemma 4B portability baseline. |  | `prompt_reforger`, `cross_family_probe`, `qwen25_coder_7b`, `frozen_corpus_clear`, `portability_comparison` |
| STAGE-GEN-017 | General | `General/prompt_reforger_guide_model_comparison.json` | Prompt Reforger Guide-Model Comparison Checkpoint | Candidate live guide-model comparison checkpoint for the frozen Gemma tool-use corpus, showing degraded Qwen guide generation, blocked LM Studio Gemma guide warmup, and an environment blocker on target-side quality comparison because the portability baseline target did not produce a score report. |  | `prompt_reforger`, `guide_model_comparison`, `candidate_generation_quality`, `environment_blocker`, `qwen_generation_partial` |
| STAGE-GEN-018 | General | `General/governed_repo_change_packet_adversarial_benchmark_2026-04-19.json` | Governed Repo Change Packet Adversarial Benchmark | Candidate mixed benchmark for the first governed repo change packet, showing six failure classes where the standalone packet verifier fails closed while the baseline comparator remains success-shaped or ambiguous. | `verdict_deterministic` on `trusted_repo_config_change_v1`<br>surface `trusted_run_witness_report.v1`<br>class `workspace` | `governed_change_packet`, `repo_change_packet`, `adversarial_benchmark`, `standalone_verifier`, `workflow_plus_logs_plus_approvals` |

## Staging Workflow
1. Copy candidate artifact(s) into the correct category folder.
2. Add/update artifact rows in `index.json` with `publish_reviewed=false`.
3. Regenerate this README:
```bash
python scripts/governance/sync_published_index.py --index benchmarks/staging/index.json --readme benchmarks/staging/README.md --write
```
4. Validate before commit:
```bash
python scripts/governance/sync_published_index.py --index benchmarks/staging/index.json --readme benchmarks/staging/README.md --check
```
5. Promote a candidate into `benchmarks/published/` only after explicit user approval.

