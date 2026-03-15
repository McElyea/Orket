# Staged Benchmark Candidates

Last updated: 2026-03-15

This directory is the review lane for benchmark artifacts awaiting explicit publication approval.

## Folder Layout
1. `General/`
2. `index.json`
   - Machine-readable catalog for automation and dashboards.

## Current Review Highlight
1. `General/truthful_runtime_packet2_repair_live_proof_qwen2_5_coder_7b_2026-03-15.json` (`STAGE-GEN-007`)
   - Candidate repaired-path proof under the corrected packet-1 contract, including agent_output/main.py as the primary boundary and preserved intended-path provenance values.

## Artifact Directory

| ID | Category | File | Title | What it proves | Key signals |
|---|---|---|---|---|---|
| STAGE-GEN-001 | General | `General/truthful_runtime_packet1_example_2026-03-14.json` | Truthful Runtime Packet-1 Example | Candidate packet-1 example run summary showing provenance, degraded classification, defect reporting, and packet-1 non-conformance on a fallback path. | `truthful_runtime_packet1`, `execution_profile`, `truth_classification`, `defect_families`, `packet1_conformance` |
| STAGE-GEN-002 | General | `General/truthful_runtime_packet1_live_proof_qwen2_5_coder_7b_2026-03-14.json` | Truthful Runtime Packet-1 Live Proof (Qwen2.5 Coder 7B) | Candidate packet-1 live proof for the original March 14 packet-1 contract and live-boundary subset. | `end-to-end_live`, `truthful_runtime_packet1`, `truth_classification`, `packet1_conformance`, `protocol_ledger_finalize` |
| STAGE-GEN-003 | General | `General/truthful_runtime_phase_c_cycle1_live_closure_qwen2_5_coder_7b_2026-03-14.json` | Truthful Runtime Phase C Cycle-1 Live Closure (Qwen2.5 Coder 7B) | Candidate closure packet for the bounded truthful-runtime Phase C live-proof subset frozen on March 14. | `phase_c_cycle1`, `packet1_live_subset`, `cancellation_truth`, `voice_truth_without_avatars`, `carry_forward_packet2` |
| STAGE-GEN-004 | General | `General/truthful_runtime_packet2_repair_live_proof_qwen2_5_coder_7b_2026-03-14.json` | Truthful Runtime Packet-2 Repair-Ledger Live Proof (Qwen2.5 Coder 7B) | Candidate repaired-path proof for the March 14 packet-2 repair-ledger slice before the packet-1 boundary cleanup. | `truthful_runtime_packet2`, `repair_ledger`, `accepted_with_repair`, `packet2_fact`, `corrective_reprompt` |
| STAGE-GEN-005 | General | `General/truthful_runtime_artifact_provenance_live_proof_qwen2_5_coder_7b_2026-03-14.json` | Truthful Runtime Artifact-Provenance Live Proof (Qwen2.5 Coder 7B) | Candidate live proof showing artifact-level provenance for generated requirements, design, and code files plus ledger reconstruction. | `truthful_runtime_artifact_provenance`, `artifact_generation_provenance`, `artifact_provenance_fact`, `write_file_effects`, `live_acceptance` |
| STAGE-GEN-006 | General | `General/truthful_runtime_packet1_boundary_cleanup_live_proof_qwen2_5_coder_7b_2026-03-15.json` | Truthful Runtime Packet-1 Boundary-Cleanup Live Proof (Qwen2.5 Coder 7B) | Candidate live proof for the corrected packet-1 boundary contract, showing agent_output/main.py as the primary boundary on a real fallback-profile run. | `truthful_runtime_packet1`, `primary_output_main_py`, `boundary_cleanup`, `fallback_profile_live`, `artifact_provenance_alignment` |
| STAGE-GEN-007 | General | `General/truthful_runtime_packet2_repair_live_proof_qwen2_5_coder_7b_2026-03-15.json` | Truthful Runtime Packet-2 Repair-Ledger Live Proof (Qwen2.5 Coder 7B, Boundary-Fixed) | Candidate repaired-path proof under the corrected packet-1 contract, including agent_output/main.py as the primary boundary and preserved intended-path provenance values. | `truthful_runtime_packet2`, `repair_ledger`, `primary_output_main_py`, `intended_path_preserved`, `corrective_reprompt` |

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

