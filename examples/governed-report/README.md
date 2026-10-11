# Governed advisory report example

This workload imports only `orket_extension_sdk`. It asks one selected model to
compare supplied sample documents and returns a structured advisory report.
It does not inspect your checkout. The host verifies delivery and source refs;
it does not certify the findings.

## Install the trusted example

The installer clones a Git repository and reads `extension.yaml` at its root.
An uncommitted directory, or the whole Orket repository with this example nested
inside it, is not the installation source. The installed checkout is separate
from your example source; editing the source alone does not update the catalog.

With Orket and its matching SDK installed, prepare a new example repository.
This Bash recipe is suitable for Linux/WSL; use absolute paths and an unused
`REPORT_REPO` directory. Run Git commits with your configured author identity:

```bash
export ORKET_SRC="$HOME/Source/Orket"
export REPORT_REPO="$HOME/Source/orket-governed-report"
export ORKET_PROJECT="$HOME/orket-gardener-project"
mkdir -p "$REPORT_REPO" "$ORKET_PROJECT"
cp -R "$ORKET_SRC/examples/governed-report/." "$REPORT_REPO/"
git -C "$REPORT_REPO" init
git -C "$REPORT_REPO" add extension.yaml report_agent.py inputs.json submission.json README.md
git -C "$REPORT_REPO" commit -m "Install trusted Orket report example"
cd "$ORKET_PROJECT"
export ORKET_DISABLE_SANDBOX=1
orket ext validate "$REPORT_REPO" --strict --json
orket runtime extensions install "$REPORT_REPO"
orket runtime extensions list
```

Check validation/install success and that the installed record is
`example.structured-report`. Unless overridden, this project now has
`.orket/durable/config/extensions_catalog.json`. Install and run with the same
selected environment. To run the example's sample documents directly:

```text
orket agent run --catalog <project>/.orket/durable/config/extensions_catalog.json --db <project>/report.sqlite3 --submission <report-repository>/submission.json --inputs <report-repository>/inputs.json --model <exact-served-model> --provider llama_cpp --provider-base-url http://127.0.0.1:8080/v1 --json
```

Use the catalog selected by `ORKET_EXTENSIONS_CATALOG` or the project's configured
durable root if it overrides the default above. Use `ORKET_DISABLE_SANDBOX=1`
for routine verification. `--model` also supports an explicitly selected Ollama
provider; there is no implicit provider fallback. The ticket-specific
`--deterministic-fixture` provider is not a report-generation fixture.

For Gardener installation, configuration and upgrades, continue with the
[command harness guide](../gardener_harness/README.md#configure-gardener).

The returned JSON includes the run ID and
`iterations[0].advisory_proposal`. Check `ok` and final truth before accepting
delivery. Later, `orket agent inspect <run-id> --db <database> --json` retrieves
the same advisory content and `orket agent replay` checks retained decisions.

To adapt the example, edit the objective, acceptance and snapshot content, then
recompute each materialized input's canonical digest and encoded byte count
using SDK `canonical_json` and `canonical_digest_sha256`. Update both context
reference lists consistently. Required report sections belong in the submission's
`verifier_config`; the complete contract is
[Governed Agent Task Submission](../../docs/specs/GOVERNED_AGENT_TASK_SUBMISSION.md).
