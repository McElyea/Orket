# Mixed Decisions v1 Verification Report

**Run identity**
- run_id: `mixed-decisions-v1-20260426t200916z`
- session_id: `None`
- namespace: `mixed_decisions_v1_20260426T200916Z`
- submitted_at: `2026-04-26T20:17:13.362449+00:00`
- completed_at: `2026-04-26T20:17:18.088395+00:00`

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
| approval before effect | true | pass |
| file absent before approval | true | pass |
| final terminal status | completed or equivalent success | pass |
| run events captured | true | pass |
| execution graph captured | true | pass |
| full ledger verification | valid | pass |
| partial ledger verification | partial_valid | pass |
| tampered ledger verification | invalid | pass |
| no raw secrets found | true | pass |
| manifest hashes verified | true | pass |
| two proposals | 2 proposal_made events | pass |
| one approve and one deny | 1 proposal_approved and 1 proposal_denied | pass |
| approval_decision_1 and approval_decision_2 captured | both artifacts exist | pass |
| selective effect | approved_artifact_exists=True and denied_artifact_exists=False | pass |
| second proposal targets denied file | approval_pending_2 path is denied_output.txt | pass |

**Commands run**
1. `C:\Python314\python.exe scripts/providers/check_model_provider_preflight.py --provider ollama --model-id qwen2.5-coder:7b --timeout 20` -> returncode=0; stdout=WARMUP_STATUS=OK source=ollama_list resolution_mode=requested resolved_model=qwen2.5-coder:7b
WARMUP_AVAILABLE_MODELS=Command-R:35B,Mistral-Nemo:12B,deepseek-coder:33B,deepseek-r1:32b,functiongemma:latest,gemma3:27b,gemma3:latest,gpt-oss:120b,gpt-oss:20b,llama3.1:8b,nomic-embed-text:latest,qwen2.5-coder:14b,qwen2.5-coder:7b,qwen2.5:14b,qwen2.5:7b,qwen3-coder:latest
provider=ollama canonical=ollama base_url=http://127.0.0.1:11434 model_id=qwen2.5-coder:7b
RESOLVED_MODEL_ID=qwen2.5-coder:7b
RESOLUTION_MODE=requested
PREFLIGHT=PASS; stderr=
2. `C:\Python314\python.exe server.py --host 127.0.0.1 --port 61160 with ORKET_API_KEY=[REDACTED] ORKET_DISABLE_SANDBOX=1` -> started pid=46168
3. `HTTP GET http://127.0.0.1:61160/health` -> HTTP 200; X-Orket-Version=
4. `HTTP GET http://127.0.0.1:61160/v1/version headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31
5. `HTTP POST http://127.0.0.1:61160/v1/runs headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=submitted_run.json
6. `HTTP GET http://127.0.0.1:61160/v1/runs/mixed-decisions-v1-20260426t200916z headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31
7. `HTTP GET http://127.0.0.1:61160/v1/approvals?status=pending&session_id=mixed-decisions-v1-20260426t200916z headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31
8. `HTTP POST http://127.0.0.1:61160/v1/approvals/proposal%3Amixed-decisions-v1-20260426t200916z%3Awrite_file%3A0001/approve headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=approval_decision_1.json
9. `HTTP GET http://127.0.0.1:61160/v1/approvals?status=pending&session_id=mixed-decisions-v1-20260426t200916z headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31
10. `HTTP POST http://127.0.0.1:61160/v1/approvals/proposal%3Amixed-decisions-v1-20260426t200916z%3Awrite_file%3A0002/deny headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=approval_decision_2.json
11. `HTTP GET http://127.0.0.1:61160/v1/runs/mixed-decisions-v1-20260426t200916z headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31
12. `HTTP GET http://127.0.0.1:61160/v1/runs/mixed-decisions-v1-20260426t200916z/ledger headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=ledger_full.json
13. `HTTP GET http://127.0.0.1:61160/v1/runs/mixed-decisions-v1-20260426t200916z/ledger?types=proposals%2Cdecisions headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=ledger_partial_decisions.json
14. `HTTP GET http://127.0.0.1:61160/v1/runs/mixed-decisions-v1-20260426t200916z/events headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=run_events.json
15. `HTTP GET http://127.0.0.1:61160/v1/runs/mixed-decisions-v1-20260426t200916z/summary headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=run_summary.json
16. `C:\Python314\python.exe scripts/observability/emit_run_evidence_graph.py --run-id mixed-decisions-v1-20260426t200916z --workspace-root c:\Source\Orket --outward-pipeline-db c:\Source\Orket\.tmp\mixed_decisions_v1_20260426T200916Z.sqlite3` -> returncode=0; stdout={
  "event_count": 16,
  "graph_kind": "outward_pipeline",
  "graph_result": "complete",
  "json_path": "C:/Source/Orket/workspace/mixed_decisions_v1_20260426T200916Z/runs/mixed-decisions-v1-20260426t200916z/run_evidence_graph.json",
  "ledger_hash": "c5afa7188d9e064114094e93e2d3378dea63656269fec55a7dbfd61f8ae3501e",
  "ok": true,
  "proposal_count": 2,
  "requested_run_id": "mixed-decisions-v1-20260426t200916z",
  "run_id": "mixed-decisions-v1-20260426t200916z",
  "schema_version": "1.0",
  "selected_views": [
    "full_lineage",
    "failure_path",
    "resource_authority_path",
    "closure_path"
  ],
  "session_id": null,
  "svg_path": "C:/Source/Orket/workspace/mixed_decisions_v1_20260426T200916Z/runs/mixed-decisions-v1-20260426t200916z/run_evidence_graph.svg",
  "tool_invocation_count": 1
}; stderr=
17. `Stop Orket server pid=46168` -> exitcode=1
18. `C:\Python314\python.exe -m orket.interfaces.orket_bundle_cli ledger verify c:\Source\Orket\artifacts\mixed_decisions_v1\20260426T200916Z\ledger_full.json` -> returncode=0; stdout={
  "schema_version": "ledger_export.v1",
  "result": "valid",
  "export_scope": "all",
  "run_id": "mixed-decisions-v1-20260426t200916z",
  "ledger_hash": "c5afa7188d9e064114094e93e2d3378dea63656269fec55a7dbfd61f8ae3501e",
  "event_count": 16,
  "checked_event_count": 16,
  "errors": []
}; stderr=
19. `C:\Python314\python.exe -m orket.interfaces.orket_bundle_cli ledger verify c:\Source\Orket\artifacts\mixed_decisions_v1\20260426T200916Z\ledger_partial_decisions.json` -> returncode=0; stdout={
  "schema_version": "ledger_export.v1",
  "result": "partial_valid",
  "export_scope": "partial_view",
  "run_id": "mixed-decisions-v1-20260426t200916z",
  "ledger_hash": "c5afa7188d9e064114094e93e2d3378dea63656269fec55a7dbfd61f8ae3501e",
  "event_count": 16,
  "checked_event_count": 6,
  "errors": []
}; stderr=
20. `C:\Python314\python.exe -m orket.interfaces.orket_bundle_cli ledger verify c:\Source\Orket\artifacts\mixed_decisions_v1\20260426T200916Z\ledger_tampered.json` -> returncode=1; stdout={
  "schema_version": "ledger_export.v1",
  "result": "invalid",
  "export_scope": "all",
  "run_id": "mixed-decisions-v1-20260426t200916z",
  "ledger_hash": "c5afa7188d9e064114094e93e2d3378dea63656269fec55a7dbfd61f8ae3501e",
  "event_count": 16,
  "checked_event_count": 16,
  "errors": [
    "event_hash mismatch at position 1",
    "chain_hash mismatch at position 1",
    "previous_chain_hash mismatch at position 2"
  ]
}; stderr=

