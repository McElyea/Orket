# Apple Silicon candidate installation

Last updated: 2026-10-07

Mac support is awaiting native acceptance. These are the candidate installation
instructions for that work, not a declaration that the complete runtime works on
macOS. Native command ownership remains blocked under
`docs/specs/MACOS_LOCAL_RUNTIME_ACCEPTANCE.md`. The offline quickstart uses a mock
model; it cannot establish llama.cpp or Metal operation.

## Install a candidate

Use a native arm64 Python 3.11 interpreter and the matching core/SDK wheel pair
from the candidate evidence record. Do not install Orket into Apple's system
Python or a contributor environment. Internet access to PyPI is required for
dependencies unless an independently prepared wheelhouse is supplied.

In Terminal, check the interpreter and create a new environment:

```bash
python3.11 -c 'import platform; print(platform.system(), platform.machine(), platform.python_version())'
python3.11 -m venv "$HOME/.local/share/orket/candidates/0.7.8"
source "$HOME/.local/share/orket/candidates/0.7.8/bin/activate"
```

The platform check must print `Darwin arm64`. An `x86_64` interpreter is outside
this milestone, including when it runs through Rosetta. Choose an unused
environment directory; the example corresponds to the current source candidate.

Set these two paths to the retained wheels named in `package-install.json` and
compare their hashes with that record before installation:

```bash
SDK_WHEEL="/absolute/path/to/orket_extension_sdk-0.7.2-py3-none-any.whl"
ORKET_WHEEL="/absolute/path/to/orket-0.7.8-py3-none-any.whl"
shasum -a 256 "$SDK_WHEEL" "$ORKET_WHEEL"
python -m pip install "$SDK_WHEEL" "$ORKET_WHEEL"
python -m pip check
command -v python orket orket-quickstart
```

Both packages must come from the same candidate build. The commands must resolve
inside the environment just activated. An editable install in the source checkout
does not substitute for this path.

Create a project outside the source checkout and try the offline approval flow:

```bash
mkdir -p "$HOME/Orket Projects/First café"
cd "$HOME/Orket Projects/First café"
orket --help
orket runtime --help
orket-quickstart
```

Approve writes `quickstart_out/hello_from_orket.txt`; deny leaves the proposed file
unchanged. For a denial check, use a fresh directory so an older approved output
cannot be mistaken for a new effect. The command prints a ledger path. Verify it
with `python -m orket.quickstart.verify_ledger "<printed ledger path>"` and inspect
the actual output separately. Hash-chain validity alone does not prove an effect.

## Guided setup and diagnostics

Start a new project with the installed command:

```bash
orket setup --project "$HOME/Orket Projects/First café" --run-example
```

The wizard asks for project inputs, provider, exact served model ID, endpoint and,
for llama.cpp, the directory containing GGUF files. Choose the model your server
actually serves; the suggested model is not a fit or availability guarantee.
llama.cpp aliases must match lowercase GGUF filename stems and the admitted
prompt profile. Use the provider launch/template instructions in `docs/RUNBOOK.md`.
The wizard does not download a model or start a server.

Setup stores the model in organization `process_rules.default_llm` and provider
inputs in project `.env`, preserving unrelated dotenv content. Existing process
environment values override `.env`; setup reports the names of conflicting keys.
Organization, settings and environment writes are individually verified, not one
transaction. On failure, earlier saved files may remain. Existing organization
configuration follows the initialization service's replacement behavior; use a
new project for a first run and back up an existing project before reinitializing.

By default setup checks catalog admission and one native command. It exits
nonzero if either fails, even when project files were saved successfully.
`--skip-check` explicitly saves files without a readiness claim. `--run-example`
uses the existing offline approval demo in the chosen workspace; its model is a
fixture. Supply `--non-interactive` and `--decision approve` or `--decision deny`
for a scripted example, together with the provider/model/path flags.

Recheck from any directory without reinitializing the project:

```bash
orket doctor --project "$HOME/Orket Projects/First café"
orket doctor --project "$HOME/Orket Projects/First café" --inference --json
```

The optional inference check asks the selected model for `42` and verifies the
answer. It uses normal provider admission and prompt-template checks; it never
switches provider or selects a different model. Missing providers, wrong answers
and native ownership failures produce nonzero exits. A successful arithmetic
check establishes only that bounded inference operation. It is not the prepared
provider-backed workflow required by MA-04, a Metal observation, or full native
process acceptance. Those remain open. HTTP cancellation/close does not prove
that a remote model server stopped its own inference work.

## Prepared provider workflow

After setup and diagnostics pass, run the packaged ticket-count example:

```bash
orket demo local-agent --project "$HOME/Orket Projects/First café"
```

This uses the project's selected model for sequential planner, actor and critic
calls over two bounded iterations. The first iteration receives one ticket batch;
the second receives the other batch and the previously verified report. The
existing governed-agent verifier checks the counts and source references before
allowing completion. The expected final counts are two open, two closed and one
blocked ticket. Model statements alone cannot complete the example.

