# Apple Silicon acceptance scope

## Summary
- Change title: First Mac local CLI/runtime acceptance requirements.
- Owner: Orket Core.
- Date: 2026-10-06.
- Affected contract(s): `docs/specs/MACOS_LOCAL_RUNTIME_ACCEPTANCE.md`,
  `docs/API_FRONTEND_CONTRACT.md`, `docs/specs/API_RUNTIME_LIFECYCLE.md`.

## Delta
- Current behavior: native command supervision admits Windows and Linux only;
  historical ATG-v1 acceptance targets Windows.
- Proposed behavior: a separate authorized Apple Silicon milestone adds native
  installed/setup/provider/Metal/process/restart acceptance obligations. No Mac
  runtime success or backend admission is granted by creating the lane.
- Implemented reporting delta: Darwin arm64 hardware has unified-memory metadata,
  null dedicated VRAM and explicitly unverified Metal/model fit. Health views
  preserve nulls; the legacy fit helper returns None for unknown. Direct hardware
  observations refuse loop-thread entry and use existing application workers.
- Why this break is required now: user explicitly authorized Mac implementation
  while preserving existing process guarantees and truthful proof boundaries.
- Packaging delta: the isolated candidate producer builds matched wheels from
  fresh Git-visible inputs, checks installed origins/bytes and public commands,
  and retains independent quickstart file/ledger controls. The guide and manual
  Gitea packaging job do not grant Mac runtime acceptance. Existing native
  command ownership remains required; unsupported dispatch is not bypassed.
- Setup delta: installed `orket setup` and `orket doctor` expose existing
  initialization, provider, hardware and command authorities. The selected model
  is a runtime organization default; selected provider inputs use project dotenv.
  Explicit dotenv bootstrap retains once-per-process and environment precedence.
  Publication is individually verified and can leave partial effects. The offline
  example and arithmetic inference diagnostic do not close MA-04 workflow proof.
- Prepared workflow delta: `orket demo local-agent` reuses governed-agent
  submission, native children and verification with the packaged ticket example.
  Fresh contained directories retain verified inputs, SQLite state and a report
  projection. Owned publication settles through interruption; partial effects
  remain visible. Existing destinations refuse. Actual-provider execution is
  separate from controlled HTTP tests, and native Mac MA-04 remains mandatory.
- Process acceptance delta: the installed native-control producer reuses existing
  tests and independent process observers outside the checkout. Candidate hashes,
  package inputs, installed origins, dependency tooling and all mandatory JUnit
  items remain explicit. Its process-only report cannot close full MA-09 or Mac
  acceptance, including when the explicit Windows control mode passes.
- Combined acceptance delta: the full producer binds retained components to
  unchanged installed bytes/dependencies and actual setup/provider/restart work.
  All nine cases are required; Metal allocation alone cannot replace inference
  against that owned server. Server cleanup/capture and port closure remain
  mandatory. Windows CONTROL_PASS is partial success, never native acceptance.
  The Gitea job and operator runbook retain the native ownership/access blockers.
- Missing-provider evidence correction (2026-10-07): the held-loopback control
  uses the diagnostic's valid default timeout and must observe connection failure,
  provider closure and settled native diagnostics. Producer and both receipt
  consumers share admission; configuration, authentication and catalog failures
  cannot substitute. Earlier nonzero-only receipts require fresh proof.

## Migration Plan
1. Compatibility window: existing Windows/Linux entrypoints and ownership rules
   remain unchanged; no Darwin fallback is introduced.
2. Migration steps: implement the canonical Mac queue and update actual public
   behavior/command owners together with their contracts.
   Hardware consumers must retain null GPU metrics and treat None fit as unknown;
   they must not convert unknown observations to zero or a supported-model claim.
3. Validation gates: MA-01 through MA-09, affected regression and governance
   checks, native Apple Silicon evidence and actual Metal inference.

## Rollback Plan
1. Rollback trigger: unsupported guarantees, failed native proof or regressions.
2. Rollback steps: retain fail-closed unsupported execution; do not publish a Mac
   support claim. Record blockers without erasing required acceptance cases.
3. Data/state recovery notes: no data migration or cloud provisioning in this delta.

## Versioning Decision
- Version bump type: none for this uncommitted planning batch; eventual release
  follows the canonical versioning policy and actual shipped behavior.
- Effective version/date: requirements accepted 2026-10-06; implementation pending.
- Downstream impact: no new supported runtime target until native acceptance.
