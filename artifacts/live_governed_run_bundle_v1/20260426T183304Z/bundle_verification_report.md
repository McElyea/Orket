# Live Governed Run Bundle v1 Verification Report

**Run identity**
- run_id: `live-governed-run-v1-20260426t183304z`
- session_id: `None`
- namespace: `live_governed_run_v1_20260426T183304Z`
- submitted_at: `2026-04-26T18:33:07.858058+00:00`
- completed_at: `2026-04-26T18:33:18.673109+00:00`

**Model and provider**
- provider name: `ollama`
- model name: `qwen2.5-coder:7b`
- endpoint used: `http://127.0.0.1:11434`

**Public claim boundaries**
This bundle proves one local live outward pipeline run. It does not prove replay stability, cross-run determinism, cloud readiness, or model-output reproducibility.

**Graph identity**
The captured graph is an outward pipeline evidence graph generated directly from the outward `run_id` and outward pipeline SQLite store. It is not a legacy ProductFlow graph and does not depend on a `runs/<session_id>/` session graph.

**Proof checklist**
| Item | Expected result | Status |
|---|---|---|
| live model invocation | success | pass |
| submitted_request proves no synthetic governed_tool_call shortcut | true | pass |
| model response captured or safely redacted | true | pass |
| proposal extraction captured | true | pass |
| proposal derived from model output | true | pass |
| proposal before effect | true | pass |
| approval before effect | true | pass |
| file absent before approval | true | pass |
| file present after approval only | true | pass |
| run events captured | true | pass |
| execution graph captured | true | pass |
| full ledger verification | valid | pass |
| partial ledger verification | partial_valid | pass |
| tampered ledger verification | invalid | pass |
| no raw secrets found | true | pass |
| manifest hashes verified | true | pass |

**Header capture note**
Commands 3-14 show blank `X-Orket-Version` values because the initial command logger read the response header case-sensitively. Command 22 reran `/v1/version` with case-insensitive header capture and recorded `x-orket-version=0.4.31`; `environment.json` records this as `orket_version_header`.

**Commands run**
1. `C:\Python314\python.exe scripts/providers/check_model_provider_preflight.py --provider ollama --model-id qwen2.5-coder:7b --timeout 20`
   - success: returncode=0; stdout=WARMUP_STATUS=OK source=ollama_list resolution_mode=requested resolved_model=qwen2.5-coder:7b
WARMUP_AVAILABLE_MODELS=Command-R:35B,Mistral-Nemo:12B,deepseek-coder:33B,deepseek-r1:32b,functiongemma:latest,gemma3:27b,gemma3:latest,gpt-oss:120b,gpt-oss:20b,llama3.1:8b,nomic-embed-text:latest,qwen2.5-coder:14b,qwen2.5-coder:7b,qwen2.5:14b,qwen2.5:7b,qwen3-coder:latest
provider=ollama canonical=ollama base_url=http://127.0.0.1:11434 model_id=qwen2.5-coder:7b
RESOLVED_MODEL_ID=qwen2.5-coder:7b
RESOLUTION_MODE=requested
PREFLIGHT=PASS; stderr=
2. `C:\Python314\python.exe server.py --host 127.0.0.1 --port 55818 with ORKET_API_KEY=[REDACTED] ORKET_DISABLE_SANDBOX=1`
   - success: started pid=6156
3. `HTTP GET http://127.0.0.1:55818/health`
   - success: HTTP 200; X-Orket-Version=
4. `HTTP GET http://127.0.0.1:55818/v1/version headers={'X-API-Key':'[REDACTED]'}`
   - success: HTTP 200; X-Orket-Version=
5. `HTTP POST http://127.0.0.1:55818/v1/runs headers={'X-API-Key':'[REDACTED]'}`
   - success: HTTP 200; X-Orket-Version=; artifact=submitted_run.json
