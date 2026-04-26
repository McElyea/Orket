# Multi-Step Approved v1 Verification Report

**Run identity**
- run_id: `multi-step-approved-v1-20260426t200916z`
- session_id: `None`
- namespace: `multi_step_approved_v1_20260426T200916Z`
- submitted_at: `2026-04-26T20:09:19.037462+00:00`
- completed_at: `2026-04-26T20:09:23.488671+00:00`

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
| two distinct proposals | 2 proposal_made events and 2 proposal IDs | pass |
| two approval decisions | 2 proposal_approved events | pass |
| proposal 2 depends on proposal 1 output | turn 2 prompt includes prior read_file result redacted in artifact | pass |
| workspace output absent after first approval | sorted_items.txt absent after read approval | pass |
| run_summary current_turn | 2 | pass |

**Commands run**
1. `C:\Python314\python.exe scripts/providers/check_model_provider_preflight.py --provider ollama --model-id qwen2.5-coder:7b --timeout 20` -> returncode=0; stdout=WARMUP_STATUS=OK source=ollama_list resolution_mode=requested resolved_model=qwen2.5-coder:7b
WARMUP_AVAILABLE_MODELS=Command-R:35B,Mistral-Nemo:12B,deepseek-coder:33B,deepseek-r1:32b,functiongemma:latest,gemma3:27b,gemma3:latest,gpt-oss:120b,gpt-oss:20b,llama3.1:8b,nomic-embed-text:latest,qwen2.5-coder:14b,qwen2.5-coder:7b,qwen2.5:14b,qwen2.5:7b,qwen3-coder:latest
provider=ollama canonical=ollama base_url=http://127.0.0.1:11434 model_id=qwen2.5-coder:7b
RESOLVED_MODEL_ID=qwen2.5-coder:7b
RESOLUTION_MODE=requested
PREFLIGHT=PASS; stderr=
2. `C:\Python314\python.exe server.py --host 127.0.0.1 --port 60701 with ORKET_API_KEY=[REDACTED] ORKET_DISABLE_SANDBOX=1` -> started pid=34768
3. `HTTP GET http://127.0.0.1:60701/health` -> HTTP 200; X-Orket-Version=
4. `HTTP GET http://127.0.0.1:60701/v1/version headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31
5. `HTTP POST http://127.0.0.1:60701/v1/runs headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=submitted_run.json
6. `HTTP GET http://127.0.0.1:60701/v1/runs/multi-step-approved-v1-20260426t200916z headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31
7. `HTTP GET http://127.0.0.1:60701/v1/approvals?status=pending&session_id=multi-step-approved-v1-20260426t200916z headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31
8. `HTTP POST http://127.0.0.1:60701/v1/approvals/proposal%3Amulti-step-approved-v1-20260426t200916z%3Aread_file%3A0001/approve headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=approval_decision_1.json
9. `HTTP GET http://127.0.0.1:60701/v1/approvals?status=pending&session_id=multi-step-approved-v1-20260426t200916z headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31
10. `HTTP POST http://127.0.0.1:60701/v1/approvals/proposal%3Amulti-step-approved-v1-20260426t200916z%3Awrite_file%3A0002/approve headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=approval_decision_2.json
11. `HTTP GET http://127.0.0.1:60701/v1/runs/multi-step-approved-v1-20260426t200916z headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31
12. `HTTP GET http://127.0.0.1:60701/v1/runs/multi-step-approved-v1-20260426t200916z/ledger headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=ledger_full.json
13. `HTTP GET http://127.0.0.1:60701/v1/runs/multi-step-approved-v1-20260426t200916z/ledger?types=proposals%2Cdecisions headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=ledger_partial_decisions.json
14. `HTTP GET http://127.0.0.1:60701/v1/runs/multi-step-approved-v1-20260426t200916z/events headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=run_events.json
15. `HTTP GET http://127.0.0.1:60701/v1/runs/multi-step-approved-v1-20260426t200916z/summary headers={'X-API-Key':'[REDACTED]'}` -> HTTP 200; X-Orket-Version=0.4.31; artifact=run_summary.json
16. `C:\Python314\python.exe scripts/observability/emit_run_evidence_graph.py --run-id multi-step-approved-v1-20260426t200916z --workspace-root C:\Source\Orket --outward-pipeline-db C:\Source\Orket\.tmp\multi_step_approved_v1_20260426T200916Z.sqlite3` -> returncode=0; stdout={
  "event_count": 17,
  "graph_kind": "outward_pipeline",
  "graph_result": "complete",
  "json_path": "C:/Source/Orket/workspace/multi_step_approved_v1_20260426T200916Z/runs/multi-step-approved-v1-20260426t200916z/run_evidence_graph.json",
  "ledger_hash": "a0ef0b0e8ab529ed63d3ec545a02ee0239da83a5c4c57a8f4a0bb5c494ca1299",
  "ok": true,
  "proposal_count": 2,
  "requested_run_id": "multi-step-approved-v1-20260426t200916z",
  "run_id": "multi-step-approved-v1-20260426t200916z",
  "schema_version": "1.0",
  "selected_views": [
    "full_lineage",
    "failure_path",
    "resource_authority_path",
    "closure_path"
  ],
  "session_id": null,
  "svg_path": "C:/Source/Orket/workspace/multi_step_approved_v1_20260426T200916Z/runs/multi-step-approved-v1-20260426t200916z/run_evidence_graph.svg",
  "tool_invocation_count": 2
}; stderr=
17. `Stop Orket server pid=34768` -> exitcode=1
18. `C:\Python314\python.exe -m orket.interfaces.orket_bundle_cli ledger verify C:\Source\Orket\artifacts\multi_step_approved_v1\20260426T200916Z\ledger_full.json` -> returncode=0; stdout={
  "schema_version": "ledger_export.v1",
  "result": "valid",
  "export_scope": "all",
  "run_id": "multi-step-approved-v1-20260426t200916z",
  "ledger_hash": "a0ef0b0e8ab529ed63d3ec545a02ee0239da83a5c4c57a8f4a0bb5c494ca1299",
  "event_count": 17,
  "checked_event_count": 17,
  "errors": []
}; stderr=
19. `C:\Python314\python.exe -m orket.interfaces.orket_bundle_cli ledger verify C:\Source\Orket\artifacts\multi_step_approved_v1\20260426T200916Z\ledger_partial_decisions.json` -> returncode=0; stdout={
  "schema_version": "ledger_export.v1",
  "result": "partial_valid",
  "export_scope": "partial_view",
  "run_id": "multi-step-approved-v1-20260426t200916z",
  "ledger_hash": "a0ef0b0e8ab529ed63d3ec545a02ee0239da83a5c4c57a8f4a0bb5c494ca1299",
  "event_count": 17,
  "checked_event_count": 6,
  "errors": []
}; stderr=
20. `C:\Python314\python.exe -m orket.interfaces.orket_bundle_cli ledger verify C:\Source\Orket\artifacts\multi_step_approved_v1\20260426T200916Z\ledger_tampered.json` -> returncode=1; stdout={
  "schema_version": "ledger_export.v1",
  "result": "invalid",
  "export_scope": "all",
  "run_id": "multi-step-approved-v1-20260426t200916z",
  "ledger_hash": "a0ef0b0e8ab529ed63d3ec545a02ee0239da83a5c4c57a8f4a0bb5c494ca1299",
  "event_count": 17,
  "checked_event_count": 17,
  "errors": [
    "event_hash mismatch at position 1",
    "chain_hash mismatch at position 1",
    "previous_chain_hash mismatch at position 2"
  ]
}; stderr=


