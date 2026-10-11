# 0.8.4 Gardener delivery and terminal failures

Date: 2026-10-10 (America/Denver)
Core: 0.8.4; SDK: unchanged 0.8.0
Scope: GitHub #7, #8, #9 and the timeout follow-up on #6.

## What changed

- #7: the 64 KiB failure was the aggregate child-output budget, which includes
  model-call requests. Gardener now admits 1 MiB and the source report manifest
  permits it. Complete input JSON crosses bounded consecutive user messages.
  Individual materialized inputs over 262144 encoded bytes refuse explicitly.
  The existing stderr owner supplies extracted SDK failure codes without exposing
  arbitrary diagnostic text. The asyncio default reader limit was not the cause.
- #8: host-admitted report tasks retain settled timeout/connection failures as
  failed receipts with unknown usage charged at the reserved caps. Five seconds
  are reserved for receipt/terminal publication. Existing continuation authority
  closes the run `failed_terminal`, closes the failed attempt with its reason,
  and publishes unsatisfied final truth. Its result class can be `blocked` under
  the existing budget-stop priority. Failed CLI results preserve run identity and
  an inspection command. Uncertain provider failures and interrupted/general
  governed runs retain recovery semantics.
- #9: the existing host verifier admits optional section minimums/prefixes.
  Gardener requires findings plus a `GARDENER_SUMMARY:` summary. Title-only,
  blank-findings and missing-prefix deliveries cannot complete. Generic tasks
  retain the original summary-only configuration. Delivery is structural;
  factual correctness and coverage remain advisory.
- #6 follow-up: extension HTTP generation translates settled provider timeout
  and connection failures to private HTTP 504/503 error envelopes after owned
  cleanup. The original full-input fix remains in 0.8.3.
- Both Quality selections retain the new regression modules. Documentation,
  current authority, release version and migration instructions were updated.

## What was verified

Observed path: **primary**. Observed result: **success** for the scoped fixes.
Proof is **live** for the native process/HTTP/SQLite paths and actual model cases
below; governance checks are **structural**.

### Native regression controls

- 254 selected Windows tests passed (zero failures/errors/skips), then the added
  unknown-provider-error control passed: **255 distinct Windows cases**.
- The 26 Gardener cases were rerun after removing an ambient model-inventory
  dependency from the fixture. All passed. Inventory fixture bytes are explicitly
  not a model; controlled HTTP supplies these test responses.
- **9 Linux/WSL cases passed** on Ubuntu 24.04 / Python 3.12, using source runtime
  inputs. The large-input assertions compare every supplied file's full content
  at the observed provider boundary. Those three cases were rerun on each OS
  after strengthening the full-content comparison.
- Windows runs use Python 3.11. Native tests exercise actual Git, wrapper, CLI,
  SDK child, SQLite, TCP HTTP, inspection/replay and process settlement. They
  cover 67 KB, 131 KB and 500 KB captures; explicit oversized-item refusal;
  protocol-budget diagnostics; report-content rejection; timeout run identity,
  failed attempt/reason and final truth; one-attempt HTTP 504/503; and retained
  uncertain-provider recovery. Controlled HTTP does not prove model quality.
- Existing process interruption, replay, provider ownership, SDK schema and
  extension API controls remain green in the scoped selection.

Machine results are retained under `.tmp/issues789/`: `regressions.xml`,
`uncertainty.xml`, `harness-final.xml`, `wsl-final.xml`, `bytes-final.xml` and
`wsl-bytes-final.xml`, with corresponding logs. Initial failing runs are retained.
The initial WSL attempt failed because the test fixture depended on a Windows
GGUF inventory; the fixture now declares its own inventory and both reruns pass.

### Fresh installed candidate and actual Ollama

The candidate producer built fresh core/SDK wheels from 1299 Git-visible package
inputs, inspected package/license contents, installed outside the checkout, ran
`pip check` and checked installed origins/bytes. Package-input digest:
`37b6c53bdea4ea8e679f08bb5b7e420edad76f4a72a7403595be1390bdf5c355`.

| Artifact | SHA-256 |
| --- | --- |
| Core wheel 0.8.4 | `64e8f69c5f9dab9ea9a564c9b344a64c4e77e8c93ea7c1d8a270b3b2973e6295` |
| SDK wheel 0.8.0 | `1030a8ccd03fc8c495c457b7f97558b6669bf51f22cf022cd4b36cf7eced8422` |

Installed environment and first retained receipt:
`C:\Users\jonmc\AppData\Local\Temp\orket-gardener-084-eosv_mi3`.
An external trusted report Git repository was installed through the normal
extension installer. An owned CPU Ollama 0.24.0 server served `llama3.2:3b`.

