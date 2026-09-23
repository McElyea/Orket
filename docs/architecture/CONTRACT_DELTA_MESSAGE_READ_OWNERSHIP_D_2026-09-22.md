# Turn-message capture and required-read ownership

## Summary
- Change title: Capture prompt inputs and own required-read observation and logging.
- Owner: Orket Core.
- Date: 2026-09-22.
- Affected contracts: `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`
  and existing workspace constraints in `PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md`.

## Delta
- Current behavior: MessageBuilder path metadata blocks the event loop and its
  interrupted native read may outlive preparation. Workspace, role/tools and
  context mutation can alter messages after the first read is admitted. Required
  preloads bypass the validator used for governed filesystem tool calls.
- Proposed behavior: capture only prompt-consumed values before the first await,
  retain the two original compaction output sinks, validate required paths with
  existing PathResolver policy, and retain native metadata/read/close and missing
  input log production with existing owners. Do not copy unrelated resources.
- Why now: matched source and installed .99 observations record three ownership
  failures among five cases and three capture failures among eight. Healthy
  controls pass. Path-admission controls and scoped repair acceptance are recorded
  separately in the remediation plan; this delta alone is not acceptance evidence.
- Admission: invalid required-read tokens fail before any preload content with
  `ValueError(E_WORKSPACE_CONSTRAINT:<read_file detail>)`; valid absent files keep
  the missing-input classification. All absolute tokens are rejected by the
  existing governed validator. No new reference-root capability is introduced.
- Preserved semantics: prompt ordering and text, compaction, card-completion
  authority, preload predicates, newline normalization, 4000-character limit,
  valid path classification and diagnostic event payload. An all-missing list
  still prunes `read_file` and emits no missing-input notice or event. Logging
  proof covers admitted directory/main-log append work, not subscriber callbacks,
  standard-library handlers, durable delivery or other producers.
- Limits: no hostile public exploit claim, atomic filesystem snapshot, rollback,
  forced native termination, hard filesystem deadline or handle-bound confinement.
  Shared PathResolver callers and upstream context construction outside this
  preparation route retain their separately recorded async obligations.

## Migration Plan
1. Compatibility window: v0.6.100 adopts capture and retained interruption without
   a shim or second resource owner.
2. Supply intended prompt inputs before preparation starts. Retain interrupted
   callers until admitted work settles. Use workspace-relative required-read paths;
   explicit low-level reference reads keep their separate capability contract.
3. Only the original metadata/layer dictionaries receive compaction output. Later
   replacement slots cannot acquire output authority for an admitted preparation.
4. Validation: matched source/wheel controls; every native metadata site, read and
   logging lifetime; captured inputs, untouched opaque resources, exact output
   parity, path refusals and low-level reference compatibility; then frozen source
   and installed Windows 3.11/3.12, package parity and canonical dependency checks.
   Linux clock and whole D/E/CAP acceptance remain separate obligations.

## Rollback Plan
1. Trigger: changed valid prompt output, lost output-sink provenance, wrong path
   admission or unowned native work.
2. Repair forward through the same builder, PathResolver and existing file/native
   owners; retain all failed and passing evidence. Do not restore escaped work.
3. No receipt/state schema migration, resealing or deletion is required.

## Versioning Decision
- Version bump type: patch; scoped architectural remediation.
- Effective version/date: 0.6.100 / 2026-09-22.
- `compatibility_status`: `breaking`.
- `affected_audience`: `all`.
- `migration_requirement`: `required`.
- Downstream impact: prompt input capture, original-sink publication, governed
  required-path refusal and retained interruption. No new provider admission.
