# Denial Path v1 Verification Report

**Run identity**
- run_id: `denial-path-v1-20260426t200916z`
- session_id: `None`
- namespace: `denial_path_v1_20260426T200916Z`
- submitted_at: `2026-04-26T20:09:29.397125+00:00`
- completed_at: `2026-04-26T20:09:30.774709+00:00`

**Model and provider**
- provider name: `ollama`
- model name: `qwen2.5-coder:7b`
- endpoint used: `http://127.0.0.1:11434`
- graph identity: outward pipeline evidence graph generated directly from the outward `run_id`, not a legacy ProductFlow or `runs/<session_id>/` graph.

**Proof checklist**
| Item | Expected result | Status |
|---|---|---|
| live model invocation | success | pass |
| submitted_request proves no synthetic governed_tool_call shortcut | true | pass |
| model response captured or safely redacted | true | pass |
| proposal extraction captured | true | pass |
| proposal derived from model output | true | pass |
| proposal before effect | true | pass |
| approval before effect | true or not applicable for policy rejection | pass |
| file absent before approval | true | pass |
| final terminal status | completed or equivalent success | pass |
| run events captured | true | pass |
| execution graph captured | true | pass |
| full ledger verification | valid | pass |
| partial ledger verification | partial_valid | pass |
| tampered ledger verification | invalid | pass |
| no raw secrets found | true | pass |
| manifest hashes verified | true | pass |
| proposal_denied event | present | pass |
| approval_decision reflects deny reason | decision=deny with reason | pass |
| denial completed cleanly | run_status_after.status=completed | pass |
| denied target absent | denied_artifact_exists=False | pass |