6. `HTTP GET http://127.0.0.1:55818/v1/runs/live-governed-run-v1-20260426t183304z headers={'X-API-Key':'[REDACTED]'}`
   - success: HTTP 200; X-Orket-Version=; artifact=run_status_before.json
7. `HTTP GET http://127.0.0.1:55818/v1/approvals?status=pending headers={'X-API-Key':'[REDACTED]'}`
   - success: HTTP 200; X-Orket-Version=
8. `HTTP GET http://127.0.0.1:55818/v1/approvals/proposal%3Alive-governed-run-v1-20260426t183304z%3Awrite_file%3A0001 headers={'X-API-Key':'[REDACTED]'}`
   - success: HTTP 200; X-Orket-Version=
9. `HTTP POST http://127.0.0.1:55818/v1/approvals/proposal%3Alive-governed-run-v1-20260426t183304z%3Awrite_file%3A0001/approve headers={'X-API-Key':'[REDACTED]'}`
   - success: HTTP 200; X-Orket-Version=; artifact=approval_decision.json
10. `HTTP GET http://127.0.0.1:55818/v1/runs/live-governed-run-v1-20260426t183304z headers={'X-API-Key':'[REDACTED]'}`
   - success: HTTP 200; X-Orket-Version=; artifact=run_status_after.json
11. `HTTP GET http://127.0.0.1:55818/v1/runs/live-governed-run-v1-20260426t183304z/ledger headers={'X-API-Key':'[REDACTED]'}`
   - success: HTTP 200; X-Orket-Version=; artifact=ledger_full.json
12. `HTTP GET http://127.0.0.1:55818/v1/runs/live-governed-run-v1-20260426t183304z/ledger?types=proposals%2Cdecisions headers={'X-API-Key':'[REDACTED]'}`
   - success: HTTP 200; X-Orket-Version=; artifact=ledger_partial_decisions.json
13. `HTTP GET http://127.0.0.1:55818/v1/runs/live-governed-run-v1-20260426t183304z/events headers={'X-API-Key':'[REDACTED]'}`
   - success: HTTP 200; X-Orket-Version=; artifact=run_events.json
14. `HTTP GET http://127.0.0.1:55818/v1/runs/live-governed-run-v1-20260426t183304z/summary headers={'X-API-Key':'[REDACTED]'}`
   - success: HTTP 200; X-Orket-Version=; artifact=run_summary.json
15. `C:\Python314\python.exe scripts/observability/emit_run_evidence_graph.py --run-id live-governed-run-v1-20260426t183304z --workspace-root C:\Source\Orket --outward-pipeline-db C:\Source\Orket\.tmp\live_governed_run_bundle_v1_20260426T183304Z.sqlite3`
   - success: returncode=0; stdout={
  "event_count": 10,
  "graph_kind": "outward_pipeline",
  "graph_result": "complete",
  "json_path": "C:/Source/Orket/workspace/live_governed_run_v1_20260426T183304Z/runs/live-governed-run-v1-20260426t183304z/run_evidence_graph.json",
  "ledger_hash": "b382919d0e99322cbfbb00ef2e5b1507037ba357bf417683bb17f8d842161efe",
  "ok": true,
  "proposal_count": 1,
  "requested_run_id": "live-governed-run-v1-20260426t183304z",
  "run_id": "live-governed-run-v1-20260426t183304z",
  "schema_version": "1.0",
  "selected_views": [
    "full_lineage",
    "failure_path",
    "resource_authority_path",
    "closure_path"
  ],
  "session_id": null,
  "svg_path": "C:/Source/Orket/workspace/live_governed_run_v1_20260426T183304Z/runs/live-governed-run-v1-20260426t183304z/run_evidence_graph.svg",
  "tool_invocation_count": 1
}; stderr=
16. `Stop Orket server pid=6156`
   - success: exitcode=1
