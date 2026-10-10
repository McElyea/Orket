# Gardener harness

Run [gardener](https://github.com/Stephenson-Software/gardener)'s report-only
repository audits as governed Orket agent runs on a local model.

gardener chooses the work: which repository, which conventions, which prompt.
Since gardener 0.3.0 it can hand each dispatch to a configured command instead
of Claude Code (its `command` harness). `gardener_harness.py` is that command
for Orket. It turns one dispatch into one bounded `orket agent submit` run of
the `repository-audit` workload in `extension/`, and returns the verified
report.

Scope: **report mode only**. Every other gardener mode (`--implement`,
`--file-issue`, `tend`, `overnight`) is refused before Orket runs.

## How a dispatch runs

1. gardener starts the wrapper in the target repository's clone, with the
   prompt on stdin and `GARDENER_HARNESS_MODE` / `GARDENER_HARNESS_SPEC` in the
   environment.
2. The wrapper builds a bounded snapshot. It takes, in order:
   - files the prompt names (only under the clone or the spec's `add_dirs`);
   - the repository's own docs;
   - its `git ls-files` listing.

   The snapshot becomes the run's `authoritative_context`. The model gets no
   file or shell tools.
3. `orket agent submit` runs one iteration. The extension makes one brokered
   `auditor` model call and returns `{report, source_refs}` with no effect
   proposals.
4. The workload requires `agent_advisory_report_verification.v1`, so the host's
   advisory-report verifier must accept the result before the run completes:
   - exact shape;
   - sources drawn from the supplied snapshot;
   - no effects.

   The verifier checks form and provenance, not correctness; the report is
   model-assisted advice.
5. The wrapper prints gardener's JSON envelope: the report plus a footer naming
   the run, the cited sources and an `orket agent inspect` command.

## Configure gardener

Install Orket so that the `orket` CLI and `orket_extension_sdk` are available
to the Python running the wrapper. Then, in gardener's environment or
`notify.env`:

```bash
GARDENER_HARNESS=command
GARDENER_HARNESS_COMMAND="/path/to/orket-venv/bin/python /path/to/Orket/examples/gardener_harness/gardener_harness.py"
GARDENER_HARNESS_MODEL=qwen2.5-coder:32b   # an exact model your provider serves
GARDENER_ALIGN_TIMEOUT=1800
```

The wrapper reads these optional settings from the environment:

| Setting | Default | Meaning |
|---|---|---|
| `ORKET_GARDENER_PROVIDER` | `ollama` | `ollama`, `llama_cpp`, `lmstudio`, `openai_compat`, or `fixture` (deterministic, offline, never live proof) |
| `ORKET_GARDENER_PROVIDER_BASE_URL` | provider default | Passed as `--provider-base-url` |
| `ORKET_GARDENER_ORKET_BIN` | `orket` | The Orket CLI to run |
| `ORKET_GARDENER_WORK_DIR` | `~/.orket/gardener-harness` | One retained run area per dispatch (request, catalog, store, submit output) |
| `ORKET_GARDENER_MAX_TOTAL_BYTES` | `24000` | Snapshot text budget |
| `ORKET_GARDENER_MAX_FILE_BYTES` | `6000` | Per-file cap |
| `ORKET_GARDENER_MAX_FILES` | `400` | Listing entries |
| `ORKET_GARDENER_DOCS` | `README.md,CLAUDE.md,AGENTS.md,CONTRIBUTING.md,SECURITY.md` | Repository docs to include |
| `ORKET_GARDENER_MAX_INPUT_TOKENS` / `_MAX_OUTPUT_TOKENS` | `8192` / `2048` | Model profile limits |
| `ORKET_GARDENER_REPORT_WORDS` | `250` | Requested report length |

A missing model or unavailable inventory (`E_AGENT_LOCAL_MODEL_UNAVAILABLE`,
`E_AGENT_LOCAL_INVENTORY_UNAVAILABLE`) is reported with `"blocked": true`, so a
gardener overnight batch stops instead of failing every repository.

## Limits observed with small local models

These were observed with Ollama and `llama3.2:3b` on a 2 GB GPU.

- **Output cap.** The packaged `ollama.llama.inst.v1` prompt profile caps
  `strict_json` output at 512 tokens. The host uses the smaller of that cap and
  the request, so a long checklist is cut off and correctly refused
  (`model_response_contract_failed`). Hence the short opaque source references
  (`src01`, …) and the report word limit.
- **Context window.** The Ollama provider does not set `num_ctx`, so Ollama's
  own default context (4096 tokens here) applies, and a larger prompt is
  truncated. Keep `ORKET_GARDENER_MAX_TOTAL_BYTES` around 8000 for such a
  model, or raise the server's context length.
- **Quality.** A 3B model's audit is often wrong. The run proves the governed
  path, not audit quality.

## Verify

```bash
python -m pytest -q tests/integration/test_gardener_harness_example.py
orket ext validate examples/gardener_harness/extension --strict --json
```