**Commands run**
1. `C:\Python314\python.exe scripts/providers/check_model_provider_preflight.py --provider ollama --model-id qwen2.5-coder:7b --timeout 20` -> returncode=0; stdout=WARMUP_STATUS=OK source=ollama_list resolution_mode=requested resolved_model=qwen2.5-coder:7b
WARMUP_AVAILABLE_MODELS=Command-R:35B,Mistral-Nemo:12B,deepseek-coder:33B,deepseek-r1:32b,functiongemma:latest,gemma3:27b,gemma3:latest,gpt-oss:120b,gpt-oss:20b,llama3.1:8b,nomic-embed-text:latest,qwen2.5-coder:14b,qwen2.5-coder:7b,qwen2.5:14b,qwen2.5:7b,qwen3-coder:latest
provider=ollama canonical=ollama base_url=http://127.0.0.1:11434 model_id=qwen2.5-coder:7b
RESOLVED_MODEL_ID=qwen2.5-coder:7b
RESOLUTION_MODE=requested
PREFLIGHT=PASS; stderr=
2. `C:\Python314\python.exe server.py --host 127.0.0.1 --port 60770 with ORKET_API_KEY=[REDACTED] ORKET_DISABLE_SANDBOX=1` -> started pid=39116
3. `HTTP GET http://127.0.0.1:60770/health` -> HTTP 200; X-Orket-Version=
4. `HTTP GET http://127.0.0.1:60770/v1/version headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31
5. `HTTP POST http://127.0.0.1:60770/v1/runs headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=submitted_run.json
6. `HTTP GET http://127.0.0.1:60770/v1/runs/denial-path-v1-20260426t200916z headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31
7. `HTTP GET http://127.0.0.1:60770/v1/approvals?status=pending&session_id=denial-path-v1-20260426t200916z headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31
8. `HTTP POST http://127.0.0.1:60770/v1/approvals/proposal%3Adenial-path-v1-20260426t200916z%3Awrite_file%3A0001/deny headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=approval_decision_1.json
9. `HTTP GET http://127.0.0.1:60770/v1/runs/denial-path-v1-20260426t200916z headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31
10. `HTTP GET http://127.0.0.1:60770/v1/runs/denial-path-v1-20260426t200916z/ledger headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=ledger_full.json
11. `HTTP GET http://127.0.0.1:60770/v1/runs/denial-path-v1-20260426t200916z/ledger?types=proposals%2Cdecisions headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=ledger_partial_decisions.json
12. `HTTP GET http://127.0.0.1:60770/v1/runs/denial-path-v1-20260426t200916z/events headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=run_events.json
13. `HTTP GET http://127.0.0.1:60770/v1/runs/denial-path-v1-20260426t200916z/summary headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=run_summary.json
14. `C:\Python314\python.exe scripts/observability/emit_run_evidence_graph.py --run-id denial-path-v1-20260426t200916z --workspace-root C:\Source\Orket --outward-pipeline-db C:\Source\Orket\.tmp\denial_path_v1_20260426T200916Z.sqlite3` -> returncode=0; stdout={
  "event_count": 9,
  "graph_kind": "outward_pipeline",
  "graph_result": "complete",
  "json_path": "C:/Source/Orket/workspace/denial_path_v1_20260426T200916Z/runs/denial-path-v1-20260426t200916z/run_evidence_graph.json",
  "ledger_hash": "d783edd04d10845cb6da980567e9dd6209e25978cbda1aa7c83e7de117c4447c",
  "ok": true,
  "proposal_count": 1,
  "requested_run_id": "denial-path-v1-20260426t200916z",
  "run_id": "denial-path-v1-20260426t200916z",
  "schema_version": "1.0",
  "selected_views": [
    "full_lineage",
    "failure_path",
    "resource_authority_path",
    "closure_path"
  ],
  "session_id": null,
  "svg_path": "C:/Source/Orket/workspace/denial_path_v1_20260426T200916Z/runs/denial-path-v1-20260426t200916z/run_evidence_graph.svg",
  "tool_invocation_count": 0
}; stderr=
15. `Stop Orket server pid=39116` -> exitcode=1
16. `C:\Python314\python.exe -m orket.interfaces.orket_bundle_cli ledger verify C:\Source\Orket\artifacts\denial_path_v1\20260426T200916Z\ledger_full.json` -> returncode=0; stdout={
  "schema_version": "ledger_export.v1",
  "result": "valid",
  "export_scope": "all",
  "run_id": "denial-path-v1-20260426t200916z",
  "ledger_hash": "d783edd04d10845cb6da980567e9dd6209e25978cbda1aa7c83e7de117c4447c",
  "event_count": 9,
  "checked_event_count": 9,
  "errors": []
}; stderr=
17. `C:\Python314\python.exe -m orket.interfaces.orket_bundle_cli ledger verify C:\Source\Orket\artifacts\denial_path_v1\20260426T200916Z\ledger_partial_decisions.json` -> returncode=0; stdout={
  "schema_version": "ledger_export.v1",
  "result": "partial_valid",
  "export_scope": "partial_view",
  "run_id": "denial-path-v1-20260426t200916z",
  "ledger_hash": "d783edd04d10845cb6da980567e9dd6209e25978cbda1aa7c83e7de117c4447c",
  "event_count": 9,
  "checked_event_count": 3,
  "errors": []
}; stderr=
18. `C:\Python314\python.exe -m orket.interfaces.orket_bundle_cli ledger verify C:\Source\Orket\artifacts\denial_path_v1\20260426T200916Z\ledger_tampered.json` -> returncode=1; stdout={
  "schema_version": "ledger_export.v1",
  "result": "invalid",
  "export_scope": "all",
  "run_id": "denial-path-v1-20260426t200916z",
  "ledger_hash": "d783edd04d10845cb6da980567e9dd6209e25978cbda1aa7c83e7de117c4447c",
  "event_count": 9,
  "checked_event_count": 9,
  "errors": [
    "event_hash mismatch at position 1",
    "chain_hash mismatch at position 1",
    "previous_chain_hash mismatch at position 2"
  ]
}; stderr=