17. `C:\Python314\python.exe -m orket.interfaces.orket_bundle_cli ledger verify C:\Source\Orket\artifacts\live_governed_run_bundle_v1\20260426T183304Z\ledger_full.json`
   - success: returncode=0; stdout={
  "schema_version": "ledger_export.v1",
  "result": "valid",
  "export_scope": "all",
  "run_id": "live-governed-run-v1-20260426t183304z",
  "ledger_hash": "b382919d0e99322cbfbb00ef2e5b1507037ba357bf417683bb17f8d842161efe",
  "event_count": 10,
  "checked_event_count": 10,
  "errors": []
}; stderr=
18. `C:\Python314\python.exe -m orket.interfaces.orket_bundle_cli ledger verify C:\Source\Orket\artifacts\live_governed_run_bundle_v1\20260426T183304Z\ledger_partial_decisions.json`
   - success: returncode=0; stdout={
  "schema_version": "ledger_export.v1",
  "result": "partial_valid",
  "export_scope": "partial_view",
  "run_id": "live-governed-run-v1-20260426t183304z",
  "ledger_hash": "b382919d0e99322cbfbb00ef2e5b1507037ba357bf417683bb17f8d842161efe",
  "event_count": 10,
  "checked_event_count": 3,
  "errors": []
}; stderr=
19. `C:\Python314\python.exe -m orket.interfaces.orket_bundle_cli ledger verify C:\Source\Orket\artifacts\live_governed_run_bundle_v1\20260426T183304Z\ledger_tampered.json`
   - success: returncode=1; stdout={
  "schema_version": "ledger_export.v1",
  "result": "invalid",
  "export_scope": "all",
  "run_id": "live-governed-run-v1-20260426t183304z",
  "ledger_hash": "b382919d0e99322cbfbb00ef2e5b1507037ba357bf417683bb17f8d842161efe",
  "event_count": 10,
  "checked_event_count": 10,
  "errors": [
    "event_hash mismatch at position 4",
    "chain_hash mismatch at position 4",
    "previous_chain_hash mismatch at position 5"
  ]
}; stderr=
20. `python - <inline report_manifest_reconcile>`
   - success: Reconcile self-referential report/manifest hashes; artifact=bundle_verification_report.md,manifest.json
21. `C:\Python314\python.exe server.py --host 127.0.0.1 --port 52308 with ORKET_API_KEY=[REDACTED] ORKET_DISABLE_SANDBOX=1`
   - success: started pid=29568
22. `HTTP GET http://127.0.0.1:52308/v1/version headers={'X-API-Key':'[REDACTED]'}`
   - success: HTTP 200; x-orket-version=0.4.31
23. `Stop Orket server pid=29568`
   - success: exitcode=1
24. `python - <inline version_header_capture_reconcile>`
   - success: updated environment/report/manifest after case-insensitive X-Orket-Version capture; artifact=environment.json,bundle_verification_report.md,manifest.json

