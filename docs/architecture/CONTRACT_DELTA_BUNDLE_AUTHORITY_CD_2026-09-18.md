# Bundle command authority and owned archive operations

Owner: Orket Core
Date: 2026-09-18
Effective version: 0.6.25 (patch checkpoint; whole architectural-truth lane open)

## Delta

Bundle validation, packing and inspection now enter `BundleService` in application.
The interface parses arguments and renders results. Core `OrketManifest` validates
supplied payloads; its unused `load_orket_manifest(path)` file reader is retired.
Application owns schema, engine, model-selection and reference policy. The
side-effecting `BundleStore` owns filesystem/archive observations and publication
through retained workers. Offline ledger verification also enters application,
and application composes the built-in connector registry for CLI callers.

Bundle service calls capture their selected store, explicit engine version and
model list before the first await. Existing installed-version lookup and the
source-checkout `pyproject.toml` fallback move into an owned worker. Core does not
observe installation state or files. Directory inspection reuses its admitted
manifest instead of independently loading it again.

Packing checks that the admitted manifest is unchanged and all required archive
members remain present. It writes a sibling temporary archive, verifies its member
names and content hashes, replaces the destination, and verifies the published
archive before reporting success. A manifest change or disappeared reference
returns `E_PACK_SOURCE_CHANGED`. Failures before replacement preserve an existing
destination. A verification error after replacement is a failure with the new
destination present; this is not a filesystem transaction with rollback.

Archive timestamps, permissions, lexical member order and compression retain their
existing deterministic values. Manifest bytes, including CRLF, are preserved.
References and packed symlink targets must resolve within the bundle root. Unsafe
or colliding archive names fail. Malformed YAML and invalid UTF-8 archive manifests
produce parse errors. No archive extraction is performed by inspection.

## Lifetime and limits

Worker admission retains ownership through repeated cancellation and timeout.
Cancellation is delivered after the admitted file operation settles; a pack may
have completed its verified replacement before cancellation reaches its caller.
Worker failure takes precedence over cancellation. Temporary files are cleaned in
the same path. CLI event-loop shutdown follows settlement of its awaited service.

This does not promise bounded OS filesystem operations, crash durability, a
transactional snapshot across source files, or fencing against external writers.
Source bytes can change while being gathered; the archive is verified against the
bytes actually read. Captured manifest agreement and required-member presence are
checked separately. Other bundle-CLI commands retain their existing boundaries;
this change is not a claim of whole-CLI asynchronous safety.

## Migration

There is no compatibility window or forwarding shim for the retired interface
helpers, their bundle error constants, or the core loader. Error code strings in
command payloads remain the contract. Embedded bundle callers use `await BundleService(...).validate(...)`, `.pack(...)` or `.inspect(...)`. Core callers supply a decoded
payload to `OrketManifest.model_validate`. Offline file callers use
`await verify_ledger_file(path)`; connector CLI composition uses
`await OutwardConnectorService.for_workspace(...)`.

Source and installed gates cover real files, archive readback, process-level CLI
commands from a foreign working directory, deterministic manifest policy, retained
worker cancellation/timeout, and negative publication paths. Controlled scheduling
and corruption hooks exercise real underlying writes and are not provider proof.
The canonical plan records exact observations and remaining acceptance gates.

## Rollback and versioning

This is a breaking Python helper/API migration in patch checkpoint 0.6.25; command
names and successful JSON shapes remain unchanged. Revert the versioned code,
caller and authority changes together if downstream migration fails, then rerun
source and installed gates. Existing archives require no data migration. Reversion
restores the prior implicit core read and unowned CLI effects; it is not C/D closure.


## Checkpoint evidence

The final candidate executes the same 1,159 unique cases in source and installed
Windows/Linux Python 3.11/3.12 environments, with zero failures/errors/skips and
937 observed core-module origins per installed cell. The canonical plan records
artifact digests, controlled negative paths, the interrupted initial source run,
and the encoding failures that preceded repair. This is scoped C/D evidence, not
full-suite, hosted, provider, capacity, hostile-containment or whole-lane acceptance.
