# Governed Agent Task Submission

Last updated: 2026-10-10
Status: Active

## Public boundary

`orket agent run` consumes the existing SDK `governed_agent_submission.v1`
contract and an array of `AgentMaterializedInput` objects. It admits one bounded
report iteration through the existing catalog, broker, child-process owner,
continuation policy and terminal transaction. It is a manual CLI entrypoint;
the existing low-level `agent submit` and wake/API contracts remain unchanged.

```text
orket agent run --submission submission.json --inputs inputs.json --catalog catalog.json --db agent.sqlite3 --model <exact-model-id> --provider llama_cpp --provider-base-url http://127.0.0.1:8080/v1 --json
orket agent inspect <returned-run-id> --db agent.sqlite3 --json
orket agent replay <returned-run-id> --db agent.sqlite3 --json
```

The application entrypoint is `run_governed_agent_task` in
`orket/application/services/governed_agent_task_service.py`. It receives explicit
paths, provider options, environment, run identity and UTC clock from its caller.
The CLI supplies the identity and clock. Extensions use only the public SDK.

The runnable source example is `examples/governed-report/`. Its report is about
authored sample documents, not an actual repository audit. Install a trusted Git
repository containing that manifest through `orket runtime extensions install`.
The manifest identity must match the submission; the requested profile map must
match the catalog declaration. Catalog integrity checks remain in force.

`examples/gardener_harness/` adapts Gardener report dispatches to this same
contract and example extension. Committed snapshot admission, source stability,
process ownership and the outward claim ceiling are specified in
`docs/specs/GARDENER_REPORT_HARNESS.md`.

## Admission and ownership

1. Both JSON files are bounded to 1 MiB each. References, kinds, content digests
   and byte counts use the existing SDK validators. Every objective, acceptance
   and context reference must have materialized input. References are labels;
   the host does not follow URLs, read named repository files or fetch commits.
2. Input reads and catalog preparation settle under an owned native worker.
   Paths and environment are captured before suspension. Caller cancellation
   waits for native preparation to settle and prevents subsequent dispatch.
3. The CLI generates a fresh run ID on each invocation. The host derives attempt,
   step, trace and invocation IDs, remaining-budget snapshots, deadline and lease.
   It observes creation time after input preparation and decision time after
   result verification. Provider preparation consumes the run's wall-time limit.
4. The submitted contract is retained in the request's
   `extension_config.governed_submission`. Configuration identity binds the
   submitted policy, verifier and generated request to the existing provider and
   catalog identity. The same durable store owns the run, model receipts and
   terminal publication.
5. This entrypoint is one-shot, with no automatic retry or supervisor admission.
   Repeating the CLI creates a different run. Inspect/replay a retained run before
   deliberately rerunning an uncertain invocation.

## Admitted report policy

`policy_schema_version` is `governed_agent_report_policy.v1`.
`allowed_capabilities` is exactly `["agent.iteration.v1"]` and
`recovery_posture` is `fail_closed`. `policy_digest` is `sha256:` followed by
SDK `canonical_digest_sha256` of this object:

```json
{
  "schema_version": "governed_agent_report_policy.v1",
  "allowed_capabilities": ["agent.iteration.v1"],
  "namespace_scope": ["<submitted scopes>"],
  "recovery_posture": "fail_closed"
}
```

Both budgets declare one iteration, concurrency one, zero effect proposals,
empty per-capability effects, and zero artifact bytes. Both wall-time limits
are identical and between 1 and 3,600,000 milliseconds. Iteration model-call and
output-byte budgets cannot exceed the manifest ceilings; recovery posture must
match the manifest. All existing SDK budget/profile constraints still apply.
The broker provides model calls; memory queries and repository effects are not
admitted. Policy refs and operator refs label the operator-authored request;
they are not external authorization services.

Extensions remain trusted code. This policy controls brokered authority and
completion; the import guard and subprocess boundary are not an OS sandbox.
No hostile-code containment or filesystem immutability claim follows from a
read-only report contract.

## Provider admission and failures

The SDK's JSON `response_schema` is forwarded to Ollama's native `format` or
OpenAI-compatible `response_format.json_schema`. The report example supplies
section and reference constraints instead of a generic object hint. This is
generation guidance and broker response validation, not another completion
verifier: `structured_report.v1` still independently checks delivery. A provider
that rejects the schema fails visibly; the host does not silently downgrade it.

