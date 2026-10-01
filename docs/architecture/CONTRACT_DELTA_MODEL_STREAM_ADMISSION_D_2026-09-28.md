# Model-stream canonical target admission

Date: 2026-09-28
Status: Implemented bounded D/C refusal correction; Windows source proof below

The runtime resolver can return a nonempty model_id with status BLOCKED when that
model is quarantined, the GGUF inventory is unavailable/empty, or the selected GGUF
model is missing. The old model_stream_v1 caller rejected only empty model IDs,
allowing these observations to construct a provider and reach inference. This is
distinct from the already prepared workload input-capture correction.

Canonical authority is the existing ProviderPreparationRequest and
require_prepared_target in `orket/core/contracts/provider_preparation.py`.
The existing provider-preparation contract explicitly requires blocked targets
to remain outside inference. The workload now supplies its captured provider,
requested model and normalized selected endpoint to that authority before
constructing either provider. Endpoint defaults remain in the existing resolver's
default_base_url helper; normalization remains in ProviderPreparationRequest.
No duplicate status/identity checker, client-type exception, alternate provider,
fallback or success coercion is introduced. A valid auto-selected model remains
allowed when the target describes the original request and selected endpoint.

The old empty-model ValueError and diagnostic message remain unchanged. For a
nonempty target, canonical refusal raises ModelConnectionError, including a
BLOCKED status or mismatched provider/backend/request/endpoint. This is a deliberate
extension of the refusal range: callers that previously received provider events
for those invalid targets now receive the canonical preparation error before any
provider construction. There is no translation into a generic note or timeout.
Successful event schemas, request copies, provider choice and fallback behavior
remain unchanged. Resource lifetime, cancellation and fatal-error precedence after
provider admission are not changed by this slice.

The seven integration controls use the real runtime resolver, local HTTP
catalog/completion endpoints, real GGUF inventory files and the public builtin
workload with InteractionManager. Four independently exercise nonempty BLOCKED
targets: OpenAI-compatible model quarantine, canonical-backend quarantine of a
llama_cpp request, missing selected GGUF file and empty GGUF directory. Each must
show the actual nonempty model ID and blocking resolution mode, no inference
provider construction, no completion POST and no model/token/finalize-workload
claim. Admitted OpenAI-compatible/llama_cpp guards and the old empty-model refusal
remain. The fixture cancels/finalizes its refused interaction for teardown; that
cleanup commit is not successful workload admission. Physical request/event/commit
readback is retained before policy assertions.

These are supplied local protocol fixtures, not model-quality, local-daemon or
external-provider inference proof. They do not demonstrate rollback of discovery
or previously completed model-load effects. The candidate author supplied only static review. Root-owned source opening
and closing are recorded below; installed evidence remains pending.
The independently reviewable input baseline is
`docs/architecture/CONTRACT_DELTA_MODEL_STREAM_INPUTS_D_2026-09-28.md`.

## Observed source proof, 2026-09-28

Windows Python 3.11 opening: nine failures and seven passes in 19.16s, with
5,634 unchanged Git-visible inputs. Five input controls expose mutated requests,
API keys, inference/turn deadlines and resolver environment/CWD. Four admission
controls physically show nonempty BLOCKED targets constructing a provider,
posting completion requests and producing successful workload intents. Both turn
phase controls pass on unchanged product. The reports retain each failed case
and actual local HTTP/event/commit readback before assertions.

After the separately reviewed input, admission and turn changes, the combined
Windows Python 3.11 selection passes 364 cases in 221.01s (one upstream warning),
5,638 unchanged inputs. Python 3.12.2 source proof passes 94 cases in 57.89s on
the same 5,638 inputs, including all fourteen workload controls, both turn phase
controls, all 22 tool ownership controls and streaming/provider guards. This is
live local HTTP/file/SQLite and controlled-provider integration proof (primary,
success). Fixture catalog/model bytes do not establish actual model inference.
The Python 3.12 environment name includes installed, but imports are from source;
neither campaign is a fresh installed-artifact acceptance run.

Evidence: `.tmp/goal-20260928-model-turn-opening-v1-*`,
`.tmp/goal-20260928-model-opening-physical-readback.json`,
`.tmp/goal-20260928-model-turn-tool-closing-v1-*`, and
`.tmp/goal-20260928-model-turn-tool-source-py312-v1-*`.
Wider provider/generator/waiter lifetime, canonical quality, installed/Linux and
CAP acceptance remain open. No version bump or whole-lane completion follows.
