# Explicit project vendors and observed card state

## Summary

Owner: Orket Core. Effective date: 2026-09-19. Version: 0.6.29.
Affected contracts: vendor selection, local project catalogs and runtime card observations.
Status: active contract; whole architectural-truth acceptance remains open.

## Delta

Application `create_project_vendor` receives a caller-supplied settings mapping.
It captures selected scalar values before its first await. It does not read
ambient settings. Only `local` and `gitea` are admitted; unsupported selections,
including the former ADO/Jira placeholders, raise `E_VENDOR_UNSUPPORTED`.
Gitea selection requires complete configuration, an HTTP(S) base URL without
embedded credentials/query/fragment, and individual owner/repository components.
HTTP-client construction runs inside an owned worker. If the caller is interrupted
before adopting the result, the factory drains construction and closes the client.
The existing Gitea request transport and the returned client's explicit `close()`
lifetime are unchanged.

Local composition requires absolute project and database paths. Application
`LocalProjectVendor` owns database directory initialization, actual card reads,
status write/readback and worker lifetime. Changing the working directory or
settings after composition cannot retarget these locations. A missing runtime
card raises `ValueError("Card not found: ...")`; no synthetic ready card is returned.
Status success follows a matching database observation. A mismatch raises
`E_VENDOR_CARD_STATUS_UNVERIFIED`. The existing database completion admission
still rejects successful lifecycle statuses without required evidence.

Catalog reads execute inside a retained worker, including path resolution,
inventory, parsing and projection. They use the existing default loader layout:
`config/<category>`, `model/<department>/<category>`, then `model/core/<category>`.
Loader strategy selection is fixed explicitly for this catalog; it does not read
ambient strategy settings. These are metadata projections, not execution
admission or acceptance verification. They validate displayed metadata without
constructing execution-only verification structures or minting catalog identities.

Rock views preserve the declared status; absent status uses `ready`. Catalog
rock/epic identifiers are asset names. Cross-department linked epics use
`<department>/<asset>` and can be passed directly to `get_cards`. Missing linked
epics surface errors instead of silently disappearing. Card collections use the
canonical epic field aliases (`issues`, `stories`, `cards`) from the schema.
Each catalog card needs a nonblank declared ID, unique within that returned list.
Missing/duplicate IDs are refused. Catalog queries without an epic return an empty
list, preserving the existing explicit-epic scope. Local `add_card` remains an
explicit unsupported operation; use the runtime's admitted card-creation path.

Cancellation and timeout retain admitted catalog, database and verification work
until it settles. Operation failures remain visible during cancellation. Native
SQLite admission and completion rules remain owned by their existing authorities.
Write and readback are separate transactions; concurrent changes may cause a
verification refusal. Success is an observation at readback, not a reservation
against subsequent writers. File catalogs are also observations, not atomic
snapshots across multiple files. No hard deadline for a hung filesystem worker,
hostile-process containment or whole-runtime shutdown guarantee is added.

## Migration Plan

1. Compatibility window: none for the retired adapter-owned coordinator imports;
   no aliases or fallback factories remain.
2. Replace `orket.vendors.factory.get_vendor` with
   `orket.application.services.project_vendor_factory.create_project_vendor`.
   Await the factory and pass `settings` explicitly. For local selection, also pass absolute
   `project_root` and `runtime_db`; missing database parent directories are created
   inside the owned operation. The root is the project, not its `model` subfolder.
3. Replace direct `orket.vendors.local.LocalVendor` construction with application
   `LocalProjectVendor(ProjectCatalogLocation(project_root, department), runtime_db)`.
   Treat missing runtime cards and malformed catalog data as errors. Supply
   declared card IDs; do not rely on read-time generated IDs or fabricated names.
4. Keep catalog metadata separate from runtime database state. A catalog status
   does not establish execution or completion acceptance. Drain pending local
   operations; close Gitea clients explicitly as before.
5. Validation gates: real model files and SQLite, captured roots/configuration,
   negative admission, actual status readback, preserved completion refusal,
   cancellation/timeout, and real loopback HTTP with client/server teardown.
   Responsiveness is bounded at 0.5 seconds and settlement at 3 seconds after a
   controlled release. The canonical plan records source and installed results.
   Loopback HTTP is not live Gitea-server acceptance.

## Rollback Plan

Rollback is versioned and requires draining pending operations before replacing
the application service and its callers together. Preserve selected model and
database files; no data migration is performed. Do not restore fabricated missing
cards, unsupported-provider fallback or working-directory retargeting as success.
Inspect retained database state after interrupted or unverified writes before retry.

## Versioning Decision

Patch checkpoint with breaking embedding and observation semantics.
Compatibility status: breaking. Affected audience: all. Migration: required.
The full C/D/E/CAP and whole-lane acceptance gates remain open.