**Artifact index**
- `README.md` - `1ce146526647aa8ae6c5b055ecd5afa2191c483b3dbdf27d3827a8a445e88008`
- `approval_decision.json` - `126573a31be513d442d80bb57e36223286e496f28ea4f07f6b52fafa37b81b83`
- `approval_pending.json` - `f03cdc4e5ba7924a09bcc806aee01aed85bbe303619c3267fd7234046b7f7fda`
- `command_log.txt` - `ad8c71c937e4aef11b124db5d474d565a1da1ee53d13463e76f6cabce8cfe629`
- `environment.json` - `8791ad659af5a85169a9b2f9909a19f60b6f106793e869ba3fda98bd405a31d3`
- `execution_graph.json` - `f1c39c11abfa454b5c48019be33fe79fa7a7152cd8b61ec43bd88d4716ee46d9`
- `execution_graph.svg` - `21ec18d057db586d2a900e591f6a09e152657d288cb5ce161f4aa9779eea39b5`
- `ledger_full.json` - `f7f91d63d06b9c357118b90dd6f3cd8a39d5e1f7c6879f54c9d58a40a643074f`
- `ledger_partial_decisions.json` - `db37355a7755035514065cb803802ea4111de6b47ddec482ceff12dd99b09734`
- `ledger_tampered.json` - `7ead79991cbd88e302726b5bb04f35e8e2360f2296e44aef72d2162e14481a71`
- `ledger_verify_full.json` - `2eb2882188a493bd92497b57d516e37c313a126b7a8ea0483b2801a895372f4c`
- `ledger_verify_partial.json` - `3b7177a9431d6a9e13d600a1bfb0f9b76caabf4a7e226b93b537720d5699adb6`
- `ledger_verify_tampered.json` - `d1e68e9a38a90f5d31cc07d274cbe945e516eb51895926ef077e55f0ff0b0dad`
- `model_invocation.json` - `2c5044981d9001fee6dcb1c7b796ac9c1dd2cd1310f3353506f8b6b1e9f26605`
- `model_prompt_redacted.json` - `4f8eda5576a5f1b0c2682d26bcb187fc17d8070aadd37252d46f71a1b9b187da`
- `model_response_redacted.json` - `acdcccdd12bf6a37474cf509cb8ccda9c4f0a3d14f305ea1196bf253e384d9fa`
- `produced_artifact.txt` - `d2e71603d8990e773ce16ac637566eed5a0c912596e089ddb45a6d32c98a1f04`
- `proposal_extraction.json` - `357dd873e874e665265d079ad9eaf630f85a7e80cb321e5c5b05baaaf5703efa`
- `run_events.json` - `bc8f520ddb989e9aab2a6b81756eac997505d6b5666516dbb1296d7736d9fd85`
- `run_status_after.json` - `bf359cee1f4347b7851f0cdcb02bebeaedd4be82605dbe764b9a8b8b3b1b1280`
- `run_status_before.json` - `a9f8bfbebdb9d70ed365c1e4e4ef020cb8c5f9cc10aa8b078288cd6266b158bb`
- `run_summary.json` - `58f60f7451f809b79f0db97bfd73184af9829a76589e3f0523bb9475bfc6e0d0`
- `server_log.txt` - `5d5a15c8799ca4f0670c4317e9a27e7f57c87d9cdeaa8a8c15af1d1920e158d7`
- `submitted_request.json` - `5d22d0c5fd4ec9e6e9253278ebacb9719c465e8740e5012105186ab4bfcf827e`
- `submitted_run.json` - `a9f8bfbebdb9d70ed365c1e4e4ef020cb8c5f9cc10aa8b078288cd6266b158bb`
- `workspace_after.txt` - `8cbf7aa2924011ff7d23d94b45cc940671058f423c6c0de66f961761abfa50d0`
- `workspace_before.txt` - `e79a2ce86425567422bb0a503544b8409099363023801396deaa927c4c264982`

Note: `manifest.json` is excluded from its own hash list because a manifest self-hash is self-referential. `bundle_verification_report.md` is excluded from this report's own artifact index for the same reason; its final SHA-256 is recorded in `manifest.json`.

**Blockers**
- None

Tampered ledger mutation: event_id=`run:live-governed-run-v1-20260426t183304z:0300:proposal:write_file`, field=`events[].payload.context_summary[0]`, old=`m`, new=`M`.

Run event hash note: `run_events.json` exposes computed `event_hash` and `chain_hash` after ledger export; `ledger_full.json` remains the canonical integrity source.

**What this bundle does NOT prove**
- "Replay stability: replay_ready=false by design. The system explicitly reports this as a known open item. No replay or cross-run stability claim is made by this bundle."
- "Cross-run determinism: this bundle covers a single run. No claim is made that an equivalent run with the same prompt produces identical output."
- "Cloud or multi-tenant deployment: this run was executed on a local Orket instance."
- "Third-party connector auto-discovery: entry-point discovery is a deferred feature and was not exercised in this run."
- "Model-output reproducibility: the model response is treated as non-deterministic. The bundle proves governance of the effect, not reproducibility of the content."
