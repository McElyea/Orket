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
provider fails with `blocked: true`.

Only `report` with plan permissions, Read/Grep/Glob, no allowed commands and
`merge_allowed: false` is accepted. Every `add_dirs` entry must be a directory
inside a clean, committed Git repository. The target must also be clean. The
snapshot includes named tracked target files, standard root documentation and
all tracked files within each extra directory. Use narrowly scoped convention
directories. File content comes from immutable Git blob IDs; symlinks, submodules,
non-UTF-8/binary selected files, failed discovery and exceeded limits refuse
before the model runs. Untracked and ignored content is never model input.

Limits are 1,000 inventory entries per selected tree, 128 text documents,
16 KiB per document, 64 KiB document content, 64 KiB prompt, eight extra
directories, and a 30–3,600 second dispatch timeout. Oversized required evidence
is refused, not silently truncated. The model may impose a smaller context or
output limit and refuse the report. Source state is checked again after the run.

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
