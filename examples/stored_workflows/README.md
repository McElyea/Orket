# Prepared stored workflows

The `standard` workflow declares, implements and verifies an integer-addition CLI.
`qa_completion_test` verifies a seeded implementation and writes a scoped handoff.
Both use declared mechanical acceptance; the QA handoff does not claim exhaustive
correctness. The preparer refuses an existing destination.

`sanity_test` is a third prepared workflow. It reads the captured organization
name and writes one exact, scoped receipt at `agent_output/sanity_receipt.md`.
Use `--workflow sanity_test` and run that epic in its own prepared directory.
The receipt proves file-writing acceptance only, not overall system health.

The fourth recipe, `challenge_workflow_runtime`, runs the twelve-card programming
challenge: requirements, design, fixtures, loader, validator, planner, simulator,
checkpoint/resume, CLI, generated tests and reporting. Prepare a new directory
with `--workflow challenge_workflow_runtime`, then run that epic with its own
durable root as below. Use the core development environment, including pytest.
Preparation seeds only the acceptance adapter; the model creates the solution.
Keep `agent_output/challenge_acceptance_runner.py` unchanged. The runtime retains
its original command/assertion checks as completion evidence. Exact requirements,
design and fixture checks prove their declared artifact shape; generated tests
and example checks do not establish correctness for every possible workflow.
For the selected 8K llama.cpp context, set `$env:ORKET_CONTEXT_WINDOW = '1'`
in the challenge's shell before `orket runtime` (or before starting its API server).
Preparation records this setting in `setup.json` and prints it; it does not change
the parent shell. It bounds repeated same-role history, while required file reads,
current instructions, acceptance and retained transcripts remain intact.

Create the Windows project `.venv` and install development dependencies using
the [runtime setup](../../README.md#full-runtime-quick-start). From the checkout,
activate that environment in each shell before preparing or running workflows:

```powershell
& C:/Source/Orket/.venv/Scripts/Activate.ps1
python examples/stored_workflows/prepare.py C:/Source/Orket-standard-demo --workflow standard --model orcarouter_qwen3.8-27b-uncensored-q4_k_l
$env:ORKET_DISABLE_SANDBOX = '1'
$env:ORKET_LLM_PROVIDER = 'llama_cpp'
$env:ORKET_LLAMA_CPP_BASE_URL = 'http://127.0.0.1:8080/v1'
$env:ORKET_DURABLE_ROOT = 'C:/Source/Orket-standard-demo/.orket/durable'
python scripts/governance/check_workflow_preflight.py --project C:/Source/Orket-standard-demo --epic standard
Set-Location C:/Source/Orket-standard-demo
orket runtime --epic standard --workspace ./workspace --model orcarouter_qwen3.8-27b-uncensored-q4_k_l
```

For QA, prepare a separate directory with `--workflow qa_completion_test`, use its
own durable root, and run that epic. Preparation seeds the correct CLI so QA has
real inputs; changing it to an incorrect implementation must refuse completion.
The generic support verifier is disabled for the three small task shapes. The
challenge keeps support verification enabled on a CLI surface. Declared
card acceptance remains mandatory. Setup and preflight are structural evidence;
runtime completion receipts establish whether the actual work was accepted.

For the API entrypoint, add `--api` during preparation. This seeds
`workspace/default` and copies the matching `server.py` into the new project.
Configure `ORKET_API_KEY`, keep that project's durable root, and start
`python server.py --host 127.0.0.1 --port 18082 --no-reload` from the project.
Submit the epic ID to `/v1/system/run-active` and follow the returned session at
`/v1/runs/{session_id}/view`; only `completion_accepted: true` establishes completion.

The model alias is the selected operator model for this Windows proof. Supply your
selected alias explicitly for another installation. These commands do not start,
restart or own the model server. Keep one inference run at a time on a one-slot
server. Adapt the card notes, inputs and acceptance together for other real work.
