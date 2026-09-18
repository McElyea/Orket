# Sandbox HTTP verification

Last updated: 2026-09-18
Status: Active implementation contract; proof status remains in the architectural-truth plan.

## Authority and inputs

`SandboxVerificationService` in application owns HTTP verification. Core captures
and interprets explicit values; `SandboxHttpAdapter` executes the admitted requests.
The service captures the sandbox id, HTTP base URL, timestamp, ordered scenario
definitions, request bodies and expected values before its first await. Nested
JSON inputs are immutable captured values. Later caller changes cannot alter the
admitted target, remaining requests or comparison criteria. The result log retains
the captured base URL; it does not reread a mutable sandbox object for evidence.

The timestamp comes from the supplied `RuntimeInputService`. The base URL must be
HTTP(S), have a host, and contain no user information, query or fragment. Scenario
ids must be unique. Raw scenario values must be JSON-compatible before model
serialization; callers explicitly convert Python models or dataclasses to JSON
values. Unsupported values, invalid scenario schemas or malformed base URLs refuse
the entire batch before HTTP. A scenario without a nonempty absolute URL path is a failed admission and
performs no HTTP request. An empty scenario list produces no HTTP observation and
cannot establish empirical completion.

## Observation and comparison

1. Each admitted request uses the captured base URL and path, an ASCII alphabetic
   method (default GET),
   optional JSON payload and per-request timeout (default ten seconds). Transport
   construction uses `trust_env=False` and does not adopt ambient HTTP proxy
   settings. Custom transport/TLS configuration belongs to the application-supplied
   transport factory.
2. Responses whose Content-Type contains `application/json` (case insensitive)
   are parsed as JSON; other response bodies are observed as text.
   Both the observed status and canonical JSON representation of the body must
   match the captured expectations. Expected status defaults to 200. Falsy values,
   including JSON null, are expectations, not permission to omit comparison.
   Canonical JSON equality distinguishes booleans from numbers and integer from
   floating-point representations; it is not fuzzy or schema-coercing comparison.
3. A transport/parse failure, missing endpoint, wrong status or wrong body is a
   failed scenario. Every scenario in an admitted batch is counted exactly once as pass or
   fail. An observation with the wrong identity or count cannot produce a result.
4. Application applies detached scenario observations only after the entire owned
   observation has settled. Concurrent edits to the same mutable caller object are
   not a supported merge operation; callers retain a separate draft for new work.
5. `VerificationResult` remains support evidence. A passing HTTP probe is neither
   independent proof of an entire workload nor sufficient card-completion authority.
   Combining fixture and HTTP verification does not make their storage atomic.

## Lifetime and migration

The application retains each admitted HTTP client operation through cancellation
and client cleanup. Cancellation stops further scenario dispatch, closes the
client and then propagates. Repeated cancellation cannot detach cleanup; cleanup
failure is not converted into clean cancellation. Cancellation publishes no new
scenario status. A completed HTTP request is not rolled back by cancellation, and
client cleanup does not prove that a remote server stopped its own work.

Use `await SandboxVerificationService(...).verify_sandbox(sandbox, verification)`.
The old core `SandboxVerifier` and `VerificationEngine.verify_sandbox` execution
surfaces are removed without forwarding shims. Core retains only captured-value
and interpretation functions. Fixture subprocess support code moves to
`orket/adapters/execution/fixture_runner.py`; its application/container consumers
use that one definition. Existing synchronous fixture tombstones retain their
`BT4-FIXTURE-SYNC-RETIRE` removal ticket.

This contract does not change Docker deployment admission, fixture execution
policy, OS isolation, provider promotion or the trusted-code claim ceiling.
