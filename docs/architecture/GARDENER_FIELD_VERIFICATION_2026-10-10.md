# Gardener field verification

Date: 2026-10-10 (America/Denver)
Status: Field verification for the fixes included in core 0.8.2. The original
candidate evidence below predates the version bump; release-specific evidence
is recorded in `docs/releases/0.8.2/PROOF_REPORT.md`.

## What changed

Reviewed Daniel's `V:/Downloads/orket-gardener-field-report.html` (SHA-256
`97582415561122164374909fff79596a025d911fe57b54786f703bea4145b99d`), the merged
PR #2, and all three open issues by Daniel. The supported path remains the
public SDK report workload, `orket agent run`, and `structured_report.v1`.

### Ship-risk debt

| Finding | Resolution |
| --- | --- |
| [#3: implicit Ollama context](https://github.com/McElyea/Orket/issues/3) | Explicit `num_ctx`, observed model capacity, and native non-truncation guards; unsupported servers refuse. |
| [#4: logging error masks provider loss](https://github.com/McElyea/Orket/issues/4) | Bind standalone CLI logging; query inventory at the selected endpoint; preserve typed provider failures in inspection and the wrapper. |
| [#5: capture and token budgets disagree](https://github.com/McElyea/Orket/issues/5) | Early input admission; configurable submission/capture limits; explicit host ceilings; relevant strict-report output ceilings raised from 512 to 2048. No silent input trimming or output downgrade. |
| SDK schema stopped at the broker | Forward JSON response schemas to provider structured-output fields. Give the report example section/reference constraints. Independent host verification still applies. |
| Truncated JSON could otherwise look valid | Mark truncated receipts failed and reject them in report verification. |
| Timeout amplification | One governed inference attempt; non-streaming timeouts are not retried. |

### Exploration-safe debt

The snapshot defaults now include manifests and CI/docs text, with explicit target
paths and a conventions subdirectory override. A 10,000-entry inventory supports
larger repositories; bounded prompt listings disclose unread contents and retain
the full inventory separately. Large conventions should be scoped into a complete
authored rubric. Cutting each document to an arbitrary byte prefix is not a
truthful substitute. Native Windows Gardener 0.3.0 still requires a POSIX/WSL
workaround because its CLI imports `fcntl`.

### Self-deception debt

The field report correctly distinguished non-delivery from delivered but wrong
findings. Its broader implication that remaining failures were entirely model
failures was unsupported: the host defects above were real. Conversely, a
structurally accepted report does not certify audit usefulness or factual truth.
The alternate headless extension is a separate runtime path, not evidence that
this governed SDK path passed. No new completion verifier was needed.

## What was verified

- **265 targeted tests passed**, including real Git, CLI, SDK child, SQLite,
  controlled provider HTTP, native client ownership/cancellation, prompt/runtime
  regressions, and installed-candidate evidence controls. Controlled model
  responses prove integration behavior, not live inference or report accuracy.
  Final selection/result: `.tmp/gardener-field/tests.xml` and `final-tests.log`.
- Independent host refusals still work when generation/broker schema passes
  (duplicate references and blank sections). Malformed/schema-invalid output,
  provider loss, timeouts, old Ollama guards, excessive input/output, and a valid
  JSON response marked truncated cannot produce successful completion.
- Fresh core/SDK wheels were built from Git-visible source and installed outside
  both checkouts. Installed origins, namespace ownership and package bytes were
  checked. At field acceptance, package source inputs and runtime example bytes
  matched the live candidates. Subsequent release metadata is verified separately.
- **Live, primary, success:** Windows llama.cpp b10809 with the Qwen3.8 27B Q4_K_L
  model delivered a report using 2742 input / 371 output tokens. Inspection and
  replay matched. Manual fixture review confirmed the report correctly identified
  missing README installation instructions and existing license/CI evidence.
- **Live, primary, success:** Ollama 0.24.0 / Llama 3.2 3B delivered a structurally
  accepted report using 2406 input / 162 output tokens with a 16K host context.
  Inspection/replay matched. Its prose was vague and is not accepted as evidence
  of useful audit quality.
- **Live, primary, success:** the separate long-context Ollama run used **5416
  measured input tokens** and 159 output tokens with an explicit 32K context.
  It exceeded the former 4096 default without a truncated receipt. This is a
  synthetic long-input integration control, not a production audit benchmark.
- **Live expected refusals:** the installed Ollama wrapper rejected a 256-token
  input limit in 6.7 seconds (`primary`, `failure`), and a held unlistened endpoint
  in 7.5 seconds (`blocked`, `failure`). Both retained specific causes; no report
  success or invented cost was emitted. The timing includes native Git/CLI setup.
- Owned Windows providers settled with complete capture and closed listening
  ports. Routine flows used `ORKET_DISABLE_SANDBOX=1`.

- **Live, fallback, success:** full Gardener 0.3.0 `align` ran in Ubuntu 24.04 WSL
  with a native CPU llama.cpp b10809 server and the same installed candidate.
  It used 3784 input / **548 output tokens**, correctly identified the missing
  README installation instructions, and marked the broader convention checks
  unknown. Gardener reported success in 364 seconds; inspect/replay matched.
  Both fixture repositories stayed clean. The native `linux_subreaper` confirmed
  process cleanup/capture and the listening port closed in the same execution.
  Cached Git fixtures were intentional; no GitHub fetch, issue filing or outbound
  notifications were exercised. Earlier TCP/inventory configuration failures
  remain retained failures, not successful model runs.
- **Structural checks:** dependency direction passed (4378 edges, 1237 files,
  zero violations/cycles); authority validation/rendering and documentation
  hygiene passed. Taxonomy classified all 13,419 collected tests with no errors
  or missing/invalid layers. Collection is not full-suite execution.

Evidence is local and ignored, not a published release proof:
The final audited result is `.tmp/gardener-field/acceptance.json` (`PASS`,
`fallback`, `success`). Its assertions check current package/example bytes,
retained command-log hashes, required successful phases, measured receipts,
replay, process cleanup and the 265-test result. Raw trial history remains in
`.tmp/gardener-field/verification.json`, `long-context.json`, `package-inputs.json`,
and retained candidate area
`C:/Users/jonmc/AppData/Local/Temp/orket-gardener-field-avh068s9`.
Earlier pre-schema model failures remain in
`C:/Users/jonmc/AppData/Local/Temp/orket-gardener-field-bcxva10u/receipt.json`.
The initial 0.8B response was malformed; pre-schema Llama 3.2 used the wrong
section nesting. Neither trial is counted as successful report delivery.

Package input digest:
`34ee679affce95956355b51c54f68055a286fcce732e19733b32254d340f1d55`.
Candidate core wheel SHA-256:
`bf28b886f89e5ff3a32343d523e6cbd2a14463bf80c95e6981ab309f9dd92235`.
Candidate SDK wheel SHA-256:
`097421159f7e0111b5351fc7cef83865b88d71e7b0893e71d4390cee7c10dd18`.
These field candidate version labels were 0.8.1/0.8.0; that core wheel was an
unreleased candidate, not the previously shipped 0.8.1 artifact or the final
0.8.2 candidate.

## What was not verified

No repeat of Daniel's complete ten-run corpus or performance on his hardware;
no general factual-correctness guarantee, complete 92 KiB conventions audit,
write/effect approvals, sandbox acceptance, hosted CI, or full-suite coverage run.
The real runs use authored repository/rubric fixtures. Native Windows full
Gardener CLI support is absent. Ollama's byte estimate is deliberately conservative,
not an exact tokenizer measurement or a bound for arbitrary custom templates.

## Remaining blockers or drift

- Small-model audit usefulness remains poor even with valid delivery. Keep human
  review and explicit evidence scope; do not equate successful final truth with
  factual accuracy. The tested stronger model gave useful fixture findings.
- Use a provider reachable inside WSL and explicitly configure its Linux GGUF
  inventory root. This host's Windows-to-WSL setup did not establish reverse TCP
  reachability from WSL to the Windows server.
- Repository-wide Ruff reports 1201 findings outside the touched files. Touched
  Python files pass Ruff. Unrestricted targeted mypy reaches four missing optional
  dependency/stub imports (`numpy`, `jcs`, `torch`, `diffusers`) elsewhere. The five
  changed typed modules pass with `--follow-imports=silent --ignore-missing-imports`;
  this is scoped typing evidence, not a repository-wide typing pass.
- GitHub issues were still open at field verification; no comments or issue
  closure were performed. Git publication is separate from these runtime results.

Architecture review: AC-01 through AC-10 pass for the changed boundary. Dependency
direction remains valid; policy is pure, effects retain existing owners, new
transport effects are declared, schemas do not acquire completion authority,
retained receipts replay, and contract/authority docs were updated together.
This scoped review does not close unrelated architectural debt.

Provider schema transport references:
[Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
and [llama.cpp server API](https://github.com/ggml-org/llama.cpp/blob/b10809/tools/server/README.md).

## Exact files touched

The list below is the implementation, documentation, test and release change set;
ignored local proof scripts, downloads and evidence are separate retained
verification artifacts.

- [.gitea/workflows/quality.yml](../../.gitea/workflows/quality.yml)
- [CHANGELOG.md](../../CHANGELOG.md)
- [CURRENT_AUTHORITY.md](../../CURRENT_AUTHORITY.md)
- [docs/CONTRIBUTOR.md](../../docs/CONTRIBUTOR.md)
- [docs/architecture/CONTRACT_DELTA_GARDENER_FIELD_2026-10-10.md](../../docs/architecture/CONTRACT_DELTA_GARDENER_FIELD_2026-10-10.md)
- [docs/architecture/GARDENER_FIELD_VERIFICATION_2026-10-10.md](../../docs/architecture/GARDENER_FIELD_VERIFICATION_2026-10-10.md)
- [docs/architecture/current_authority.json](../../docs/architecture/current_authority.json)
- [docs/releases/0.8.2/PROOF_REPORT.md](../../docs/releases/0.8.2/PROOF_REPORT.md)
- [docs/specs/GARDENER_REPORT_HARNESS.md](../../docs/specs/GARDENER_REPORT_HARNESS.md)
- [docs/specs/GOVERNED_AGENT_TASK_SUBMISSION.md](../../docs/specs/GOVERNED_AGENT_TASK_SUBMISSION.md)
- [docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md](../../docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md)
- [docs/specs/PROVIDER_INFERENCE_CLIENT_OWNERSHIP.md](../../docs/specs/PROVIDER_INFERENCE_CLIENT_OWNERSHIP.md)
- [examples/gardener_harness/README.md](../../examples/gardener_harness/README.md)
- [examples/gardener_harness/gardener_harness.py](../../examples/gardener_harness/gardener_harness.py)
- [examples/gardener_harness/gardener_scope.py](../../examples/gardener_harness/gardener_scope.py)
- [examples/gardener_harness/gardener_snapshot.py](../../examples/gardener_harness/gardener_snapshot.py)
- [examples/gardener_harness/gardener_submission.py](../../examples/gardener_harness/gardener_submission.py)
- [examples/governed-report/report_agent.py](../../examples/governed-report/report_agent.py)
- [orket/adapters/llm/governed_ollama_client.py](../../orket/adapters/llm/governed_ollama_client.py)
- [orket/adapters/llm/llama_cpp_render_verification.py](../../orket/adapters/llm/llama_cpp_render_verification.py)
- [orket/adapters/llm/local_model_provider.py](../../orket/adapters/llm/local_model_provider.py)
- [orket/adapters/llm/openai_compat_runtime.py](../../orket/adapters/llm/openai_compat_runtime.py)
- [orket/adapters/llm/provider_inference_client.py](../../orket/adapters/llm/provider_inference_client.py)
- [orket/application/services/governed_agent_broker_service.py](../../orket/application/services/governed_agent_broker_service.py)
- [orket/application/services/governed_agent_inspection_service.py](../../orket/application/services/governed_agent_inspection_service.py)
- [orket/application/services/governed_agent_logging.py](../../orket/application/services/governed_agent_logging.py)
- [orket/application/services/governed_agent_model_provider.py](../../orket/application/services/governed_agent_model_provider.py)
- [orket/application/services/governed_agent_report_verifier.py](../../orket/application/services/governed_agent_report_verifier.py)
- [orket/application/services/local_model_factory.py](../../orket/application/services/local_model_factory.py)
- [orket/application/services/local_prompting_service.py](../../orket/application/services/local_prompting_service.py)
- [orket/application/services/provider_inference_http_service.py](../../orket/application/services/provider_inference_http_service.py)
- [orket/core/contracts/local_prompting.py](../../orket/core/contracts/local_prompting.py)
- [orket/core/contracts/model_input_budget.py](../../orket/core/contracts/model_input_budget.py)
- [orket/interfaces/governed_agent_cli.py](../../orket/interfaces/governed_agent_cli.py)
- [orket/runtime/config/local_prompt_profiles.json](../../orket/runtime/config/local_prompt_profiles.json)
- [orket/runtime/config/provider_runtime_inventory.py](../../orket/runtime/config/provider_runtime_inventory.py)
- [orket/runtime/config/provider_runtime_target.py](../../orket/runtime/config/provider_runtime_target.py)
- [pyproject.toml](../../pyproject.toml)
- [scripts/ci/verify_candidate_install.py](../../scripts/ci/verify_candidate_install.py)
- [tests/integration/test_gardener_harness_example.py](../../tests/integration/test_gardener_harness_example.py)
- [tests/integration/test_governed_agent_provider_inputs.py](../../tests/integration/test_governed_agent_provider_inputs.py)
- [tests/integration/test_governed_agent_task.py](../../tests/integration/test_governed_agent_task.py)
- [tests/integration/test_governed_ollama_reports.py](../../tests/integration/test_governed_ollama_reports.py)
- [tests/integration/test_provider_inference_ownership.py](../../tests/integration/test_provider_inference_ownership.py)
- [tests/runtime/test_provider_runtime_target.py](../../tests/runtime/test_provider_runtime_target.py)
