# Model provider timing availability

Last updated: 2026-09-13
Status: Active development contract; architectural-truth candidate
Owner: Orket Core

## Provider response observations

New `LocalModelProvider` observations carry
`timing_schema_version: model_provider_timing.v1`. Their `timings` object has
`prompt_ms`, `predicted_ms` and `total_ms`, each a finite nonnegative float or null.
Zero is a valid reported value. Boolean, negative, nonfinite, overflowing or
missing metadata is unavailable. OpenAI-compatible millisecond fields also
accept finite numeric strings; provider nanosecond fields require numbers.

Each field comes from that provider-reported duration. OpenAI-compatible lookup
uses nested millisecond fields, nested nanosecond fields, then top-level
nanosecond fields. Ollama uses its reported nanosecond fields. A missing phase is
never derived by subtracting another phase from total time. Client elapsed time
never substitutes for a missing backend phase or backend total. The original
provider payload stays available under its existing raw-provider key.

`latency_ms` remains the locally measured integer elapsed time for the successful
attempt. `latency_measurement` names `source: perf_counter` and
`scope: successful_attempt_until_response_observed`. The timer excludes preceding
failed attempts and retry waits. It includes request construction/dispatch and
response observation at the existing adapter seam; OpenAI-compatible observation
includes response parsing. It does not measure GPU execution, time to first token,
an entire retried invocation, or service capacity. Failed calls that raise do not
produce a successful response or an invented zero measurement.

## Runtime event and benchmark projections

The turn token payload retains `timing_schema_version` and `timing_posture`:

- `reported`: both validated phases supplied under the new provider schema.
- `partial`: only one phase supplied under that schema.
- `unavailable`: neither phase has a valid duration.
- `legacy_unverified`: numeric phases have no recognized new-schema provenance.

Its existing token/timing `status` describes field availability, not independent
measurement certification. Historical source observations and logs are not
rewritten or assigned the new schema. Reprojected legacy numeric values remain
explicitly unverified. New consumers must inspect provenance before using them
as current timing evidence.

The live-card benchmark aggregates phase durations only if every included
`turn_complete` for the selected session carries both valid phases, the recognized
schema and `timing_posture: reported`. Missing or legacy timing makes aggregate
phase durations and throughput unavailable. It cannot combine disjoint phases
from separate turns into a complete measurement. Complete prompt/output token
coverage is separately required for token totals used in throughput. Reported
zero durations remain zero; division by zero does not produce a throughput value.
Old benchmark outputs stay historical and are not retrospectively certified.

## Public SDK generation and generic host API

SDK `GenerateResponse` exposes `schema_version: model_generate_response.v1`,
`latency_ms: int | None` and a derived, frozen `latency_posture` field. Non-null
latency must be a nonnegative integer; invalid explicit constructor inputs raise
`E_SDK_GENERATE_LATENCY_INVALID`. `dataclasses.asdict` retains version and posture.
The host's local generation adapter maps invalid/missing integer metadata to
null without coercing strings, fractional numbers or booleans. Its token counts
use the same strict integer observation helper. Governed receipt observation
reuses that helper without changing its v2 wire or budget contract.

`NullLLMProvider` and the host's deterministic static provider perform no model
inference and report unavailable latency. The generic extension generate route
preserves these fields; it does not cast null to an integer. `reported` means the
host/provider supplied that observation, not an independent timing attestation.

This public change belongs to SDK 0.7.0a1 and its matched host candidate only.
Consumers must handle nullable latency and retain the response version/posture.
Published core/SDK compatibility remains governed by
`docs/requirements/sdk/VERSIONING.md`; no release or tag is created here.
Governed-agent receipts retain the separate v2 contract in
`docs/specs/GOVERNED_AGENT_LOOP_V1.md`.
