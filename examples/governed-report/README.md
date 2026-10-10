# Governed advisory report example

This workload imports only `orket_extension_sdk`. It asks one selected model to
compare supplied sample documents and returns a structured advisory report.
It does not inspect your checkout. The host verifies delivery and source refs;
it does not certify the findings.

Copy this directory into a separate trusted Git repository, commit it, then use
the existing installer from your Orket project:

```text
orket ext validate <report-repository> --strict --json
orket runtime extensions install <report-repository>
orket agent run --catalog <project>/.orket/durable/config/extensions_catalog.json --db <project>/report.sqlite3 --submission <report-repository>/submission.json --inputs <report-repository>/inputs.json --model <exact-served-model> --provider llama_cpp --provider-base-url http://127.0.0.1:8080/v1 --json
```

Use the catalog selected by `ORKET_EXTENSIONS_CATALOG` or the project's configured
durable root if it overrides the default above. Use `ORKET_DISABLE_SANDBOX=1`
for routine verification. `--model` also supports an explicitly selected Ollama
provider; there is no implicit provider fallback. The ticket-specific
`--deterministic-fixture` provider is not a report-generation fixture.

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
