# Installed Windows llama.cpp walkthrough

Date: 2026-10-04. Tested on native Python 3.11.14 and 3.12.2, matched core/SDK
0.7.2, using the existing authenticated interaction API and builtin
`model_stream_v1`. [Proof and limits](PROOF_REPORT.md).

## Install and select the existing server

Download both wheels, `dependency-constraints-0.7.2.txt`, and the hash manifest
from the core `v0.7.2` GitHub release.
In a fresh virtual environment, outside the checkout:

```powershell
python -m pip install --constraint <path-to-dependency-constraints-0.7.2.txt> <path-to-orket-0.7.2-py3-none-any.whl> <path-to-orket_extension_sdk-0.7.2-py3-none-any.whl>
python -m pip check
```

Use the interpreter from that environment for every command below. No editable
installation is involved. These are base installs without extras, using the
retained dependency constraints; unconstrained future resolution is not covered.
The tested operator-owned server remains at
`http://127.0.0.1:8080/v1`, with catalog identity
`orcarouter_qwen3.8-27b-uncensored-q4_k_l`. Check `/v1/models` before inference;
do not silently select/load another model. No API billing is used.

The standard API launcher remains `python server.py`. It is a source launcher,
not a wheel entrypoint. Copy the release's unchanged `server.py` into the intended
project and configure the launching shell:

```powershell
$env:ORKET_API_KEY = [guid]::NewGuid().ToString('N')
$env:ORKET_DISABLE_SANDBOX = '1'
$env:ORKET_STREAM_EVENTS_V1 = 'true'
$env:ORKET_MODEL_STREAM_PROVIDER = 'real'
$env:ORKET_MODEL_STREAM_REAL_PROVIDER = 'llama_cpp'
$env:ORKET_MODEL_STREAM_REAL_MODEL_ID = 'orcarouter_qwen3.8-27b-uncensored-q4_k_l'
$env:ORKET_LLAMA_CPP_BASE_URL = 'http://127.0.0.1:8080/v1'
$env:ORKET_MODEL_STREAM_OPENAI_USE_STREAM = 'true'
$env:ORKET_MODEL_STREAM_REAL_TIMEOUT_S = '120'
$env:ORKET_MODEL_STREAM_TURN_TIMEOUT_S = '120'
$env:ORKET_MODULE_PROFILE = 'developer-local'
$env:ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED = '0'
$env:ORKET_DURABLE_ROOT = Join-Path (Get-Location).Path '.orket/durable'
$env:ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL = '0'
$env:ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL = '0'
python server.py
```

Authenticate requests with `X-API-Key`. Create a session using
`POST /v1/interactions/sessions` with `{}`. Connect its WebSocket at
`/ws/interactions/<session_id>` **before** submitting
`POST /v1/interactions/<session_id>/turns`:

```json
{
  "workload_id": "model_stream_v1",
  "input_config": {
    "model_id": "orcarouter_qwen3.8-27b-uncensored-q4_k_l",
    "temperature": 0,
    "max_tokens": 96,
    "prompt": "Write one short sentence explaining why the sky appears blue."
  },
  "workspace": "workspace/default",
  "turn_params": {}
}
```

Observe actual `token_delta`, `turn_final`, and `commit_final`. This bounds token
generation; it is not a semantic answer-quality or natural-stop guarantee.
Inspect `GET /v1/sessions/<session_id>/status`, `/snapshot`, and `/replay` before
shutdown. For a separate cancellation run, request a long integer list with
`max_tokens=2048`; after its first real token send
`POST /v1/interactions/<session_id>/cancel` with `{"turn_id":"<turn_id>"}`.
Wait for `turn_interrupted` and `commit_final`. A second terminal cancel returns
409. Close the WebSocket before cooperatively stopping the API.

Inspect the project files after close:
`workspace/interactions/<session>/<turn>/authority_commit.json` and
`interaction_trace.jsonl`. Completion's intent references `model_stream_v1`;
interruption's lifecycle finalize intent references the turn ID. The digest binds
session, turn and intents. Neither file promises a generated-text transcript or
restartable API session. Token output requires its own capture.

## Reproduce the retained local acceptance probe

The exact release probe is retained at
`benchmarks/results/releases/0.7.2/probes/prr_journey.py`. It is an evidence
harness for this `C:/Source/Orket` workspace, not a new product entrypoint.
From a new external project containing the release's `server.py`, invoke:

```powershell
python -I C:/Source/Orket/benchmarks/results/releases/0.7.2/probes/prr_journey.py (Get-Location).Path 0.7.2
```

It imports the installed packages, boots the canonical app through Uvicorn on an
ephemeral local port, executes the requests above, verifies durable digests and
cooperatively closes the server. `journey.json` is its stable diff-ledger result.
Expected: `observed_result=success`, `runtime_closed=true`, zero owned requests
and background tasks. The outer acceptance run additionally verifies native
process cleanup. It does not prove remote inference termination or console
signal delivery. `--parser-proof` instead sends actual streamed output unchanged
through the installed parser/validator and retains the strict-grounding refusal.

## Diagnose CLI startup

Run `orket runtime --workspace <output-directory>` from the intended project.
An absent `model/` produces the retained structural reconciliation warning and
degraded status. For a fresh startup-only demonstration, create these JSON files:

| Path | Contents |
| --- | --- |
| `model/core/rocks/run_the_business.json` | `{"name":"Run the Business","epics":[]}` |
| `model/core/epics/prr_startup.json` | `{"name":"prr_startup","team":"prr_team","environment":"standard","issues":[]}` |
| `model/core/teams/prr_team.json` | `{"name":"PRR startup team","seats":{}}` |

Startup adopts `{"epic":"prr_startup","department":"core"}` into the rock,
shows the epic without a metadata error, and reaches `ORKET DRIVER (Interactive)`
without that warning. Enter `exit` to close. Do not overwrite existing project
assets with this demonstration. It has no issues and establishes startup only.

The original operator server's embedded GGUF template failed the separately
declared Qwen3.8 card profile with `E_LLAMA_CPP_TEMPLATE_IDENTITY`. A later
independently replaced server used the declared template; bounded installed
TurnExecutor file-write and grounding checks passed on both interpreters.
That separate evidence does not make this streaming walkthrough a general
card-workflow acceptance test. Keep template identity checks enabled.