**Artifact index**
- `README.md` - `3942dca5699a82ca7c2b654ef7c58f0b360cd684640652882e83554f69465096`
- `approval_decision.json` - `3ee294ee01729049cc97b51ae9c2799f8a05c6e92fdcf02fc539b8d5e7fc1f11`
- `approval_decision_1.json` - `12c4e39692fc5bcaed4882fd83e52f07086a5518f0a603ef4b11b24bd5a8318b`
- `approval_decision_2.json` - `70c3a43bbfc84fd565d28f1cde808edb9b878319c7d73be18663db6091746ac1`
- `approval_pending.json` - `24a371429cc2e4d118805c6cd99a0daa0fce0ed5940374a83c24084bb06d56df`
- `approval_pending_1.json` - `47916c5d877d3e4cf40ba0f314476cf91bc37f6756d7713820521dd02c91e3c5`
- `approval_pending_2.json` - `f3cc6e82368110c0320fe66f6c468889fb632e01b3f8f8c81b91854e387f7cc5`
- `command_log.txt` - `3df625faad9450ffb96f3402b6ddf392e1490d6a36fb2325b3ff559ed83290dc`
- `environment.json` - `b6ebbed6bd29d0336ee73557a87d6ccbd47bac92f754b98ff4c6e6e157781124`
- `execution_graph.json` - `2f465928fbac60b887260269b5a43770f5e67d9ea8d1c2cc072472f83a73b6a9`
- `execution_graph.svg` - `91b23b0df3c08354263ae4a7dc74a72679256390ac282c213056f95c559b83ab`
- `ledger_full.json` - `28460184c085699f3219aa19d12a351589c5fc611dff9e2545c20c47a6030433`
- `ledger_partial_decisions.json` - `4fdd64b37c63aa7866510691d2148f7b9cf110e13a721ddca07c43b60cf48bfa`
- `ledger_tampered.json` - `ce35e9d388f733427de15e84194f53070304f16f74aaf1e26d3c2b7116531208`
- `ledger_verify_full.json` - `d25fac946c5bbff00712021d04be7694fd94688932831ee5c7118c6d0a1dc5ad`
- `ledger_verify_partial.json` - `4bad33070f6d56922e077fee7be768af7c444a616f2f7c3f12a53271e50d1254`
- `ledger_verify_tampered.json` - `837cf6cb1d6c568299241d130502c765fb090e927de47f116c226025b00860eb`
- `model_invocation.json` - `64a536879bbd15d33f57b536f348699ec03a693870c4c4a42e63b3641ac172d3`
- `model_invocation_turn_1.json` - `381876ac6510efe09392ad9cb8d0a028a2965a099f45f88a8a730294fc8c15e7`
- `model_invocation_turn_2.json` - `64a536879bbd15d33f57b536f348699ec03a693870c4c4a42e63b3641ac172d3`
- `model_prompt_redacted.json` - `46332ecf67f28673d7ba61671d303e225ca8d386c291c4dfdd56e6b4a70aef19`
- `model_prompt_redacted_turn_1.json` - `e7eb3bbb35c45b0985e476e1c679de76ef4dec479824eed69cfc5f54c80ca106`
- `model_prompt_redacted_turn_2.json` - `46332ecf67f28673d7ba61671d303e225ca8d386c291c4dfdd56e6b4a70aef19`
- `model_response_redacted.json` - `f20a8a87f9fc9c97c702c00ef2d00842517150b1648fbd67e293d6e968af39f8`
- `model_response_redacted_turn_1.json` - `c6090a93fdedb43302fbba07ce29b0608a0e295860b2e78f84c0bcedcc97d81f`
- `model_response_redacted_turn_2.json` - `f20a8a87f9fc9c97c702c00ef2d00842517150b1648fbd67e293d6e968af39f8`
- `produced_artifact.txt` - `8f4f656d35d80c61e0e11ea5159c80208ac999db3559aa4e585ce607a1ba8f29`
- `proposal_extraction.json` - `35fb05de66e24b1c40276e4923982259895786d82d6331ca83d20d79e272059b`
- `proposal_extraction_turn_1.json` - `9766b63ac301c86555d459480b900413fc7a449dd33a44ad52214ece9c2fc4f7`
- `proposal_extraction_turn_2.json` - `35fb05de66e24b1c40276e4923982259895786d82d6331ca83d20d79e272059b`
- `run_events.json` - `6d4e776f4e9718da724ca86ec39a63fd455574072e362075ff9b6b64b976881f`
- `run_status_after.json` - `57e8fe2a62a6b495f01ed0c421b566c1e11678e1a5b48120548cb34d25e0c041`
- `run_status_before.json` - `404197f2c113f46f54bc1b08639fda5b9de9af3f004543b760920722a1fbe374`
- `run_summary.json` - `f351bf485450e9a0b14133f3df654f057387795f3cd66b2c05347592674105ba`
- `server_log.txt` - `efb76e2fa2cfbe5311f99b5a241a6ead3a13fa237d81d79caf1b3583fdecb91a`
- `submitted_request.json` - `2c857d6cdc06788bccf9726c730af557c5d939b0c80764e09230f51e267dda57`
- `submitted_run.json` - `404197f2c113f46f54bc1b08639fda5b9de9af3f004543b760920722a1fbe374`
- `tamper_mutation.json` - `3eebca9e8b4f64f88de6d8276ee6934306ea1db0abd798a00e5bfb0b2df44db9`
- `workspace_after.txt` - `b254894e525feed6a6b3f40030304f03207f76d35c988600f51993306a265866`
- `workspace_before.txt` - `add1701e12a839a124639a157546c2eefae25413f47e79cd0a7e61a7883fe42d`

Note: `manifest.json` is excluded from its own hash list. `bundle_verification_report.md` is excluded from this report's own artifact index; its SHA-256 is recorded in `manifest.json`.

**Blockers**
- None

Tampered ledger mutation: event_id=`run:mixed-decisions-v1-20260426t200916z:submitted`, field=`namespace`, old=`m`, new=`M`.

Run event hash note: `run_events.json` exposes computed `event_hash` and `chain_hash` after ledger export; `ledger_full.json` remains the canonical integrity source.

**What this bundle does NOT prove**
- "Replay stability: replay_ready=false by design. The system explicitly reports this as a known open item. No replay or cross-run stability claim is made by this bundle."
- "Cross-run determinism: this bundle covers a single run. No claim is made that an equivalent run with the same prompt produces identical output."
- "Cloud or multi-tenant deployment: this run was executed on a local Orket instance."
- "Third-party connector auto-discovery: entry-point discovery is a deferred feature and was not exercised in this run."
- "Model-output reproducibility: the model response is treated as non-deterministic. The bundle proves governance of the effect, not reproducibility of the content."