The command materializes the packaged agent template and inputs into the fresh
project directory `.orket/examples/local-agent`, retaining `agent.sqlite3` and
`report.json`. It refuses an existing destination. To run again, choose another
unused directory inside the project with `--output .orket/examples/second-run`.
Earlier files and state may remain after a failure; retain them for diagnosis.
The example does not enable effect proposals or modify user ticket data.

Inspect and replay the retained run from a new terminal without model inference:

```bash
orket agent inspect run-1 --db "$HOME/Orket Projects/First café/.orket/examples/local-agent/agent.sqlite3" --json
orket agent replay run-1 --db "$HOME/Orket Projects/First café/.orket/examples/local-agent/agent.sqlite3" --json
```

The report is a projection of the retained governed-agent state, not a second
completion authority. The workflow requires the existing native command owner
and refuses failed diagnostics. Its ten-minute request deadline, two iterations,
bounded role calls and output budgets do not establish model quality or Metal
use. The offline approval example remains a separate check. Native execution of
this prepared workflow is still required for MA-04; a Windows result cannot close it.

## Upgrades, removal and state

For an upgrade, stop active Orket processes, back up the project and retained
stores, then install the new matched pair in a new environment. Run its acceptance
checks before using retained state. Keep the previous environment available;
state compatibility and downgrade safety require the applicable release notes.

`python -m pip uninstall orket orket-extension-sdk` removes the two installed
distributions from the active environment. After deactivating it, the dedicated
environment folder can be removed separately. Dependencies and projects are not
removed by that uninstall command.

Project `config/` and `model/` directories hold project inputs; runtime durable
state defaults to `.orket/durable/`, execution output to `workspace/`, and this
quickstart's ledgers to `.orket/quickstart/runs/`. Preserve the whole project,
including hidden `.orket`, and any explicitly configured external workspace or
durable root. The detailed store authority is `docs/ARCHITECTURE.md` section 20.

## Maintainer reproduction and native runner

Use the canonical contributor environment from `docs/CONTRIBUTOR.md` to run:

```bash
python scripts/ci/verify_candidate_install.py
```

The producer copies Git-visible package inputs to a new directory outside the
checkout, builds both wheels, installs them in a fresh environment, verifies
import/distribution ownership and installed bytes, and invokes all public CLI
help surfaces. It separately checks approved/denied quickstart effects, reopens
retained ledgers in fresh processes, and rejects tampered ledgers. All command
execution uses the existing bounded native owner. No Darwin fallback is added.
It also exercises installed setup and a fresh doctor invocation, with a held
unlistened loopback port as the missing-provider control; no model inference is
claimed by that packaging campaign.

The stable reports are `.tmp/macos-support/package-install.json` and
`.tmp/macos-support/package-inputs.json`, both with rerun diff ledgers. The first
records exact commands, native settlement, logs, source identity, dependency
inventory, wheel hashes and a retained external candidate directory. That
directory contains a terminal `receipt.json` snapshot, wheels, environment, logs and example projects; collect
it with the reports before disposing of a runner. It is intentionally retained
for inspection. A failed attempt must not be published as an accepted candidate.

The manual `.gitea/workflows/macos-candidate-install.yml` job requires an authorized
native host registered with `orket-macos-arm64:host`, native `python3.11`, Git and
the Node runtime needed by checkout. Gitea's
[host runner instructions](https://docs.gitea.com/runner/1/) describe registration;
the label alone does not establish a host or authorization. Its exact command is:

```bash
python scripts/ci/verify_candidate_install.py --require-macos-arm64
python scripts/ci/verify_installed_process_acceptance.py
python scripts/ci/verify_macos_acceptance.py --llama-server "/absolute/path/to/llama-server" --model-file "/absolute/path/to/model.gguf"
```

On other platforms that command refuses before building. On macOS the unresolved
native owner currently blocks dispatch; retain that failure instead of bypassing
the owner. A successful Windows run is live Windows installed-package/quickstart
proof only. The job also invokes the combined actual-provider acceptance producer;
full MA-01 through MA-09 and Metal proof remain outstanding until native execution.

The second command consumes the passing candidate receipt and exercises native
process success/failure, cancellation, bounded capture, detached descendants and
uncertain acknowledgement. It retains `.tmp/macos-support/process-acceptance.json`
and its external test directory. The same candidate receives its core wheel's
declared dev extra for these tests, with installed-byte checks and final dependency
inventory retained. Every selected test must run; skips are not acceptance.
Its model fixture is controlled and it does not satisfy the actual-provider or
Metal cases. A Windows maintainer may exercise this component explicitly with
`--windows-control`; that flag never grants Mac acceptance.

The third command requires prepared llama.cpp/model paths, checks retained
component evidence and runs the actual guided/provider/restart cases. Its stable
report is `.tmp/macos-support/native-acceptance.json`; only all nine native cases
can produce Mac acceptance. See [the acceptance operator runbook](MACOS_ACCEPTANCE_RUNBOOK.md)
for provider preparation, the remote host proposal, Gitea inputs, artifact retrieval
and teardown. These procedures are prepared tooling, not evidence that a Mac job ran.
