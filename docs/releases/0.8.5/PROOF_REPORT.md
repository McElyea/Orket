# 0.8.5: Gardener Rev 2 review and source-refusal inspection

Date: 2026-10-10 (America/Denver)
Status: Scoped verification complete.

## What changed

Reviewed `V:/Downloads/orket-gardener-field-report (1).html`, SHA-256
`7103a246e385a4bdcfb8d3274069b109cca5ad58077ca80b1f24ca12e91a70c8`.
Rev 2 tested core 0.8.2; its newly filed issues are #6–#9, already resolved in
0.8.3/0.8.4. GitHub had no additional open issues during this review.

### Ship-risk debt

| Report finding | Resolution and proof |
| --- | --- |
| #3–#5: context, unavailable providers and model budgets | Fixed in 0.8.2; [original field verification](../../architecture/GARDENER_FIELD_VERIFICATION_2026-10-10.md). Rev 2 independently confirms these fixes. |
| #6: generic SDK/API silent input loss and HTTP 500 on timeout | Full-input admission in 0.8.3; typed HTTP 504/503 failures in 0.8.4. [Input proof](../0.8.3/PROOF_REPORT.md), [failure proof](../0.8.4/PROOF_REPORT.md). |
| #7: larger inputs disconnect at about 64 KiB | Fixed aggregate child-output admission, bounded complete message transport and typed input/protocol refusals in 0.8.4. Its proof includes native Windows/WSL full-content comparisons and actual large-input Ollama dispatch. |
| #8: timeout has no terminal truth or run identity | Settled report-only provider failures close with unknown usage and an inspectable run in 0.8.4. General execution uncertainty retains its recovery requirements. |
| #9: title-only reports pass | The 0.8.4 Gardener contract requires findings and a prefixed summary with minimum lengths. Delivery verification does not establish factual correctness. |
| Additional reproduced gap: post-model source refusal loses the run identity | Fixed here. The wrapper preserves the CLI identity through its report/source checks and includes the inspection command in the refusal. It does not rewrite an accepted captured-snapshot outcome. |
| Upstream integration-suite mismatch: native input-budget refusal omits the non-truncation statement | The actual llama.cpp call correctly refused before generation, but the expected diagnostic text was absent. The native error now explicitly states `input was not truncated`. Limits and admission behavior are unchanged. |

The last row failed its added native regression before the change with
`session_id: null`. The updated wrapper preserves blocking classifications and
refuses successful CLI payloads that omit their identity. Contract delta:
[source-refusal inspection](../../architecture/CONTRACT_DELTA_GARDENER_SOURCE_REFUSAL_2026-10-10.md).

### Exploration-safe debt

The report's optional placeholder-reference feedback was already addressed in
0.8.2: prompts and generation schemas use the actual supplied references. Snapshot
limits and subdirectory selection were already configurable; individual encoded
input, aggregate transport and model-context limits remain independent.

Gardener's upstream CLI still uses POSIX `fcntl` through 0.4.2. WSL is the tested
full-dispatch route; native Windows Orket/wrapper acceptance does not establish
native Windows Gardener support. The local Gardener checkout was fast-forwarded
to upstream `f322982` (0.4.2), including the new integration suite and its timeout/
signal cleanup fixes. No Gardener source modifications were made.

### Self-deception debt

A real Qwen3.8 27B report correctly identified missing test instructions,
contributing documentation, CLAUDE.md, CODEOWNERS, issue templates and CI in the
fixture. Its summary nevertheless said seven gaps while the findings described
six. It also did not explicitly mark the supplied README run command as passing.
This is useful advisory content, not complete or reliably counted audit truth.
No new semantic-accuracy guarantee or automatic fix execution is claimed.

## What was verified

- **Live integration controls:** 26 selected native Windows tests passed
  (`test_gardener_harness_example.py` and `test_gardener_delivery_regressions.py`).
  The changed source-refusal case also passed in WSL. These exercise real Git,
  CLI/SDK child processes, SQLite, controlled provider HTTP, inspection and replay.
  Controlled model responses are not actual inference proof.
- **Structural:** touched-file Ruff, taxonomy for all 17 harness-module cases,
  authority rendering/validation and documentation hygiene passed. Dependency
  direction passed: 4382 edges, 1237 files, no violations, unknown modules,
  analysis errors, authority cycles or adapter-effect violations.
- The native render/ownership selection passed 12 cases after the diagnostic
  fix. The new native-budget contract case failed before the change on the exact
  missing phrase. Its mocked HTTP proof is distinct from the live upstream case.

### Actual larger-model baseline

Fresh installed core 0.8.4/SDK 0.8.0 and upstream Gardener 0.4.2 (`f322982`)
ran 33 upstream tests in WSL Ubuntu 24.04/Python 3.12 with native CPU llama.cpp
b10809 and Qwen3.8 27B Q4_K_L. **32 passed, one failed**: the native input-budget
error lacked the non-truncation phrase. Both actual-model cases passed: delivered
report with matching replay, and outward refusal after source mutation. The
baseline's `FAIL` receipt is retained; this review does not turn that suite run
into a pass. The mutation envelope also independently reproduced the missing
run ID fixed here. The owned server confirmed complete capture/cleanup and a
closed port. Routine proof used `ORKET_DISABLE_SANDBOX=1`.
The delivery call measured 5822 input / 518 output tokens (548.9 seconds for the
wrapper); the mutation call measured 5698 / 633 (560.616 seconds).

