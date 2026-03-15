# Truthful Runtime Artifact Provenance Contract

Last updated: 2026-03-15
Status: Active
Owner: Orket Core
Phase authority: `docs/projects/truthful-runtime/ORKET-TRUTHFUL-RUNTIME-HARDENING-PHASE-C-PACKET2-IMPLEMENTATION-PLAN.md`

## 1. Objective

Make generated artifacts attributable at run-summary level so Orket can say which file was produced, by which runtime path, from which authoritative source record, and when.

## 2. Current Bounded Scope

This contract currently covers final surviving workspace artifacts produced by successful `write_file` tool effects on the bounded Phase C packet-2 slice.

Truth source priority:
1. successful protocol `write_file` receipts
2. correlated `tool_call_start` + `tool_call_result(ok=true)` evidence when protocol receipts are absent

Out of scope:
1. runtime-generated verification artifacts that were not created through `write_file`
2. external exports and publication provenance
3. narration-to-effect audit beyond file-generation attribution
4. high-stakes source attribution / evidence-first synthesis
5. spreadsheet, slide, or remote document provider integrations not yet implemented

## 3. Run Summary Surface

Canonical additive summary key:
1. `truthful_runtime_artifact_provenance`

Canonical shape:

```json
{
  "schema_version": "1.0",
  "artifacts": [
    {
      "artifact_path": "agent_output/requirements.txt",
      "artifact_type": "requirements_document",
      "generator": "tool.write_file",
      "generator_version": "unversioned",
      "source_hash": "<sha256>",
      "produced_at": "<iso8601>",
      "truth_classification": "direct",
      "step_id": "REQ-1:1",
      "operation_id": "<operation_id>",
      "issue_id": "REQ-1",
      "role_name": "requirements_analyst",
      "turn_index": 1
    }
  ]
}
```

## 4. Entry Rules

Required fields per entry:
1. `artifact_path`
2. `artifact_type`
3. `generator`
4. `generator_version`
5. `source_hash`
6. `produced_at`
7. `truth_classification`

Optional additive fields:
1. `step_id`
2. `operation_id`
3. `issue_id`
4. `role_name`
5. `turn_index`
6. `tool_call_hash`
7. `receipt_digest`

Field semantics:
1. `artifact_path` is workspace-relative and uses `/` separators.
2. `generator` is the runtime-owned generator identity. Current bounded value: `tool.write_file`.
3. `generator_version` is the authoritative tool contract version when protocol receipts exist, otherwise `unversioned`.
4. `source_hash` is the digest of the authoritative source record used for provenance attribution.
5. `produced_at` is the observed artifact production timestamp recorded at finalize time.
6. `truth_classification` reports the provenance truth class for the artifact record. Current bounded value: `direct`.

## 5. Emission Rules

1. Omit `truthful_runtime_artifact_provenance` when no qualifying generated artifacts are observed.
2. Deduplicate by `artifact_path`; the final surviving successful generation wins.
3. Record a reconstructable ledger fact before `run_finalized`.
4. Replay reconstruction must use the recorded ledger fact rather than reparsing workspace files.

Canonical ledger event:
1. `artifact_provenance_fact`

## 6. Live Evidence Authority

1. Recorder script: `python scripts/governance/record_truthful_runtime_artifact_provenance_live_proof.py`
2. Rerunnable result: `benchmarks/results/governance/truthful_runtime_artifact_provenance_live_proof.json`
3. Staged candidate proof: `benchmarks/staging/General/truthful_runtime_artifact_provenance_live_proof_qwen2_5_coder_7b_2026-03-14.json`