**Artifact index**
- `README.md` - `a9b01d26f24f805ccbffa658eddf6f8ae19fc852c6bebe6ffcd4947e05a86dd3`
- `approval_decision.json` - `6f8784fe26858e253ef51d642e1b0b0df763eeb4b84227c7c3ffe3b0b3d8ca0b`
- `approval_decision_1.json` - `6f8784fe26858e253ef51d642e1b0b0df763eeb4b84227c7c3ffe3b0b3d8ca0b`
- `approval_pending.json` - `b46357a6af524f97a6336b2fc560eff59e719206ad163cf4760c0109357f63ae`
- `approval_pending_1.json` - `f5d3c294b5112e0d1ff87ffed4f4ca61b7e978516614a5a243cf827c57c0891c`
- `command_log.txt` - `c5ae3adbfbc875228bd34a612f7ad0036a27523880cd31e2e8ea3074e4278a47`
- `environment.json` - `32c6c9ed61b7e1914a308ca1983a1a9570a9e9b15a117ecdecfb2a8e741e60d1`
- `execution_graph.json` - `0ce7ba3c64c2adac8fc97a2d83a3d1a7b7fad808bafc73fbbb5c09c6f7641d1e`
- `execution_graph.svg` - `a32d1c1988572a269159cf6eab5b03205943ea979f22eff707e52c37b44c5097`
- `ledger_full.json` - `4eee65ecd7de7f694176f913456a0941181213bf1b4270a4f90465e3d47249f8`
- `ledger_partial_decisions.json` - `31f559b74a6736459c5c0de24493e976146df952f9d38e127ae38b7e7d1335af`
- `ledger_tampered.json` - `2b04c460bb9d9b851bbdb27a2b87576d63afd2eaa290f4a8b8e66ec67e04e387`
- `ledger_verify_full.json` - `25041fdb547a7b081225821dca28c3f5daa6e0b945852fa4ef317cb5880789bf`
- `ledger_verify_partial.json` - `da5b83470bdf9d47e92e30750cbe959e92ac00b95a091d8463af9e33f3ea0038`
- `ledger_verify_tampered.json` - `d722296b203911bc8ee3c97a6ce44773bdd4fd309dceb8e39b44e8c97a6e2588`
- `model_invocation.json` - `03e512254f0e34ee66d2c409bea20a35269e1b37bfc4a591c036736640aae1c5`
- `model_invocation_turn_1.json` - `03e512254f0e34ee66d2c409bea20a35269e1b37bfc4a591c036736640aae1c5`
- `model_prompt_redacted.json` - `e181db6153a1d78adc4f4210378286d7497d81c1794760172dbbb2fa76746d85`
- `model_prompt_redacted_turn_1.json` - `e181db6153a1d78adc4f4210378286d7497d81c1794760172dbbb2fa76746d85`
- `model_response_redacted.json` - `18694b7a52fc9526212d23c5158522051067c7c4f6e880f70db38c307b0e498a`
- `model_response_redacted_turn_1.json` - `18694b7a52fc9526212d23c5158522051067c7c4f6e880f70db38c307b0e498a`
- `produced_artifact.txt` - `70a2aaf79fd6051d590c09fb5434618e468fc91e7c44d947cf060e5de1a5b14a`
- `proposal_extraction.json` - `493e671221128a43f0822c8604fbaa2b3bebf245ecd399a15909c1314ff96a22`
- `proposal_extraction_turn_1.json` - `493e671221128a43f0822c8604fbaa2b3bebf245ecd399a15909c1314ff96a22`
- `run_events.json` - `4db3271c8abaa06b34ca4a748b33549ced2139884df34c2e1d02be47c3af59e8`
- `run_status_after.json` - `edfea7383d586471d7c1f679c6ac75cf6af8dbd6cf16d42722cc831967265762`
- `run_status_before.json` - `e8a11c9c0f22414db02852888c5a08596702885257847ba10727c96244caa0a6`
- `run_summary.json` - `5de5104ee55cbe5035c33f9dd33abd055c32b6c1fa5fa808ec3525b0767f58e4`
- `server_log.txt` - `06847d6e2e820b76e6166ece0f2c29d87d4e425cc456502f17d62d5aa002dabb`
- `submitted_request.json` - `8d95152416cdb89b3877cd867d76d8d7bd698dac63e3b46ae1c64b2977dc40ba`
- `submitted_run.json` - `e8a11c9c0f22414db02852888c5a08596702885257847ba10727c96244caa0a6`
- `tamper_mutation.json` - `444b5b101b24d43aa82d3e0720869e81a729acbca1656b9cf7a13587c249cce1`
- `workspace_after.txt` - `db99ac73fc2f458050aae1e9ce2e509e912604a5d13d0700f99a99f4c9c4f4f2`
- `workspace_before.txt` - `9a42f99ddd93de7e23e3e1f1336bae5dc4f8e1a9948ccdfd6df98f50cac7a0f8`

Note: `manifest.json` is excluded from its own hash list. `bundle_verification_report.md` is excluded from this report's own artifact index; its SHA-256 is recorded in `manifest.json`.

**Blockers**
- None

Tampered ledger mutation: event_id=`run:denial-path-v1-20260426t200916z:submitted`, field=`namespace`, old=`d`, new=`D`.

Run event hash note: `run_events.json` exposes computed `event_hash` and `chain_hash` after ledger export; `ledger_full.json` remains the canonical integrity source.

**What this bundle does NOT prove**
- "Replay stability: replay_ready=false by design. The system explicitly reports this as a known open item. No replay or cross-run stability claim is made by this bundle."
- "Cross-run determinism: this bundle covers a single run. No claim is made that an equivalent run with the same prompt produces identical output."
- "Cloud or multi-tenant deployment: this run was executed on a local Orket instance."
- "Third-party connector auto-discovery: entry-point discovery is a deferred feature and was not exercised in this run."
- "Model-output reproducibility: the model response is treated as non-deterministic. The bundle proves governance of the effect, not reproducibility of the content."
