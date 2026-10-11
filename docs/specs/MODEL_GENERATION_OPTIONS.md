# Host model generation options

The extension HTTP generation route translates settled provider timeouts to
HTTP 504 with `E_EXTENSION_MODEL_PROVIDER_TIMEOUT` and connection failures to
HTTP 503 with `E_EXTENSION_MODEL_PROVIDER_UNAVAILABLE`. Both use the existing
`detail: {ok: false, code, message}` envelope, after owned provider cleanup.
Provider response bodies and arbitrary exception text are not exposed. These
statuses do not establish remote inference termination or authorize retries.

Last updated: 2026-10-10
Status: Active development contract; architectural-truth candidate
Owner: Orket Core

The host's `LocalModelCapabilityProvider.generate(GenerateRequest)` forwards each
request's `max_tokens`, `temperature` and `stop_sequences` through the canonical
local prompting policy. They become `local_prompt_max_output_tokens`,
`local_prompt_temperature` and `local_prompt_stop_sequences` in that call's runtime
context. Request defaults apply on each call. Provider instance defaults and
process environment are not mutated to implement per-call options.

## Effective options

1. Maximum output is the smaller of the requested positive integer and the
   selected profile's maximum, except builtin SDK Ollama generation refuses a
   request above that ceiling with `E_MODEL_OUTPUT_LIMIT`. A request never widens
   its profile ceiling. Without a resolved profile, an explicitly requested limit
   remains applicable only on paths that admit unresolved profiles.
2. Explicit request temperature overrides the profile/constructor temperature
   for that call. It must be a finite number between 0 and 2, inclusive.
3. Requested stops precede profile stops. Only identical strings are deduplicated;
   spaces, newlines and other characters retain their exact value. An empty list
   adds no caller stops; it does not remove profile stops. Empty strings are invalid.
   Custom profile files use the same exact-string validator; profile loading and
   provider-default binding do not trim stops or stringify invalid elements.
4. The policy rejects boolean, fractional, string, zero or negative token limits;
   boolean/non-numeric/nonfinite/out-of-range temperature; and stop lists with
   non-string or empty elements. Existing API numeric parsing/bounds still apply
   at the interface. Policy validation runs for resolved and unresolved profiles.
5. Unresolved profiles in an already admitted shadow/compat path retain only
   explicitly supplied sampling options, without fabricating other sampling
   values. Builtin SDK Ollama requires a resolved profile in every mode.
   Existing strict-task/enforce missing-profile refusal remains intact.
6. OpenAI-compatible requests use `max_tokens`, `temperature` and `stop`.
   Ollama uses `options.num_predict`, `options.temperature` and `options.stop`.
   The shared policy retains its existing profile sampling and seed behavior.

The generic extension HTTP route preserves stop strings through service/SDK
construction. An empty stop string fails with HTTP 400 before inference. Injected
providers remain authoritative for their own behavior; builtin provider conformance
does not certify arbitrary third-party implementations.

## Ollama full-input admission

Builtin SDK generation and `POST /v1/extensions/{id}/runtime/llm/generate`
use the existing budget admission and guarded native Ollama transport. Both
default and per-request provider/model selections follow this rule. The SDK
sets internal `local_prompt_ollama_full_input`; the policy derives the input
budget from the resolved host profile and reserves the effective output budget.
It preserves all messages after normal profile shaping instead of trimming
history or dropping an oversized user message. These checks also apply in
shadow/compat modes.

Admission uses the conservative UTF-8 byte estimate with message overhead from
`model_input_budget.py`; it is not an exact tokenizer measurement. The host sends
explicit `num_ctx` within the selected profile's context capacity, plus
`truncate: false` and `shift: false`. Ollama >=0.24.0 and observed model context
metadata are required. The existing HTTP owner retains captured TLS/auth/proxy
inputs, client cleanup and one inference attempt.

An oversized input returns `E_MODEL_INPUT_BUDGET` before generation. Unsupported
guards or context capacity return the existing `E_OLLAMA_*` admission errors.
The extension API maps these to HTTP 400 using its existing
`detail: {ok: false, code, message}` envelope. A missing profile returns
`E_LOCAL_PROMPT_PROFILE_REQUIRED`, rather than dispatching without a budget.
Direct SDK callers receive the corresponding exception.

