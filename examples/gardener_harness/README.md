# Gardener report harness

Serve Gardener's `command` harness with the public `orket agent run` path and
the existing [SDK report example](../governed-report/README.md). The host's
`structured_report.v1` verifier checks report delivery and input references.
Findings remain advisory. No write mode, repository tool, automatic retry,
provider fallback, or new completion verifier is added.

First install the trusted report example through the normal extension installer,
as described in its README. Retain this source checkout for the wrapper and its
adjacent submission template; the examples are not installed wheel entrypoints.
Use the Python environment containing the installed core and SDK.

Configure Gardener's environment, using absolute paths:

```text
GARDENER_HARNESS=command
GARDENER_HARNESS_COMMAND="C:/path/to/venv/Scripts/python.exe" "C:/Source/Orket/examples/gardener_harness/gardener_harness.py"
GARDENER_HARNESS_MODEL=<exact-served-model>
ORKET_GARDENER_CATALOG=C:/path/to/project/.orket/durable/config/extensions_catalog.json
ORKET_GARDENER_PROVIDER_BASE_URL=http://127.0.0.1:8080/v1
GARDENER_ALIGN_TIMEOUT=1800
```

For POSIX, substitute the environment's `bin/python` and source/catalog paths.
`ORKET_GARDENER_PROVIDER` defaults to the canonical `llama_cpp`; supported
alternatives require explicit selection. `ORKET_GARDENER_WORK_DIR` defaults to
`~/.orket/gardener-harness` and must be outside every source repository. The
wrapper starts the installed module with its own Python, so it cannot silently
select an unrelated `orket` executable from PATH. A missing model or unavailable
provider, or an inference timeout, fails with `blocked: true`.
For Ollama explicitly set `ORKET_GARDENER_PROVIDER=ollama` and the native base
URL (without `/v1`). Governed Ollama requires version 0.24.0 or later for its
non-truncating request guards. The selected HTTP endpoint supplies model inventory;
an unrelated local Ollama CLI installation is not required.

Only `report` with plan permissions, Read/Grep/Glob, no allowed commands and
`merge_allowed: false` is accepted. Every `add_dirs` entry must be a directory
inside a clean, committed Git repository. The target must also be clean. The
snapshot includes named tracked target files, standard root documentation,
manifests, text files in `docs/`, `.github/` and `.gitea/`, and all tracked files
within each selected extra directory. Use narrowly scoped convention
directories. File content comes from immutable Git blob IDs; symlinks, submodules,
non-UTF-8/binary selected files, failed discovery and exceeded limits refuse
before the model runs. Untracked and ignored content is never model input.

Limits are 10,000 inventory entries per selected tree, 128 text documents,
16 KiB per document, 64 KiB document content, 64 KiB prompt, eight extra
directories, and a 30–3,600 second dispatch timeout. Oversized required evidence
is refused, not silently truncated. Source state is checked again after the run.

For a large repository, explicitly choose the files to inspect, for example:

```text
ORKET_GARDENER_TARGET_PATHS=["README.md","pyproject.toml",".github/workflows"]
ORKET_GARDENER_CONVENTIONS_SUBDIR=review-rubric
ORKET_GARDENER_MAX_INPUT_TOKENS=8192
ORKET_GARDENER_MAX_OUTPUT_TOKENS=2048
ORKET_GARDENER_MAX_FILE_BYTES=16384
ORKET_GARDENER_MAX_SNAPSHOT_BYTES=65536
```

Target paths replace the default selection; they are literal relative paths,
not globs. The conventions subdirectory applies inside each `add_dirs` root.
Commit a complete, smaller rubric there. Raising byte limits (at most 524288)
does not raise token capacity. Submission token ranges are 256..131072 input
and 64..8192 output, still bounded by the selected host profile and model.
`ORKET_LOCAL_PROMPT_PROFILE_REGISTRY_PATH` can select an operator-authored copy
of the packaged `orket/runtime/config/local_prompt_profiles.json`: increase
the chosen profile's `context_budget_tokens` and
`sampling_bundles.strict_json.max_output_tokens`
only within your model/server capacity. The packaged relevant Qwen and Llama
strict-report output ceilings are 2048; requests above a ceiling now refuse
with `E_MODEL_OUTPUT_LIMIT` instead of silently lowering it.

`E_MODEL_INPUT_BUDGET` means reduce selected evidence or explicitly enlarge both
submission and host capacity. Native Qwen3.8 llama.cpp uses rendered token counts;
other admitted profiles use a conservative UTF-8 byte estimate with message
overhead, which may refuse text that would fit a tokenizer. It is not a measured
token count. Ollama receives an explicit `num_ctx`, `truncate: false` and
`shift: false`; no implicit retry follows a timeout. Inspection retains specific
model failure reasons even when the terminal policy reason is more general.

Each run retains `snapshot-inventory.json`. For trees larger than 128 entries,
the model sees a bounded listing, selected content, coverage counts and the full
inventory digest. Names prove presence; uninspected content remains unknown.
Full Gardener 0.3.0–0.4.2 `align` needs POSIX/WSL because of its `fcntl` imports;
the Windows wrapper alone does not establish native Windows CLI support.
Inside WSL, use Linux paths throughout and a provider reachable from that
environment. For llama.cpp, set `ORKET_LLAMA_CPP_GGUF_MODEL_ROOT` to the Linux
path containing the GGUF files (for example `/mnt/d/Models/GGUF`); a Windows
drive-letter default is not a valid Linux inventory root.

Each dispatch retains its input JSON files and SQLite evidence in a private
run directory. The result footer supplies the run ID, database and inspection
command. Inspect or replay retained evidence before deliberately retrying a
failed or interrupted run; rerunning creates a new run. No cost is invented.

The command owner confirms process-tree cleanup and complete capture before
accepting output. This is trusted local extension execution, not an OS sandbox
for hostile Python or a guarantee of arbitrary audit correctness. The durable
boundary and verification requirements are in
[Gardener Report Harness](../../docs/specs/GARDENER_REPORT_HARNESS.md).

```text
python -m pytest -q tests/integration/test_gardener_harness_example.py
```

Adapted from Daniel McCoy Stephenson's Orket PR #2 and Gardener's released
command-harness proposal; contribution terms are Apache-2.0.

## Delivery and failure inspection

Gardener requires a `summary` of at least 40 trimmed characters starting with
`GARDENER_SUMMARY:` and `findings` of at least 80 trimmed characters. Findings
should identify checks, evidence or unknown coverage, and suggested actions.
The host verifies delivery structure; factual findings remain advisory.

One materialized input may not exceed 262144 encoded bytes; larger individual
files refuse before dispatch. Total capture may reach 524288 bytes across
multiple inputs. The complete prompt travels in consecutive message chunks,
under a 1 MiB aggregate child-output budget and the independent wire-frame cap.
These bounds do not enlarge model context or authorize input truncation.

Failures with a retained CLI run identity return that ID and the exact inspection
command, including wrapper refusals after a source change. In that case the
stored snapshot report can be accepted while Gardener delivery is refused;
inspection describes the captured snapshot, not the subsequently edited tree.
Model calls
reserve five seconds for failed-receipt delivery and terminal publication.
Settled report-only timeouts/unavailability retain unknown token usage, charge
the reserved budget, and close unsatisfied through the existing stop policy.
Inspect the failed attempt and receipt for the provider error code. No retry or
remote-inference termination is implied.
