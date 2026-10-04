# Four-card bug-fix example

This Windows example creates an isolated small Python project with a deliberately
seeded whitespace-normalization bug. Orket writes regression tests, repairs the
function, verifies the tests and records a review through four dependent cards.
It uses the existing local llama.cpp server; no paid API or model download is needed.
It is a working example of bounded coding work, not a fix to an existing Orket bug.

| Card | Work | Required completion evidence |
| --- | --- | --- |
| BF-01 | Write regression tests | At least six tests run; baseline rejected without test errors |
| BF-02 | Repair the JSON CLI | Nine operator-declared input/output cases pass |
| BF-03 | Verify the repaired program | Existing and new tests pass, at least eight total |
| BF-04 | Inspect and record a review | Tests still pass and the declared review artifact matches |

The model has read/write/status tools, not a shell tool. Declared
[`card_python_cli_acceptance.v1`](../../docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md)
executes the actual CLI and test suite before accepting completion. The review
artifact alone is not proof. The original baseline is retained so BF-01's evidence
remains meaningful after the repair.

## Prepare and run on this machine

Run this block in PowerShell. The interpreter below is the existing matched
installed Orket/SDK 0.7.2 environment used for the observed run. On another Windows
installation, select a configured interpreter following the repository
[installation guide](../../README.md) and retain the selected provider/model.
The target project directory must be new; preparation refuses to overwrite it.

```powershell
$orketPython = 'C:\Users\jonmc\AppData\Local\Temp\orket-prr-v1\final-packages-r02-py311\Scripts\python.exe'
$orketCommand = Join-Path (Split-Path $orketPython) 'orket.exe'
$project = 'C:\Source\Orket-bugfix-next'
Set-Location C:\Source\Orket
& $orketPython examples/bug_fix/prepare.py $project
if ($LASTEXITCODE -ne 0) { throw 'Project preparation failed' }

$env:ORKET_DISABLE_SANDBOX = '1'
$env:ORKET_DISABLE_RUNTIME_VERIFIER = '1'
$env:ORKET_LLM_PROVIDER = 'llama_cpp'
$env:ORKET_LLAMA_CPP_BASE_URL = 'http://127.0.0.1:8080/v1'
$env:ORKET_LLM_LLAMA_CPP_BASE_URL = 'http://127.0.0.1:8080/v1'
$env:ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL = '0'
$env:ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL = '0'
$env:ORKET_MODULE_PROFILE = 'developer-local'
$env:ORKET_DURABLE_ROOT = Join-Path $project '.orket\durable'
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
Set-Location $project
& $orketCommand runtime --epic bug_fix --workspace "$project\workspace" --build-id run-01 --model orcarouter_qwen3.8-27b-uncensored-q4_k_l
if ($LASTEXITCODE -ne 0) { throw 'Orket run failed; retain its logs before retrying' }
& $orketPython -I -B "$project\workspace\agent_output\verify.py" tests
& $orketPython -I -B "$project\workspace\agent_output\verify.py" review
```

The last two commands report JSON booleans; require all fields to be `true`.
Check `workspace/runs/<run-id>/run_summary.json` for `status: done` and
`stop_reason: completed`, and retain the card receipts in `.orket/durable/db/`.
Do not infer acceptance merely from a model message or an exit code. The generic
support verifier is disabled because it assumes a different application shape;
each card's explicit completion acceptance remains enabled.

The invocation directory selects the project; `--workspace` selects output only.
The generated board, settings, databases and artifacts belong to this project.
Preparation does not edit the checkout's operator board. The server is
operator-owned and must already be running with the selected model; this example
does not start, stop or change it. Use a new project directory for each fresh run.

## Observed run, October 4, 2026

Project: `C:\Source\Orket-bugfix-demo`; run ID: `b50f60cc`; build ID: `run-01`.
The installed 0.7.2 core/SDK pair executed all four cards on Windows using
`orcarouter_qwen3.8-27b-uncensored-q4_k_l` through llama.cpp. The epic completed
in 213.175 seconds. Path: `primary`; workload result: `success`.

Orket authored six regression tests and changed the implementation to trim and
collapse whitespace before lowercasing. The original baseline failed all six
regressions; the repaired implementation passed the two existing tests, six new
tests and nine declared oracle cases. All four retained completion receipts were
accepted. The frozen verifier, baseline, requirements and existing tests remained
unchanged during the model run. Local setup settings and board adoption were
updated by the runtime as expected.

The eight role turns each needed a corrective prompt. The runtime reports
`is_degraded: false` and no provider fallback, but its truth packet classifies
the run as `repaired` and `non_conformant`, with `silent_repaired_success`.
That warning remains unresolved; successful workload acceptance does not clear it.
BF-01 and BF-04 also retain expected pre-work missing-artifact observations.
No failed observation or model attempt was deleted.

Local evidence is retained in the checkout's `.tmp/bug-fix/run-01/state.json`
(native command ownership, logs, installed identity and frozen input hashes),
`.tmp/bug-fix/inspection.json` (validated completion receipts), and
`.tmp/bug-fix/verify-01/state.json` (final template checks and independent execution).
The original project's `setup.json`, `workspace/orket.log`, per-turn
`workspace/observability/b50f60cc/` and durable databases retain the exact run.
Afterward, import ordering was corrected in the reusable templates; a separately
prepared project exercised those final verifier/test bytes against the retained
model outputs without another inference run.

## Reuse for real work

Use [workflow.py](workflow.py) as the four-stage card pattern and replace the
seed, requirements and acceptance cases with one bounded task. Keep the baseline
and operator-owned checks separate from the files the model is asked to change.
Review generated tests as well as their result. BF-01 currently requires at least
one failing baseline regression, not proof that every generated assertion is
meaningful. The observed run's six tests were inspected and each failed against
the baseline, then passed against the repair.

The nine fixed cases establish only their declared behavior. They do not prove
arbitrary repository repair, broad review quality, repeatability, performance,
other providers or other operating systems. This trusted local execution is not
hostile-code containment. The workflow and task-specific acceptance inputs live
here; runtime authority remains in the existing contracts and implementation.
