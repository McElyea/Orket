# Controller schema package and input ownership

Last updated: 2026-09-19
Status: Active contract delta; scoped source/installed proof recorded in the canonical plan
Owner: Orket Core

## Problem and resulting behavior

Installed controller workloads previously tried to read an unpackaged schema
beside the installation. Their observability step failed after child execution.
A process-wide cache also silently reused the first schema when later callers
selected another path or replaced the selected file.

The canonical schema now lives at
`orket/runtime/config/assets/contracts/controller_observability_v1.json` and ships
in both the source archive and wheel. Its JSON schema identifier and validation
rules are unchanged. The former repository path is retired; no runtime fallback
or second editable schema remains. Archived planning references are historical.

`validate_observability_schema` loads the packaged default unless a caller
explicitly supplies a schema path. Each call reads its selected bytes without a
shared schema cache. Nested event values are captured before awaiting the read.
Explicit relative paths retain normal process-working-directory semantics;
callers requiring a bound root supply an absolute path.
Application owns the read worker through cancellation; a failed read or invalid
event cannot become successful validation. This is worker ownership, not a
filesystem snapshot guarantee against concurrent external writers.

## Migration and proof limits

Embeddings may continue using the default validator or supplying an explicit
schema path. Tools that directly opened the retired repository path must use the
new canonical package location. Event payloads and the schema identifier remain
compatible. Controller projections still do not authorize terminal child truth.

The four retained installed failures, the installed schema-selection
counterexample, and subsequent source/package/native proof are recorded in the
architectural-truth plan under `.tmp/d-sdk-lifetime/`. Native SDK lifetime and
uncertainty semantics remain defined by `docs/specs/SDK_WORKLOAD_PROCESS_LIFETIME.md`.
Artifact publication workers and the remaining C/D/E/CAP obligations stay open.

Effective version: 0.6.34 / 2026-09-19.
