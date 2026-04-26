# live_governed_run_bundle_v1

- run_id: `live-governed-run-v1-20260426t183304z`
- namespace: `live_governed_run_v1_20260426T183304Z`
- provider: `ollama`
- model: `qwen2.5-coder:7b`
- generated_at: `20260426T183304Z`

This bundle includes an intentional synthetic-shortcut probe. The `acceptance_contract` tool args differ from the model-requested tool args. The contract shortcut file remained absent, while the model-produced proposal file appeared only after approval.

Proposal derivation is tied through `model_response_redacted.json`, `proposal_extraction.json`, and the `proposal_made` ledger payload.

The graph artifacts are outward pipeline evidence graphs generated directly from the outward run id and outward pipeline store, not legacy ProductFlow or `runs/<session_id>/` session graphs.

`environment.json` records `orket_version_header: 0.4.31`. The command log initially printed blank version values because the capture code read the response header case-sensitively; a later case-insensitive validation captured the same `X-Orket-Version` value explicitly.

This bundle does not prove replay stability, cross-run determinism, cloud readiness, or model-output reproducibility.