The standalone CLI prepares and binds its logging scope before provider work.
Ollama inventory comes from `/api/tags` at the selected endpoint using captured
authentication. An unreachable endpoint produces a typed inventory/provider
failure, not a logging-preparation error or inventory from another daemon.

Governed model requests preserve their admitted messages. Output requests above
the host profile ceiling fail with `E_MODEL_OUTPUT_LIMIT`; inputs above the
admitted capacity fail with `E_MODEL_INPUT_BUDGET` before generation. Qwen3.8
llama.cpp uses native rendering/tokenization, including the output reservation.
Both native input-limit and conservative input-budget refusals explicitly state
`input was not truncated`; their measured-count/estimate fields remain distinct.
Other supported profiles conservatively estimate UTF-8 bytes plus 128 per
message and 256 overhead. This is admission guidance, not tokenizer measurement
or a universal custom-template bound. Post-call observed usage is still enforced.

Ollama additionally requires version >=0.24.0, an observed model context limit,
and native `/api/chat` guards `truncate: false` and `shift: false`. Its explicit
`num_ctx` is the smaller of host capacity and requested input plus effective
output. Old servers or unknown/insufficient model capacity refuse before chat.
The shared HTTP resource owner supplies captured TLS, proxy, authentication and
cleanup; the governed non-streaming transport disables redirects. No speculative
inference retry follows a timeout or governed connection failure. Closing the
HTTP client does not prove termination of remote inference.

Run/inspect expose `iterations[].model_calls[].normalized_reason` from retained
result payloads or retained uncertain-call reasons. Budget refusals record zero
measured tokens. Settled transport timeouts/unavailability in the admitted
report-only path return failed receipts with unknown usage and charge the full
reserved budget. A stopped child can then publish unsatisfied terminal truth
through the existing continuation policy. Unknown provider errors, interrupted
dispatch/publication and general governed runs retain recovery semantics. A
provider-truncated response fails even if its JSON is structurally valid.

## Host verifier and completion meaning

`verifier_class` selects the built-in `structured_report.v1` implementation.
Unknown classes are refused before provider construction. The host never imports
a verifier module named by the submission. `verifier_config` requires
`required_sections`: 1–32 unique, nonblank names of at most 128 characters.
Optional `minimum_section_lengths` maps required section names to integer
trimmed-character minimums from 1 to 32768; booleans are refused. Optional
`required_section_prefixes` maps required names to nonblank prefixes of at most
128 characters. Prefixes must begin the section exactly and have nonblank text
afterward. Unknown keys or section names refuse before provider construction.

The result's `advisory_proposal` contains a JSON object with exactly these fields:

```json
{
  "sections": {"summary": "Findings based on the supplied inputs."},
  "source_refs": ["snapshot:readme", "snapshot:conventions"],
  "limitations": ["Only the supplied documents were inspected."],
  "advisory": true
}
```

Section keys must exactly match the configuration. Values are nonblank strings
of at most 32,768 characters. `source_refs` contains every submitted initial
context reference exactly once, no others, with at most 256 entries. `limitations`
contains at most 128 nonempty strings of at most 2,048 characters; an empty array
is allowed. Existing SDK proposal and result size limits also apply.

The host requires a returned invocation, returned non-truncated model receipts, and no effect,
memory-write or handoff proposals. Missing/invalid output cannot produce a
successful final truth. Extension completion recommendations remain advisory.
Successful completion means **delivery of a structurally valid advisory report
bound to the supplied input references**. It does not certify factual accuracy,
repository coverage, test results, fixes, or broader prose acceptance criteria.
Tasks needing those guarantees require a different host-owned verifier contract.

Run and inspect JSON expose `iterations[].advisory_proposal`, alongside its
existing result digest and decision. This is retained advisory content and is
also visible for a rejected result; consumers must separately check `ok`, the
decision and final truth. Replay checks retained decision evidence, not the truth
of model findings and not a fresh model invocation.

## Verification contract

`tests/integration/test_governed_agent_task.py` exercises a real CLI, external
SDK child, controlled provider HTTP, SQLite, inspection/replay and refusal cases.
`tests/integration/test_governed_agent_task_ownership.py` exercises actual native
input settlement, captured paths/environment and post-model clock observation.
Both Quality selections retain these controls. Controlled HTTP is integration
proof, not live-model proof. Live proof requires the public command with an
actual provider, retained receipts and settled process cleanup, with
`ORKET_DISABLE_SANDBOX=1` for this report-only flow.