Operators can reduce the input or select an operator-authored registry with
`ORKET_LOCAL_PROMPT_PROFILE_REGISTRY_PATH`, increasing `context_budget_tokens`
only within the model's capacity. The request's `max_tokens` controls output;
it does not authorize more input. Other providers, streaming and injected
third-party SDK implementations retain their existing contracts.

### Larger prompts through the headless extension

Gardener's headless extension uses this generic API. Its prompt and output reserve
can exceed the packaged Qwen/Llama Ollama profiles' 8192-token context even with
a small repository snapshot. `E_MODEL_INPUT_BUDGET` names both
`context_budget_tokens` and `ORKET_LOCAL_PROMPT_PROFILE_REGISTRY_PATH` so the
host operator can locate the limit. The estimate counts UTF-8 bytes plus overhead,
not tokenizer tokens; reducing only the snapshot may still be insufficient.

1. From the host's installed Python environment, copy the packaged registry to a
   new operator-owned file. Choose a new destination to preserve existing settings:

   ```text
   python -c "from importlib.resources import files; from shutil import copyfile; copyfile(str(files('orket.runtime.config').joinpath('local_prompt_profiles.json')), 'local_prompt_profiles.operator.json')"
   ```

2. Edit the matching entry under `profiles`. For `qwen2.5:7b` on Ollama this is
   `profile.profile_id: ollama.qwen.chatml.v1`; for `llama3.2:3b` it is
   `ollama.llama.inst.v1`. Set that entry's `profile.context_budget_tokens` to `32768`
   only if the selected model supports it and the host has sufficient memory.
   Preserve the other registry fields. This affects every model matching that
   entry, so review its `provider` and `match` rules. If the host explicitly sets
   `ORKET_LOCAL_PROMPT_PROFILE_ID`, edit that selected profile instead.
3. Validate the edited file using the same installed environment:

   ```text
   python -c "from orket.runtime.config.local_prompt_profiles import load_local_prompt_profile_registry_file; load_local_prompt_profile_registry_file('local_prompt_profiles.operator.json'); print('Registry schema valid; model capacity and inference not tested')"
   ```

4. Set `ORKET_LOCAL_PROMPT_PROFILE_REGISTRY_PATH` to the file's **absolute path in
   the Orket API host's environment**, then restart that host. For example, in
   PowerShell from the Orket checkout before starting the API:

   ```powershell
   $env:ORKET_LOCAL_PROMPT_PROFILE_REGISTRY_PATH = (Resolve-Path ./local_prompt_profiles.operator.json).Path
   python server.py
   ```

   For a POSIX host, export its absolute POSIX path before starting the API.
   Setting the variable only in Gardener's separate client process does not
   reconfigure a running Orket host. `ORKET_GARDENER_MAX_INPUT_TOKENS` belongs to
   the command harness; it does not configure this generic API.
5. Retry deliberately and inspect the result. Orket sends the selected context
   as Ollama's `num_ctx`; changing only `OLLAMA_CONTEXT_LENGTH` on the server does
   not override this per-request limit. The input estimate plus output reserve
   must fit. `max_tokens` must also fit the selected sampling bundle's output
   ceiling. Raising context alone does not raise that ceiling, guarantee report
   quality or authorize truncation. A missing registry still fails closed.

The packaged default remains 8192. A 32768-token profile is an explicit example,
not a promise that every Gardener prompt or device fits. The command harness has
its separate submission limits in [Gardener Report Harness](GARDENER_REPORT_HARNESS.md).

## Evidence and limits

Retain the effective sampling bundle/stops in the existing provider telemetry and
the original backend response. Forwarding a limit is distinct from proving a
backend honored it. Conformance requires actual selected-provider behavior,
including a length-limited response and a paired stop/no-stop control; temperature
forwarding does not independently certify its statistical effect.

This contract covers the generic host SDK/API path and its shared policy. It does
not admit arbitrary native payload overrides or certify all runtime-context
producers. A length-limited text response is transport success, not proof that the
user's larger writing objective completed. SDK timing and response schemas remain
unchanged; latency authority is `docs/specs/MODEL_PROVIDER_TIMING.md`, and local
client/cancellation ownership is `docs/specs/API_RUNTIME_LIFECYCLE.md`.
