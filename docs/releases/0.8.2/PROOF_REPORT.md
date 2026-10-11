# 0.8.2: Gardener field fixes and explicit model budgets

Date: 2026-10-10

## What changed

The field report and GitHub issues #3, #4 and #5 exposed host defects in context
selection, logging preparation and budget admission. This patch fixes those
boundaries, forwards SDK JSON schemas to providers, rejects truncated reports,
and makes snapshot coverage and model limits explicit. Contract and operator
actions are recorded in `CHANGELOG.md` and
`docs/architecture/CONTRACT_DELTA_GARDENER_FIELD_2026-10-10.md`.

Core advances to 0.8.2; SDK remains 0.8.0. Compatibility is classified as breaking
for operators and extension authors because governed Ollama now requires 0.24.0
or newer with observable context metadata. Reinstall the updated report example
and scope evidence or configure explicit host/submission budgets.

## What was verified

**Live release proof: primary / success, native Windows.** Fresh Git-visible
source produced core 0.8.2 and SDK 0.8.0 wheels in a new build tree. Installation
outside the checkout passed dependency checks, namespace/license inspection,
import-origin checks and installed package-byte comparison. All 1299 package
inputs match the prior field candidate except `pyproject.toml`; the runtime
example files also retain their field-verified hashes.

The normal extension installer admitted the copied trusted report example. The
installed Gardener wrapper ran real llama.cpp b10809/Qwen3.8 27B inference with
2742 measured input and 371 output tokens, no truncation, and matching inspection
and replay. Manual fixture review confirmed its findings: README installation
instructions were missing, while license and CI evidence were present. The model
call took 116.527 seconds; this is not a latency benchmark or reliability claim.
Both fixture repositories remained clean.

The installed wrapper refused a 256-token input limit in 7.75 seconds
(`primary / failure`, expected `E_MODEL_INPUT_BUDGET`) and a held unavailable
endpoint in 8.47 seconds (`blocked / failure`, expected
`E_AGENT_LOCAL_INVENTORY_UNAVAILABLE`). The owned Windows Job server confirmed
complete capture/cleanup and its listening port closed. The run used
`ORKET_DISABLE_SANDBOX=1`.

Machine evidence remains local and ignored at
`benchmarks/results/releases/0.8.2/package-live.json` and `package-inputs.json`,
with command logs and installed artifacts retained under
`C:/Users/jonmc/AppData/Local/Temp/orket-gardener-082-u1tmablb`.
The observed final result is `PASS / primary / success`.

- Package input digest:
  `721caffa5056665a99c5db1554aab804f51332f88b6bd2498af1d9c262c5afd5`.
- Core wheel SHA-256:
  `95dfde2ca1e0f0a7065e44a9bb220e20d236857579addbfcff6f82aec660b31f`.
- SDK wheel SHA-256:
  `20e2195aff6c82146ff0f72cd0fae11753fcaa1a9e7778685cfbd8e740a51c33`.

**Prior field verification:** 265 targeted tests passed with no failures, errors
or skips. Live installed Ollama accepted 5416 measured input tokens with explicit
32K context and no truncated receipt. Full Gardener 0.3.0 align succeeded through
Ubuntu 24.04 WSL with native llama.cpp, measured usage, matching replay, clean
fixture repositories and confirmed process teardown. That WSL route is recorded
as `fallback / success`; the Windows wrapper and Ollama routes were
`primary / success`. These runs used patched pre-release core candidates carrying
the 0.8.1 version label, not the previously shipped 0.8.1 artifact. Their exact
source identities, results and limitations remain in
[the field verification](../../architecture/GARDENER_FIELD_VERIFICATION_2026-10-10.md).

**Structural verification:** dependency direction, authority rendering/checks,
test taxonomy, touched-file Ruff and scoped typing passed at field acceptance.
Version/changelog alignment, authority rendering, documentation hygiene and
whitespace checks were repeated during release preparation. Structural authority
validation does not establish portable whole-runtime proof.

## What was not verified

The full test suite, a new coverage measurement, hosted CI, Daniel's complete
corpus/hardware, general report accuracy, write approvals or sandbox acceptance
were not verified. The full WSL/Ollama matrix was not repeated after the version
metadata change. No package-registry publication is claimed.

## Remaining blockers or drift

Native Windows Gardener 0.3.0 still imports POSIX `fcntl`; use the verified WSL
route with a provider and GGUF inventory reachable inside Linux. Small-model
reports still require human review. Broader Ruff findings and optional typing
dependency gaps are retained in the field report, rather than represented as
passing repository-wide checks. GitHub issue closure is separate from this
commit/tag publication.

## Exact files touched

The complete 45-file implementation, test, documentation and release manifest is
in [the field verification](../../architecture/GARDENER_FIELD_VERIFICATION_2026-10-10.md#exact-files-touched).
Release preparation changes `pyproject.toml`, `CHANGELOG.md`, this report, and the
field verification/contract-delta status. Runtime and test bytes remain those of
the verified field changes.