**Artifact index**
- `README.md` - `44592be94657f5e6467de935cb08fdd4689fedd4aa2df407594f9815dcedf315`
- `approval_decision.json` - `03e7d21d1355b3efec7e8e45f11a95fc66f5913499e14cdf5cf6fb160317d999`
- `approval_decision_1.json` - `68ec46015ce6322ab4b5b8647ca8b00372fc62ada76c9fac7db3be85a20f11b1`
- `approval_decision_2.json` - `56a232603799f8abc20cadf922c600d644bd0baec57a78987efbc6ce1be9b92f`
- `approval_pending.json` - `e757214cbb10c2d1c01215431f8b057c26f2393f9c771b0ae7c62eba65a023fd`
- `approval_pending_1.json` - `5d5436c5e3003f2ec3a5810c3288599e1928180a7fcd94ef49e2e086f9491a46`
- `approval_pending_2.json` - `7df934b645bbe6ba7d82563975a89d56e4521963204a95ae724499f27729ae1d`
- `command_log.txt` - `75354c3112c90e692f1fd2dfaae7abf016f2cd97a0014c15529e4743afd62338`
- `environment.json` - `47f6e0d4dd4da5049ce73a81a3e7f8362f2c1ccdc7a0c652ab1a065780037bb5`
- `execution_graph.json` - `d02b8e8770f71995428d4e5f90b848f982a1831a27aa94a2e35f0850cfce6076`
- `execution_graph.svg` - `1e95bee8bd1ae2140c6d5193f53c93b42de7014b72c39bbe4ce64edc71ca5308`
- `ledger_full.json` - `f293f3fecb2f677df70b0f70154114155fc7a9397166e8fc74550dc3965600a6`
- `ledger_partial_decisions.json` - `67f2947fbf7642d1b624963a1b954d71c1d3cf02027dafa740c4f0357ce85819`
- `ledger_tampered.json` - `a9ffb4ff48eb63bc28c1df3c606d1657b4050d2be1b8cfdc088a2dfae9caf633`
- `ledger_verify_full.json` - `3116313f48d23b2dec9cc6f6035f069961ac7fa3c77c74c790d7211b8ea8c370`
- `ledger_verify_partial.json` - `34466af9050a1a6911f3b6aaa0694527089981bfc9091fe9394310cb12361afa`
- `ledger_verify_tampered.json` - `b8fd283f85974b3e39256aff2946ef36b32a4f7cb9ea78b777537bec30a02a84`
- `model_invocation.json` - `5da019c422bfbe813391aaa3c7e727cfc1599cfd3e87b08deb56546544800a58`
- `model_invocation_turn_1.json` - `61dcacf0680df71591fe315a6f36798f58c31d6a2f5bc76a1213dcef77f224c1`
- `model_invocation_turn_2.json` - `5da019c422bfbe813391aaa3c7e727cfc1599cfd3e87b08deb56546544800a58`
- `model_prompt_redacted.json` - `856e79c0fcea77c2d4fb262632b68d8ffa0b8dd790d691cbecf6a6f7232aa7ec`
- `model_prompt_redacted_turn_1.json` - `fe7bae02c6c7023899060b7dcfe532fb7a90ba87cf9926ddeb2b529824c5ce4b`
- `model_prompt_redacted_turn_2.json` - `856e79c0fcea77c2d4fb262632b68d8ffa0b8dd790d691cbecf6a6f7232aa7ec`
- `model_response_redacted.json` - `d60920116aab52dbe09416d5845db725bef08765ca2d4f02e05e73eee6d7f81e`
- `model_response_redacted_turn_1.json` - `918683e7a0d9809105c73d841f92faa2281a79610ffc54ed23422546ecbe2131`
- `model_response_redacted_turn_2.json` - `d60920116aab52dbe09416d5845db725bef08765ca2d4f02e05e73eee6d7f81e`
- `produced_artifact.txt` - `8e75b944ef3c957e2f305e50461b5a9980e53707686a81bb6781d7b5420a2a43`
- `proposal_extraction.json` - `1802d43428e2aa0f3066347aa2c9c429c78f57cb00bb0d9e1f6122b1c8205f7b`
- `proposal_extraction_turn_1.json` - `10be38f8c9fe27b7371bd4f38b7f12cf5229d9c2b094370083831cb6572722e5`
- `proposal_extraction_turn_2.json` - `1802d43428e2aa0f3066347aa2c9c429c78f57cb00bb0d9e1f6122b1c8205f7b`
- `run_events.json` - `a0fa5302161d42fbd40dcd25b4126add881609f7459fc46463920da1ee94fd30`
- `run_status_after.json` - `615524083f027e0cb6854535dac6b51b1bb56b7944b3a8a04a615878464cd843`
- `run_status_before.json` - `1c91523cd77fdfe84d531be664470f0acbf15fc770a9829c050adf51ac7a2bfe`
- `run_summary.json` - `369c205c46509bc06e014302cce33a7916e675ffbb90433ac13c57e6fe243555`
- `server_log.txt` - `34323ec91121ee466ee1928b26b8f3e2177d011e50675d4730c62961f2917f96`
- `submitted_request.json` - `c7056c6711460e1a506d9cc5a658b55443e7ddae3de9561713c0f60d19571d34`
- `submitted_run.json` - `1c91523cd77fdfe84d531be664470f0acbf15fc770a9829c050adf51ac7a2bfe`
- `tamper_mutation.json` - `5b6922318746a2ad7c43142e6deea0c9debb5d17f7cfb1912daef55dcf8fc37f`
- `workspace_after.txt` - `3d749da8daf802972a5295369f0eff7fec37d57482c3ef66c7e4370269f00de3`
- `workspace_after_first_approval.txt` - `a853682ce3119f1ab39236a6fb4d4d14b0df1798edd536bf2a9eec59a304c149`
- `workspace_before.txt` - `61733d32434c9e34c6c7da676f9c710c697645655c3bc2aa5e8b76f5bbf8307e`

Note: `manifest.json` is excluded from its own hash list. `bundle_verification_report.md` is excluded from this report's own artifact index; its SHA-256 is recorded in `manifest.json`.

**Blockers**
- None

Tampered ledger mutation: event_id=`run:multi-step-approved-v1-20260426t200916z:submitted`, field=`namespace`, old=`m`, new=`M`.

Run event hash note: `run_events.json` exposes computed `event_hash` and `chain_hash` after ledger export; `ledger_full.json` remains the canonical integrity source.

**What this bundle does NOT prove**
- "Replay stability: replay_ready=false by design. The system explicitly reports this as a known open item. No replay or cross-run stability claim is made by this bundle."
- "Cross-run determinism: this bundle covers a single run. No claim is made that an equivalent run with the same prompt produces identical output."
- "Cloud or multi-tenant deployment: this run was executed on a local Orket instance."
- "Third-party connector auto-discovery: entry-point discovery is a deferred feature and was not exercised in this run."
- "Model-output reproducibility: the model response is treated as non-deterministic. The bundle proves governance of the effect, not reproducibility of the content."
