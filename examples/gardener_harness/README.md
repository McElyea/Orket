# Gardener report harness

Serve Gardener's `command` harness with the public `orket agent run` path and
the existing [SDK report example](../governed-report/README.md). The host's
`structured_report.v1` verifier checks report delivery and input references.
Findings remain advisory. No write mode, repository tool, automatic retry,
provider fallback, or new completion verifier is added.

For Gardener's separate headless extension using the generic HTTP generation API,
see [larger host prompt profiles](../../docs/specs/MODEL_GENERATION_OPTIONS.md#larger-prompts-through-the-headless-extension).
Its settings belong to the Orket API host. The command-harness submission options
below configure this source wrapper.

## Install Orket and the report extension

The full Gardener route is an opt-in report integration. Use Linux/WSL for the
Gardener CLI; native Windows wrapper tests do not establish Windows Gardener
support. Prepare Git, Python 3.11 or later, Gardener and a reachable model server.
See [Gardener's harness instructions](https://github.com/Stephenson-Software/gardener/blob/main/docs/HARNESSES.md)
for its configuration requirements. A model's presence alone does not establish
adequate context capacity or useful report quality.

In a Linux/WSL shell, choose an unused checkout path and install core and SDK
from that same checkout:

```bash
mkdir -p "$HOME/Source"
git clone https://github.com/McElyea/Orket.git "$HOME/Source/Orket"
export ORKET_SRC="$HOME/Source/Orket"
cd "$ORKET_SRC"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e "./orket_extension_sdk[testing]" -e ".[dev]"
python -m pip check
python -c "import orket; print(orket.__version__)"
command -v python orket
```

For an existing checkout, select the intended release before installing and
check its release notes. The canonical contributor install is also in
[CONTRIBUTOR.md](../../docs/CONTRIBUTOR.md#canonical-commands).

Next follow [Install the trusted example](../governed-report/README.md#install-the-trusted-example):
copy `examples/governed-report` to its own Git repository, commit it, validate
with `orket ext validate --strict`, and install from the Orket project directory.
Keep the resulting catalog path. Retain the Orket checkout: the wrapper imports
adjacent modules and uses `examples/governed-report/submission.json`. Copying
only the wrapper script is insufficient; these are not wheel entrypoints.

## Configure Gardener

Export these in the environment that launches Gardener, including scheduled runs.
The paths below match the installation recipe. Replace the model placeholder
with the exact ID served by the selected provider:

```bash
export ORKET_SRC="$HOME/Source/Orket"
export ORKET_PROJECT="$HOME/orket-gardener-project"
export GARDENER_HARNESS=command
export GARDENER_HARNESS_COMMAND="\"$ORKET_SRC/.venv/bin/python\" \"$ORKET_SRC/examples/gardener_harness/gardener_harness.py\""
export GARDENER_HARNESS_MODEL='<exact-served-model>'
export ORKET_GARDENER_CATALOG="$ORKET_PROJECT/.orket/durable/config/extensions_catalog.json"
export ORKET_GARDENER_PROVIDER=llama_cpp
export ORKET_GARDENER_PROVIDER_BASE_URL=http://127.0.0.1:8080/v1
export ORKET_GARDENER_WORK_DIR="$HOME/.orket/gardener-harness"
export ORKET_DISABLE_SANDBOX=1
export GARDENER_ALIGN_TIMEOUT=1800
```

An existing `ORKET_EXTENSIONS_CATALOG` or durable-root override can change the
installed catalog location; use that actual path. Keep the work directory outside
every target and conventions repository. Gardener supplies the report-mode spec
and dispatch timeout; these need not be hand-authored. Run `gardener doctor`, then
one deliberate report-mode `gardener align --repo owner/repo` before scheduling
a batch. Both source repositories must be clean and committed.

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

For example, with an already served Qwen model and the budget configuration below:

```bash
export ORKET_GARDENER_PROVIDER=ollama
export ORKET_GARDENER_PROVIDER_BASE_URL=http://127.0.0.1:11434
export GARDENER_HARNESS_MODEL=qwen2.5:7b
```

These endpoint examples are local to the shell's network environment. Inside
WSL, use a provider address reachable from WSL. For native Windows wrapper-only
use, substitute the environment's `Scripts/python.exe` and absolute Windows paths;
this is not a native Windows Gardener installation recipe.

## Choose evidence and budgets

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

For the compact Ollama rubric reported by Daniel, a concrete starting point is
**30000 input + 2048 output, with a 32768-token host profile**. Follow the copy,
edit and validation steps in the [host-profile guide](../../docs/specs/MODEL_GENERATION_OPTIONS.md#larger-prompts-through-the-headless-extension)
for `ollama.qwen.chatml.v1`, preserving the strict JSON output ceiling. Then set
these in Gardener's launcher environment, using the actual absolute registry path:

```bash
export ORKET_GARDENER_MAX_INPUT_TOKENS=30000
export ORKET_GARDENER_MAX_OUTPUT_TOKENS=2048
export ORKET_LOCAL_PROMPT_PROFILE_REGISTRY_PATH=/absolute/path/local_prompt_profiles.operator.json
```

The command harness starts its own Orket CLI, so it inherits this registry setting;
it does not require a separately running Orket API host. The headless extension
instead configures and restarts its API host as that guide describes.

All three bounds matter: the admission estimate must fit the requested input
limit and the host context remaining after the output reserve. The chosen model
and server must support the resulting context. Increasing only snapshot bytes,
only submission tokens or only the server's default context does not resolve the
other limits. Reduce or explicitly select complete evidence if it cannot fit.

Daniel's compact Ollama fixture estimated 26919 tokens against measured input
of 7126 (3B) or 7557 (7B). Those 3.6–3.8 ratios are observations, not a sizing
formula. Byte-based admission can refuse prompts that fit a tokenizer; native
Qwen3.8 llama.cpp uses rendered token counts. The reported 131072-token profile
for roughly 100 KB of conventions is a larger transport/budget case, not proof
that the private rubric delivered a useful audit. A 32K profile is likewise not
a promise that every repository fits.

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

## Upgrade and first-run checklist

1. Keep core/SDK, the source wrapper plus adjacent files, and the installed report
   extension on a compatible release set. Read the release notes; do not infer
   compatibility from the example manifest's version alone. A release may
   explicitly allow an unchanged earlier example, as 0.8.5/0.8.6 do for 0.8.4.
2. After selecting an updated Orket checkout, repeat its editable install and
   version/path checks. Refresh the separate example repository from that same
   checkout, review and commit changes, then repeat strict validation and
   installation from the same Orket project. Preserve any intentional local
   customizations; use a fresh example repository if replacing them is unwanted.
3. Confirm the catalog points to the newly installed commit, then launch Gardener
   with the matching wrapper. Editing the source example without reinstalling
   leaves the previously cloned implementation active.
4. Recheck provider reachability, exact model ID, registry profile, input/output
   budgets, clean source trees and work-directory placement. Keep
   `ORKET_DISABLE_SANDBOX=1` for routine proof. Start with one compact report.
5. Accept delivery only after checking the returned success and retained report.
   Use the supplied inspection command and `orket agent replay <run-id> --db
   <database> --json`; review the findings themselves before using them.

Daniel's Rev 4 field report found no default-settings Ollama delivery on his
machine through 0.8.4. Its configured 7B run delivered in 460 seconds but still
made factual/counting errors; those timings and sizing ratios are not guarantees
for other hardware or inputs. Set the timeout deliberately and expect model work
to dominate runtime. This integration remains report-only: neither successful
installation nor a passing report authorizes `tend`, edits, PRs or other write modes.
