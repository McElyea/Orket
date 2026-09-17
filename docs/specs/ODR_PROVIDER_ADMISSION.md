# ODR provider admission and native result evidence

Last updated: 2026-09-14
Status: Active contract; current acceptance is scoped in the architectural-truth plan.

The quant-sweep entrypoint is `python scripts/odr/run_odr_quant_sweep.py`.
It compiles `odr.run_arbiter.plan.v2` and resolves its existing `WorkloadRecord`
through the shared control-plane workload catalog. It does not create a second
workload-ID registry or acquire card/outward execution guarantees.

`--provider` overrides the shared configured provider, whose default is llama.cpp.
`--base-url` overrides that provider's configured endpoint. One non-secret selection
is captured in the plan and its workload materials, used for model discovery,
passed explicitly to the native child, and retained in the child's result config.
Endpoint URLs cannot contain credentials, queries or fragments. API keys remain
in the provider adapter's existing configuration and never enter the plan.

Discovery uses `orket/runtime/config/provider_runtime_target.py`. The selected
provider's inventory must contain every requested model. Missing files or tools
refuse before provider discovery. Discovery failure produces the declared
preflight error artifact and CLI exit 2. Ollama installation is not a prerequisite
for llama.cpp work; unavailable providers do not cause a provider switch.
Child execution disables automatic model selection/loading for the admitted
explicit model identities. The existing provider adapter still owns runtime
policy and request validation.

The arbiter accepts current output only after existing shape/leak/trace checks
and matching provider selection and architect/auditor model receipts. Absent,
empty or conflicting provider evidence refuses. The runner closes both provider
clients on completion and failure. HTTP protocol fixtures establish transport and
control behavior; actual model inference requires separate live proof.

The native role runner uses the kernel's canonical architect/auditor prompt
builders. Scenario requirements, seed decisions and auditor issues remain explicit
inputs. Runner rules ask for concise prose within 250 words, preserve required
constraints and prohibit copying input constraint metadata as a ledger block.
This is a prompt instruction, not a measured output bound or quality guarantee;
existing shape/leak/trace validators and provider token ceilings still apply.

The plan, error and raw-run output paths retain their existing defaults/overrides.
Their reruns use the common diff ledger. The error path retains the last failed
invocation; its presence alone does not describe a later invocation's outcome.
The CLI exit and that invocation's validated child artifacts define its result.
The index aggregates its configured directory, including retained historical runs;
its total is not an invocation execution count or independent quality verdict.

Old v1 plans remain historical diagnostics and refuse preflight. Normal execution
compiles a fresh v2 plan; there is no automatic plan migration or effect replay.
Old raw results can remain in historical indexes, but cannot satisfy current
provider-bound output validation without the required evidence.

This contract covers bounded ODR planning, provider admission and artifact
validation. It grants no independent requirement-quality verdict, card acceptance,
automatic restart, general native descendant supervision, OS containment or remote
effect fencing. The architectural-truth plan owns current source/installed/native
proof, historical observations and remaining BT-5 obligations.