| Actual observation | Result |
| --- | --- |
| Public Gardener wrapper report | Accepted required summary/findings; 835 measured input / 146 output tokens; no truncation; inspect/replay matched. |
| 93233-byte `inputs.json` | Reached native `/api/chat` beyond the former limit; one call timed out. Failed attempt retained its end timestamp and `E_AGENT_MODEL_PROVIDER_TIMEOUT`; run became `failed_terminal`, final truth unsatisfied, envelope retained run ID, replay matched. |
| Timeout accounting | Usage stayed unknown; charged 129024 input / 1024 output tokens, with no retry. |
| Second actual report attempt | Model returned invalid JSON. The host refused it, retained the run ID and terminal failure, and replay matched. This is failed inference, not a passing report. |
| Owned resources | Both Ollama process trees had confirmed Windows Job cleanup and complete capture; both listening ports closed. |

The initial producer failed **after** retaining both first-run outcomes because
its bookkeeping expected a nonexistent `size_bytes` metadata field. The retry
retains the second model's invalid-output failure; neither raw failure was erased.
An independent final audit checks actual file sizes, all command/log hashes,
package-input equality, copied example runtime bytes, failed-run inspection and
replay, teardown, and regression receipts. Its stable canonical result is
`benchmarks/results/releases/0.8.4/acceptance.json` (**PASS**). It links both raw
receipts; the second is retained at
`C:\Users\jonmc\AppData\Local\Temp\orket-gardener-084-r7ewwv_t`.
Package inputs are in `benchmarks/results/releases/0.8.4/package-inputs.json`.
These are ignored local evidence, not published benchmark claims.

### Structural checks and architecture review

Touched Python Ruff checks, scoped mypy (five application files), documentation
hygiene, release policy, generated authority equality and authority validation
passed. New tests have exactly one canonical integration layer. Dependency gate:
4382 edges / 1237 files; zero violations, cycles, unknown modules, analysis errors
or adapter-effect violations. Current authority's repository-wide live proof
remains explicitly unestablished; the structural check does not change that.

AC-01 through AC-10: **pass for this change's scope**. Dependencies retain the
interface/application boundary; no decision-node effects or new ambient decision
inputs were introduced. Existing application/broker/terminal owners retain effect
authority and supplied identities/clocks. Storage projects an existing reason
column, without a new store or event authority. Failed outcomes cannot authorize
completion; actual inspect/replay and negative controls support that claim.
Contracts, contributor retention instructions and current authority changed with
the behavior. No new Python file exceeds 400 lines; the existing 400-line broker
did not grow. No new function exceeds 70 lines.

## What was not verified

No full repository suite/coverage, hosted CI, native Mac, or new complete Gardener
CLI campaign. WSL proof here is the native wrapper path with controlled HTTP,
not installed Linux-wheel or actual Linux-model acceptance. Actual-model proof is
Windows Ollama. HTTP 504/503 mapping uses real controlled TCP failure tests; the
earlier original #6 live-input proof remains in the 0.8.3 report.

Report checks do not certify factual accuracy. The small model's accepted report
contained weak/contradictory limitations, and its second attempt was invalid JSON.
These observations do not establish reliable advisory quality. Remote inference
termination is not inferred from a client timeout; the owned proof servers were
explicitly terminated after inspection.

## Remaining blockers or drift

None blocking these issue resolutions. Refresh the trusted report source and
catalog with the wrapper to obtain the increased manifest allowance and stronger
delivery requirements. The documented structural/advisory ceiling remains.
Existing general recovery requirements and whole-repository proof gaps remain.

## Exact files touched

<!-- The complete commit manifest follows. -->

- .gitea/workflows/quality.yml
- CHANGELOG.md
- CURRENT_AUTHORITY.md
- docs/CONTRIBUTOR.md
- docs/architecture/CONTRACT_DELTA_GARDENER_DELIVERY_2026-10-10.md
- docs/architecture/current_authority.json
- docs/releases/0.8.4/PROOF_REPORT.md
- docs/specs/GARDENER_REPORT_HARNESS.md
- docs/specs/GOVERNED_AGENT_TASK_SUBMISSION.md
- docs/specs/MODEL_GENERATION_OPTIONS.md
- examples/gardener_harness/README.md
- examples/gardener_harness/gardener_harness.py
- examples/gardener_harness/gardener_snapshot.py
- examples/gardener_harness/gardener_submission.py
- examples/governed-report/extension.yaml
- examples/governed-report/report_agent.py
- orket/adapters/storage/governed_agent_repository_support.py
- orket/application/services/extension_runtime_support.py
- orket/application/services/governed_agent_broker_service.py
- orket/application/services/governed_agent_inspection_service.py
- orket/application/services/governed_agent_loop_service.py
- orket/application/services/governed_agent_model_provider.py
- orket/application/services/governed_agent_report_verifier.py
- orket/application/services/governed_agent_submission_service.py
- orket/application/services/governed_agent_terminal_service.py
- orket/core/contracts/governed_agent_ports.py
- orket/extensions/governed_agent_invoker.py
- orket/interfaces/routers/extension_runtime.py
- pyproject.toml
- tests/integration/test_extension_provider_failures.py
- tests/integration/test_gardener_delivery_regressions.py
- tests/integration/test_gardener_harness_example.py
- tests/integration/test_governed_agent_task.py
- tests/integration/test_governed_ollama_reports.py
