# Host model generation options

Last updated: 2026-09-13
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
   selected profile's maximum. A request never widens its profile ceiling.
   Without a resolved profile, an explicitly requested limit remains applicable.
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
   values. Existing strict-task/enforce missing-profile refusal remains intact.
6. OpenAI-compatible requests use `max_tokens`, `temperature` and `stop`.
   Ollama uses `options.num_predict`, `options.temperature` and `options.stop`.
   The shared policy retains its existing profile sampling and seed behavior.

The generic extension HTTP route preserves stop strings through service/SDK
construction. An empty stop string fails with HTTP 400 before inference. Injected
providers remain authoritative for their own behavior; builtin provider conformance
does not certify arbitrary third-party implementations.

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