Baseline artifacts are retained under
`C:/Users/jonmc/AppData/Local/Temp/orket-gardener-rev2-ke04oatv`; the stable ignored
receipt is `.tmp/gardener-rev2/acceptance.json`. The live delivery used the upstream
fixture, not Daniel's private corpus or public LC-3 repository. Its six listed
gaps and incorrect seven-gap summary were reviewed against supplied evidence.

### Fresh release installation

Core 0.8.5 and SDK 0.8.0 were built from fresh Git-visible sources and installed
outside the checkout. Windows and WSL dependency, namespace/license, import-origin
and installed-package-byte checks passed. Of 1299 package inputs, exactly two
differ from 0.8.4: core version metadata and the native diagnostic message.
The source wrapper is separately copied and normally installs its trusted report
example; it is not a wheel entrypoint.

- Package-input digest:
  `feb0b2773b91a2159a0a59ac4552a78b30a4c16f72ff6ed41ae43399ed5d3730`.
- Core wheel SHA-256:
  `7341b456340346d3cf0ccded95247a23f1839b25fdfc6dd58b9570eaf54e02f7`.
- SDK wheel SHA-256:
  `672777756ef31067db22fd3664004d1fb45a3a46c93b34c40f028b00de1d9e60`.

The Windows build/install artifacts are under
`C:/Users/jonmc/AppData/Local/Temp/orket-gardener-085-zr074n2c`; receipts and exact
input hashes are `.tmp/gardener-rev2/package-install.json` and `package-inputs.json`.
The fresh WSL installation is in `/tmp/orket-gardener-source-refusal-ss5o1kqk-venv`.

### Final live follow-up

**Live verification: fallback / success.** Fresh installed 0.8.5, the updated
source wrapper and Gardener 0.4.2 passed all 32 selected upstream cases in 477.271
seconds: 23 offline controls, eight refusals and one actual-model source-mutation
case. The complete `compact/` fixture rubric and an 8192-token native server
context were used; source documents were not truncated. This final selection
does not repeat the baseline's separate successful outward-delivery case.

The 27B call used **4004 measured input / 405 output tokens**, finished normally
without truncation, and reported 370344 ms latency. Gardener refused delivery
after the intentional README edit (**fallback / failure, expected**) and returned
`orket:agent-run:8b4868b1a8a3480697c27cc2d0aa21fd` plus its exact inspect command.
The original captured-snapshot outcome remained `completion_satisfied` and replay
matched. This is the intended separation between snapshot acceptance and later
source stability, not a claim that the edited tree was accepted.

The native input-budget control reported 5782 rendered tokens against its 256
limit, explicitly stated `input was not truncated`, retained a failed zero-token
receipt and replayed successfully. Input/output refusals did not generate model
tokens. The owned provider confirmed capture/cleanup and its listening port
closed. Full runtime proof remains bounded to this report-only path.

Artifacts are under
`C:/Users/jonmc/AppData/Local/Temp/orket-gardener-source-refusal-ss5o1kqk`; the stable
ignored receipt is `.tmp/gardener-rev2/source-refusal.json`. The final independent
audit, `.tmp/gardener-rev2/final-acceptance.json`, passed with retained source/
example hashes, command-log hashes, test results, baseline/final outcome checks,
fresh baseline inspection/replay and provider cleanup. Its retained area is
`C:/Users/jonmc/AppData/Local/Temp/orket-gardener-rev2-audit-oydlu2h2`.

An initial audit attempt held a Windows SQLite reader open during Linux
inspection and failed. The observer now closes that handle before inspection;
the same unchanged retained runs then inspected and replayed successfully. The
failed audit remains under `orket-gardener-rev2-audit-to4q1dq2`, with ledger history.
It is not counted as a passing audit or hidden as a product success.

AC-01 through AC-10: **pass for this change's scope**. Existing owners, dependency
direction, explicit inputs, terminal authority and replay are retained. The
wrapper only enriches its failure envelope; the adapter only clarifies a refusal
message. No new blocking runtime I/O or oversized committed functions/files were
introduced. Source contracts and the generated authority view changed together.

## What was not verified

No full Orket test suite/coverage, hosted CI, native Mac, native Windows Gardener,
Daniel's private conventions or hardware, or general audit-quality guarantee.
The review does not independently reproduce every historical timing or model
answer in the HTML report. The earlier SDK/API/Ollama proofs remain scoped to
their recorded candidates; this follow-up does not rerun that entire matrix.
No package-registry publication, write-mode approval or sandbox acceptance claim.

## Remaining blockers or drift

The reproduced integration defects are resolved. Reports remain advisory; human
review is required for findings and counts. Use WSL for full Gardener dispatch and keep
the trusted 0.8.4 report extension/catalog with the updated source wrapper.
Repository-wide current runtime proof remains unestablished; passing structural
authority checks does not change that posture.

## Exact files touched

- `CHANGELOG.md`
- `CURRENT_AUTHORITY.md`
- `docs/architecture/CONTRACT_DELTA_GARDENER_SOURCE_REFUSAL_2026-10-10.md`
- `docs/architecture/current_authority.json`
- `docs/releases/0.8.5/PROOF_REPORT.md`
- `docs/specs/GARDENER_REPORT_HARNESS.md`
- `docs/specs/GOVERNED_AGENT_TASK_SUBMISSION.md`
- `examples/gardener_harness/README.md`
- `examples/gardener_harness/gardener_harness.py`
- `orket/adapters/llm/llama_cpp_render_verification.py`
- `pyproject.toml`
- `tests/adapters/test_llama_cpp_render_verification.py`
- `tests/integration/test_gardener_harness_example.py`
