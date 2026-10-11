# 0.8.6: Gardener Rev 3 and host context guidance

Date: 2026-10-10 (America/Denver)
Status: Scoped verification complete.

## What changed

Reviewed `V:/Downloads/orket-gardener-field-report (2).html`, SHA-256
`f643f3f5d5f32107fb8ce7d03fbbecf353aa28d196d1b52624c2c67c0cebed9b`.
Its Rev 3 tests core 0.8.4. Cross-checked the published
[Gardener PR #192](https://github.com/Stephenson-Software/gardener/pull/192)
and its verification record; the PR is merged at `96d7db7e`.
The report independently confirms #6–#9; all remain closed and GitHub had no
additional open Orket issues during this review.

### Ship-risk debt

No new admission or delivery defect was reported. The default 8192-token host
profile correctly refuses the headless extension's larger prompt plus output
reserve. The existing explicit larger profile works. Increasing the global
default would impose additional memory/context requirements on other users.

The remaining operator feedback is addressed by naming
`ORKET_LOCAL_PROMPT_PROFILE_REGISTRY_PATH` and `context_budget_tokens` directly
in the conservative budget error and documenting the complete configuration
recipe. It selects a matching operator-owned profile in the **API host**, then
restarts that host. Gardener client settings and command-harness limits do not
reconfigure it. Runbook and harness README link to one canonical guide.
Limits, defaults, transport and error codes remain unchanged; SDK 0.8.0 is
compatible. [Contract delta](../../architecture/CONTRACT_DELTA_HOST_PROFILE_GUIDANCE_2026-10-10.md).

### Exploration-safe debt

Rev 3's request for a model above 7B predates the completed local 27B campaign.
The [0.8.5 proof](../0.8.5/PROOF_REPORT.md) records actual native CPU llama.cpp
inference through Gardener in WSL, delivered report, measured tokens, matching
replay and owned server teardown. That campaign used Gardener 0.4.2; this review
does not relabel it as a run of the newer 0.4.3/PR #192 suite.

### Self-deception debt

Daniel's 7B report still missed supplied README evidence and miscounted gaps.
Our actual 27B report also miscounted six listed gaps as seven. Larger models
can produce useful advisory findings without making those findings reliably
true. Structural delivery checks, a valid registry and a larger context are
not semantic audit acceptance. Human review remains necessary.

## What was verified

**Live API integration controls: primary / success.** On native Windows,
`test_extension_ollama_input_budget.py` passed **16 tests** in 12.43 seconds.
For both the host default model and an explicit request override, the same
approximately 16.8 KB user message is refused with HTTP 400 at 8192 context
without `/api/chat`, then sent exactly once with complete system/user content
at 32768. The observed request preserves the output budget, `num_ctx=32768`,
`truncate=false` and `shift=false`. The real TCP API/SDK path also exposes the
new diagnostic fields and settles its owned provider resources. The refusal
is an expected product failure; proof acceptance is success.

The provider HTTP responses are synthetic, so these are integration controls,
not fresh model-inference proof. The small-output request fixture produces
17 expected SDK warning instances about limits below 256; no tests skip.
`test_governed_ollama_reports.py` passed **10 tests** in 25.75 seconds, retaining
full-input, pre-generation refusal, timeout, truncation and recovery controls.
Both modules already occur in both Quality workflow selections.

**Installed operator-command check: primary / success.** The exact Python
copy and schema-validation commands ran outside the checkout using the retained
0.8.5 installed environment. The copied registry matched current packaged bytes;
both documented Qwen/Llama profile IDs resolved with the edited 32768 context.
The PowerShell absolute-path assignment returned the actual file. This checks
the recipe against unchanged registry/loader code, not a fresh 0.8.6 installation
or model capacity. An initial proof observer failed after all commands succeeded
because it passed captured bytes to `Path`; it was corrected to decode stdout.
The failed receipt remains in the diff ledger and is not a product failure.

The merged headless-extension PR #2 at `49f2c80f` admits only a restricted
diagnostic character set and at most 400 characters. The final 290-character
representative budget error matches that upstream regex and preserves the
setting name. This is structural compatibility against the retrieved source,
not a new full extension-dispatch run. An apostrophe in the initial draft was
removed before publication so the extension would retain the guidance.

Supporting evidence:

- `.tmp/gardener-rev3/api-context.xml` and `api-context.log`.
- `.tmp/gardener-rev3/governed.xml` and `governed.log`.
- `.tmp/gardener-rev3/final-regressions.xml` and `final-regressions.log` retain
  the combined 26-case pass after the final diagnostic wording adjustment.
- `.tmp/gardener-rev3/guide.json`: stable receipt using the shared diff ledger.
  Successful retained area:
  `C:/Users/jonmc/AppData/Local/Temp/orket-gardener-rev3-guide-eb84mpx1`.
  The prior observer failure remains under `orket-gardener-rev3-guide-ssi9854f`.

**Structural:** touched Python Ruff, strict taxonomy (16 integration cases),
dependency direction, authority render/check, project docs hygiene, release
policy and whitespace checks passed. AC-01 through AC-10 pass within this
diagnostic/documentation scope: no new runtime ownership, I/O, authority or
completion behavior. The source contract and generated authority agree.

## What was not verified

No new actual inference, full Orket suite/coverage, hosted CI, native Mac,
native Windows Gardener, private corpus, model-quality guarantee or fresh
0.8.6 package installation. Historical model/timing claims in Daniel's report
were not independently rerun. The prior larger-model campaign remains evidence
for its recorded candidate only. No package-registry publication is claimed.

## Remaining blockers or drift

No unresolved defect from Rev 3's operator feedback remains. Model-quality
limitations persist; context changes require explicit operator sizing. The
global authority snapshot still does not claim whole-runtime live acceptance.
No roadmap lane was opened or retired by this scoped follow-up.

## Exact files touched

- `CHANGELOG.md`
- `CURRENT_AUTHORITY.md`
- `docs/RUNBOOK.md`
- `docs/architecture/CONTRACT_DELTA_HOST_PROFILE_GUIDANCE_2026-10-10.md`
- `docs/architecture/current_authority.json`
- `docs/releases/0.8.6/PROOF_REPORT.md`
- `docs/specs/MODEL_GENERATION_OPTIONS.md`
- `examples/gardener_harness/README.md`
- `orket/core/contracts/model_input_budget.py`
- `pyproject.toml`
- `tests/integration/test_extension_ollama_input_budget.py`
