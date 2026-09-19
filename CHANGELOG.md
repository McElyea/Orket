# Changelog

All notable changes to Orket will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.25] - 2026-09-18 - "Owned bundle commands"

### Fixed
- Route bundle validation, packing and inspection through application authority and retained filesystem workers.
- Verify packed archives before and after replacement; reject changed admitted manifests and missing required members.
- Retire the core manifest file loader and interface-owned bundle policy helpers.
- Move offline ledger verification and CLI connector registry composition into application.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Migration and limits: `docs/architecture/CONTRACT_DELTA_BUNDLE_AUTHORITY_CD_2026-09-18.md`.
- Stability: a scoped architectural-truth checkpoint; C/D and whole-lane acceptance remain open.

## [0.6.24] - 2026-09-18 - "Explicit turn time"

### Fixed
- Require an explicit timestamp or explicit absence when constructing core execution turns.
- Capture the Agent's supplied clock before awaiting; retain the UTC host clock as its application default.
- Stop inventing response timestamps when replaying or resuming stored turns whose checkpoints lack that observation.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Migration and limits: `docs/architecture/CONTRACT_DELTA_TURN_TIME_D_2026-09-18.md`.
- Stability: a scoped architectural-truth checkpoint; C/D and whole-lane acceptance remain open.

## [0.6.23] - 2026-09-18 - "Owned protocol queries"

### Fixed
- Delegate protocol CLI dispatch to application services and retain replay/parity workers through cancellation and API shutdown.
- Capture query inputs before awaiting, resolve paths off the event loop, and refuse requested or discovered session paths and linked files escaping the selected query root.
- Require observed events on both sides of replay comparisons; an empty baseline cannot make its campaign pass.
- Preserve explicit CLI file operands, HTTP error mappings and populated comparison fields; add comparison scope, evidence status and event counts.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Migration and limits: `docs/specs/PROTOCOL_QUERY_LIFETIME.md` and `docs/architecture/CONTRACT_DELTA_PROTOCOL_QUERIES_CD_2026-09-18.md`.
- Stability: this checkpoint retains separate source, installed and quality observations in the architectural-truth plan; whole-lane acceptance remains open.

## [0.6.22] - 2026-09-18 - "Owned API startup"

### Fixed
- Retain API initialization through shutdown, capture broadcaster inputs before admission, and retain completed broadcaster failures.
- Own log subscription cleanup and report effective anonymous access in the startup security posture.
- Keep benchmark child commands in the selected Python environment and repair retained quality fixtures without relaxing runtime checks.
- Enable Git long-path support only for a marshaller clone operation and its owned repository; native working-directory launch limits still apply.
- `compatibility_status`: `preserved`
- `affected_audience`: `all`
- `migration_requirement`: `none`
- Contract and proof limits: `docs/architecture/CONTRACT_DELTA_API_STARTUP_D_2026-09-18.md` and the architectural-truth plan.
- Stability: source, installed and full-suite results are recorded separately in the active plan; this checkpoint is not whole-lane acceptance.

## [0.6.21] - 2026-09-18 - "Captured settings operations"

### Changed
- Capture nested runtime settings and per-operation paths; remove the process-wide data/path cache and implicit pytest behavior.
- Own settings file workers through cancellation, atomically replace and verify published files, and refuse malformed or unreadable settings.
- Retain preference migration progress for restart after partial publication, with native admission for cooperating writers and explicit conflict refusal.
- Require a captured snapshot or pre-loop bootstrap for synchronous reads; explicitly isolate settings in the test fixture.
- Bind persisted CLI settings after onboarding, and retain admin API file operations through request shutdown.
- Refuse stale concurrent admin updates with HTTP 409 and compare retained migration values with JSON types preserved.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Migration: `docs/specs/SETTINGS_INPUT_OWNERSHIP.md` and `docs/architecture/CONTRACT_DELTA_SETTINGS_INPUTS_CD_2026-09-18.md`.
- Stability: candidate verification and remaining full-plan gates are recorded in the architectural-truth plan. Work-hours commits and tags remain local.

## [0.6.20] - 2026-09-18 - "Owned webhook applications"

### Changed
- Move Gitea review coordination into application services and replace the module-global webhook app with distinct factory results and captured configuration.
- Share request, background task and shutdown ownership with the API; retain review engine cleanup and unexpected background failures.
- Accept native Gitea HMAC signatures and translate its actual review events; preserve delivery identity through HTTP ingress and refuse conflicting review vocabulary.
- Keep review-cycle thresholds and explicit unsupported sandbox behavior; document delivery deduplication and remote-effect limits.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Migration: `docs/specs/WEBHOOK_RUNTIME_LIFECYCLE.md` and `docs/architecture/CONTRACT_DELTA_WEBHOOK_AUTHORITY_CD_2026-09-18.md`.
- Stability: checkpoint verification and unresolved gates remain in the active architectural-truth plan. The full remediation goal remains open; commits and annotated tags stay local during work hours.

## [0.6.19] - 2026-09-18 - "Interface-owned entrypoints"

### Changed
- Move admitted API, CLI and webhook factories into `orket.interfaces.runtime_entrypoints`; application retains module-profile authorization and engine construction.
- Remove the three runtime transport-factory exports and migrate callers without a forwarding shim.
- Render the existing module-resolution code and reason in fatal CLI diagnostics.
- Clarify that distinct API owners share the invocation's default store unless separate durable roots are selected.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Migration: `docs/architecture/CONTRACT_DELTA_INTERFACE_COMPOSITION_C_2026-09-18.md`.
- Stability: focused source and installed proof is recorded in the active architectural-truth plan. Full platform, hosted Quality, provider, C/D/E/CAP and whole-lane acceptance remain open. Commit and annotated tag stay local during work hours.

## [0.6.18] - 2026-09-18 - "Owned coordinator transitions"

### Changed
- Replace standalone coordinator module-global owners with an explicit application factory and captured storage/clock inputs.
- Capture nested results, serialize admitted card/publication transitions and retain their lifetime through cancellation and close.
- Retain unexpected transition failures, refuse subsequent admission with 503 and prevent a clean shutdown claim.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Migration: `docs/specs/COORDINATOR_RUNTIME_LIFECYCLE.md` and `docs/architecture/CONTRACT_DELTA_COORDINATOR_AUTHORITY_CD_2026-09-18.md`.
- Stability: 39 selected cases pass in source and fresh Windows/Linux Python
  3.11 installations, with real HTTP/SQLite, package/CLI and cleanup checks.
  Original counterexamples and two corrected test expectations remain retained.
  Full platform/Quality/provider, C/D/E/CAP and whole-lane acceptance remain open.
  Commit and annotated tag remain local during work hours.

## [0.6.17] - 2026-09-18 - "Atomic flow authoring"

### Changed
- Capture submitted flow definitions before awaiting; enforce revision guards atomically in SQLite and refuse create-id collisions.
- Application owns flow storage composition, supplied clock/identity inputs and bounded single-card run admission.
- Retain admitted database operations and cleanup through cancellation; interrupted requests may already have committed.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Migration: `docs/architecture/CONTRACT_DELTA_FLOW_AUTHORITY_CD_2026-09-18.md`.
- Stability: 46 selected cases pass in source and fresh Windows/Linux Python 3.11
  installations, with package/CLI/cleanup checks. Original counterexamples and
  the corrected shutdown-response test expectation remain retained. This is a
  focused checkpoint; fresh Python 3.12, broad platform/quality/provider gates
  and whole-lane acceptance remain open. Commit and annotated tag remain local.

## [0.6.16] - 2026-09-18 - "Captured HTTP verification"

### Changed
- Application owns sandbox HTTP verification, captured target/scenario inputs and client cleanup; core interprets immutable observations.
- Compare every expected JSON value, including falsy values and null, without boolean/numeric coercion. Missing endpoints count as failed scenarios.
- Retain cleanup through repeated cancellation, stop further dispatch and publish no new scenario state on cancellation.
- Move the shared native fixture payload into the execution adapter without changing its executable contents.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Migration: `docs/architecture/CONTRACT_DELTA_SANDBOX_VERIFICATION_CD_2026-09-18.md`.
- Stability: scoped proof passes 2808 source cases and 2803 installed
  cases in each Windows/Linux Python 3.11/3.12 cell, plus eight actual llama.cpp
  regressions and three opted-in memory integrations. Five repository-only
  checks stay in source proof. Original false passes and candidate regressions
  remain retained. Docker deployment, full-workload completion and whole
  architectural-truth acceptance are not established. Commit and tag remain local.

## [0.6.15] - 2026-09-18 - "Explicit provider preparation"

### Changed
- Application composition supplies provider preparation through a core port over captured inputs.
- Require admitted provider, model request and endpoint identity before inference; client subclasses and mock transports no longer bypass preparation.
- Move pure endpoint normalization into core and migrate its internal callers without a forwarding shim.
- Bind the Ollama client's default host explicitly instead of inheriting an excluded ambient host.
- `compatibility_status`: `breaking`
- `affected_audience`: `internal_only`
- `migration_requirement`: `required`
- Internal migration: `docs/architecture/CONTRACT_DELTA_PROVIDER_PREPARATION_CD_2026-09-18.md`.
- Stability: scoped proof passes: 2,715 source cases, 2,710 installed runtime
  cases in each Windows/Linux Python 3.11/3.12 cell, eight actual llama.cpp
  regressions and three opted-in memory integrations. Five repository-only
  checks remain in source proof. The final Windows 3.12 proof uses a declared
  outer-budget retry. Original failures and verified fixture-load
  cleanup are retained; the earlier stock-clock regression remains unexplained.
  Native CLI environment capture, concurrent preparation/shutdown and full
  architectural-truth acceptance remain open. Commit and tag remain local.

## [0.6.14] - 2026-09-18 - "Captured SDK memory requests"

### Changed
- Move SDK memory policy and scope coordination into application ownership.
- Capture nested memory-write request values before submitting work to the synchronous bridge.
- Preserve existing memory controls, profile policy, extension namespaces and SDK wire types.
- Admit SQLite WAL connections with a bounded busy-family retry that closes failed
  bootstrap connections and never replays caller statements or commits.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Internal import migration: `docs/architecture/CONTRACT_DELTA_SDK_MEMORY_OWNER_CD_2026-09-18.md`.
- Stability: scoped source and installed proof passes: 2,634 source cases, 2,629
  runtime cases in each of four Windows/Linux Python 3.11/3.12 cells, eight actual
  llama.cpp regressions and three opted-in memory integrations. Five repository-only
  checks remain in source proof. Shared bridge/store lifetime, competing
  profile-write atomicity and memory clocks remain outside this scoped guarantee.
  The full architectural-truth goal remains active.

## [0.6.13] - 2026-09-18 - "Owned tool-result publication"

### Changed
- Capture nested tool-result and protocol-receipt inputs before file publication awaits.
- Retain admitted file workers and the enclosing turn owner through repeated cancellation and caller timeout.
- Preserve worker errors during interruption; keep partial-file and unresolved-dispatch truth explicit.
- Consolidate protocol and ordinary result persistence under one application module.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Internal import migration and limitations: `docs/architecture/CONTRACT_DELTA_TOOL_RESULT_WORKERS_D_2026-09-17.md`.
- Stability: scoped local checkpoint. The source recheck and four fresh installed
  Windows/Linux Python 3.11/3.12 cells each pass 2,066 selected cases. Eight actual
  llama.cpp regressions and two actual file-write/publication turns pass. The initial
  source rename failure and incomplete Linux invocation remain retained; historical
  native and rename causes are unresolved. Full architecture, quality, capability
  and whole-lane gates remain open. No remote Git publication is included.

## [0.6.12] - 2026-09-17 - "Captured prompt and scheduler inputs"

### Changed
- Move prompt-policy preparation and SDK model composition into application ownership.
- Capture provider settings and nested request inputs before asynchronous preparation.
- Bind registry provenance to one read and retain worker lifetime through cancellation.
- Return immutable policy values with detached transport and telemetry exports.
- Carry the supplied control-plane clock into scheduler publication and failure cleanup.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Follow `docs/architecture/CONTRACT_DELTA_PROMPT_POLICY_CD_2026-09-17.md`.
- Scheduler clock scope: `docs/architecture/CONTRACT_DELTA_SCHEDULER_CLOCK_D_2026-09-17.md`.
- Stability: partial local checkpoint. 2,036 selected source cases and three
  installed Windows/Linux cells pass; Windows 3.12 passes 2,035 and fails one
  native-agent fixture with `Connection lost`. Installed acceptance remains open.
  Eight actual llama.cpp regressions, an installed policy/factory flow and four
  live role-response checks pass. Lifecycle fixtures use explicit clocks;
  production reversal rejection and native deadlines are unchanged. Retained
  failures, remaining architecture debt and whole-plan acceptance stay open.

## [0.6.11] - 2026-09-17 - "Captured model-selection inputs"

### Changed
- Move model-selection preparation and compliance disposition into application ownership.
- Prompt strategies receive immutable values; retire the mutable selector and last-call state.
- Retain score-file provenance and owned preparation through cancellation.
- Move preview coordination into application services; own API driver bootstrap and transport cleanup.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Follow `docs/architecture/CONTRACT_DELTA_MODEL_SELECTION_CD_2026-09-17.md`.
- Stability: local checkpoint. 1,853 selected cases pass in source and each of four
  fresh installed Windows/Linux Python 3.11/3.12 cells. Eight actual llama.cpp regressions
  and an installed selection/compliance/inference flow pass. Full-plan acceptance,
  remaining dependency/input debt and historical failure diagnoses remain open.

## [0.6.10] - 2026-09-17 - "Application-owned strategy composition"

### Changed
- Move decision-node registration and settings capture into application composition.
- Restrict tool strategy output to known tool names; application owns executable bindings.
- Retire model-client policy nodes in favor of an application factory over captured settings.
- Supply immutable loop limits and apply organization overrides in the application loader.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Follow `docs/architecture/CONTRACT_DELTA_DECISION_INPUTS_CD_2026-09-17.md`.
- Stability: local checkpoint. 1,815 selected cases pass in source and each of four
  fresh installed Windows/Linux Python 3.11/3.12 cells. Eight actual llama.cpp regressions,
  one application-factory live flow and changed-file Ruff pass. Full architectural-truth
  acceptance, remaining dependency debt and historical failure diagnoses remain open.

## [0.6.9] - 2026-09-17 - "Captured API authority and packaged scaffolds"

### Changed
- Move authentication, explorer containment and board observations from replaceable
  strategy methods into application services and owned filesystem adapters.
- Capture each app's security/CORS settings, EOS baseline and timezone; use its
  explicit runtime clock. Board reads use the selected project root.
- Retain filesystem observations through cancellation, timeout and shutdown.
- Package both extension scaffold templates and verify materialized output;
  `orket ext init` no longer requires documentation beside the installed module.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Follow `docs/architecture/CONTRACT_DELTA_API_AUTHORITY_INPUTS_CD_2026-09-17.md`
  for retired internal strategy methods and application settings capture.
- Stability: local checkpoint. The full selected source suite and all four fresh
  installed cells pass 1,751 cases each; eight actual llama.cpp cases and changed-file
  Ruff pass. Whole-plan acceptance, historical clock/resume failures and live pipeline
  completion remain open. Exact evidence and limits are in the canonical plan.

## [0.6.8] - 2026-09-17 - "Captured provider preparation candidate"

### Changed
- Capture provider preparation settings and nested target metadata; move provider
  identity and target values to core contracts.
- Retain admitted inventory/load workers through cancellation and timeout; preserve
  their failures and require a loaded-model observation before reporting load success.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Follow `docs/architecture/CONTRACT_DELTA_PROVIDER_INPUTS_CD_2026-09-17.md` for core
  imports, captured settings, immutable inventory records and load-result semantics.
  SDK remains `0.7.0a1`; serialized target fields remain unchanged.
- Stability: local checkpoint; source passes 1,310 selected cases and the current
  four-cell installed gate passes. Eight actual llama.cpp cases and seven
  separate mixed feature/pipeline cases pass. Full changed-file Ruff, historical
  clock/resume investigations and full-plan gates remain open.
  The live pipeline workload retains `terminal_failure` for unverified COD-1/REV-1
  completion; its passing truth-reporting test does not establish workload success.

## [0.6.7] - 2026-09-17 - "Protocol graph publication candidate"

### Changed
- Move deterministic protocol graph values to core and owned file effects to storage.
- Publish graphs from committed terminal ledger events, verify file replacement,
  and repair missing or corrupted projections on repeated finalization.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Follow `docs/architecture/CONTRACT_DELTA_PROTOCOL_GRAPH_CD_2026-09-17.md` for removed
  runtime imports, async replay and post-append projection failure handling.
  SDK remains `0.7.0a1`; graph schema and node/edge meaning are unchanged.
- Stability: local checkpoint with partial installed proof. Source and Windows
  pass 1,213 selected cases; Linux 3.11 has two resume failures and Linux 3.12 has
  one. All 18 graph cases pass in every cell, and eight actual installed llama.cpp
  cases pass. Broader installed acceptance and full-plan gates remain open.

## [0.6.6] - 2026-09-17 - "Governed invocation lifetime candidate"

### Changed
- Retain governed child ownership from admission through native launch and cleanup,
  including repeated caller cancellation and pending-launch operator cancellation.
- Refuse duplicate stop claims and cross-loop invoker reuse; capture cancellation
  payloads before awaiting and preserve failed cleanup as an explicit failure.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Follow `docs/architecture/CONTRACT_DELTA_AGENT_INVOCATION_LIFETIME_D_2026-09-17.md`.
  SDK remains `0.7.0a1`; request deadlines and child framing are unchanged.
- Stability: local checkpoint. Source and four installed proof unions cover 1,201
  selected cases through retained full runs and 28-case explicit-clock follow-ups
  on the unchanged wheel; eight actual installed llama.cpp cases pass. Host-clock
  stability, prior Linux deadlines, full-suite/hosted CI and whole-lane acceptance remain open.

## [0.6.5] - 2026-09-17 - "Dual-ledger recovery candidate"

### Changed
- Move dual-ledger lifecycle authority to application services with bound journals,
  native admission, verified backend effects and retained cancellation ownership.
- Refuse unbound legacy recovery, conflicting starts/terminal content and later
  lifecycle transitions while a session's mirror remains unresolved.
- Read child stdin without Python's buffered-input shutdown lock so a crashing
  governed workload exits with its diagnostic instead of an interpreter abort.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Follow `docs/architecture/CONTRACT_DELTA_DUAL_LEDGER_CD_2026-09-17.md` for imports,
  journal migration and telemetry callback execution. SDK remains `0.7.0a1`.
- Stability: implementation candidate; installed, full-suite/hosted CI and broader
  architectural-truth acceptance remain open.

## [0.6.4] - 2026-09-17 - "Protocol ledger ownership checkpoint"

### Changed
- Move pure protocol hashing, invocation contracts and error/result vocabulary
  into core; move operation-commit persistence into storage adapters.
- Reload first-winner state under native local ownership, refuse malformed
  history and invalid event sequences, and verify persistence before publication.
- Retain protocol file workers and repository ownership through cancellation or
  timeout; capture caller-owned nested ledger inputs before the first await.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Update internal imports and follow the storage refusal/retry instructions in
  `docs/architecture/CONTRACT_DELTA_PROTOCOL_LEDGER_CD_2026-09-17.md`. Valid existing
  registry JSON and protocol hashes retain their formats; SDK remains `0.7.0a1`.
- Stability: scoped branch checkpoint. Full C/D, quality, capability,
  full-suite/hosted CI, release readiness and whole-lane acceptance remain open.

## [0.6.3] - 2026-09-16 - "Architectural truth remediation checkpoint"

### Changed
- Retain the accumulated architectural-truth repairs for authorization, durable
  effects and evidence, completion/replay, cancellation and shared run authority.
  Preserve scoped BT-1 through BT-5 acceptance and its documented claim limits.
- Separate core values/contracts from application effects, propagate explicit
  clock inputs, and move governed-agent CLI coordination into application services.
  Submission captures immutable options and owns preparation/provider cleanup.
- Replace the dependency denylist with one classified allowed-edge policy and
  fail-closed import analysis. Existing dependency failures remain visible.
- Pair this branch candidate with SDK `0.7.0a1`; model receipts retain their
  versioned semantics. Use the migrations and quarantined-history dispositions in
  the architectural-truth plan and its durable contracts.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Operator/author action: install the pinned SDK alongside core, follow
  `docs/requirements/sdk/VERSIONING.md`, and apply the relevant runtime-store,
  retained-history and internal-import migrations before resuming existing work.
- Stability: this is a versioned branch checkpoint. C/D, E1/E2, capability,
  fresh full-suite/hosted CI, release-readiness and whole-lane acceptance gates
  remain open. Exact historical and current proof scopes live in
  `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`.

## [0.6.2] - 2026-09-11 - "llama.cpp defaults and Qwen3.8 promotion"

### Changed
- Make llama.cpp the shared default across provider-neutral runtime and proof
  paths, followed by explicitly selected LM Studio and Ollama. Never switch
  providers when the configured llama.cpp endpoint is unavailable.
- Promote the exact Qwen3.8 Q4_K_L profile with the packaged text ChatML
  template, native render/token verification, and pinned llama.cpp b10809 with
  prompt caching enabled. Remove the older no-cache workaround from current setup.
- Harden template audits and promotion gates against missing bytes, incomplete
  reruns and incorrect tool arguments. Include validator details in corrective
  prompts; report empty continuation replay as `no_decisions`.
- Preserve the updated architectural-truth remediation plan as remaining work.
- Stability: verified bounded trusted-extension workflows and this exact local
  model/profile; no arbitrary coding-objective, production-soak or containment claim.
- `compatibility_status`: `breaking`
- `affected_audience`: `operator_only`
- `migration_requirement`: `required`
- Operator action: follow `docs/RUNBOOK.md` for the pinned server/template setup;
  select LM Studio or Ollama explicitly when intended. Keep SDK 0.6.0 and
  reference extension 0.2.0. Existing stored run configuration is unchanged.
- Release verification: `docs/releases/0.6.2/PROOF_REPORT.md`.

## [0.6.1] - 2026-09-10 - "Local provider truth hardening"

### Added
- Add the llama.cpp governed-agent integration proof path, provider identity
  helpers, and live/provider-focused regression coverage.
- Add the behavioral-truth architecture review and its runnable evidence packet
  for unresolved outward approval, evidence, and verification risks.

### Changed
- Align governed-agent local provider wiring, provider truth tables, streaming
  scripts, runbook notes, and local-prompting authority around the canonical
  local provider target behavior.
- `compatibility_status`: `preserved_with_additive_surfaces`
- `affected_audience`: `operators; extension_authors`
- `migration_requirement`: `none`

## [0.6.0] - 2026-09-10 - "Governed continuous agents"

### Changed
- Complete the governed continuous-agent roadmap lane: public SDK contracts,
  separate external reference package, durable wake supervision, schedules and
  authenticated webhooks, staged input, host-owned progress/memory/control,
  approval-gated effects and observation-only recovery after process loss.
- Ship the local prompt registry in core and complete per-app API composition
  isolation required by the governed-agent supervisor.
- Release with standalone SDK 0.6.0 and external reference 0.2.0. Core no longer
  owns SDK namespace files; install both pinned wheels and reinstall SDK last
  when upgrading a historical bundling core.
- Stability: bounded trusted-extension workflows are supported within the
  tested local Ollama scope; no hostile-code containment, comparative model
  quality, cloud-provider expansion, or production-soak guarantee is claimed.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Operator/author action: use core 0.6.0 with SDK 0.6.0, validate extracted
  extension 0.2.0 strictly, and follow the release proof report's upgrade steps.
  The legacy source wrapper and hidden `--rock` alias remain deprecated through
  0.6.x, with removal tracked in the architectural-truth lane.
- Proof and accepted closeout: `docs/releases/0.6.0/PROOF_REPORT.md`.

## [0.5.10] - 2026-09-07 - "The Governed Agent Foundations Cut"

### Added
- **Governed Agent Slices 0-5**: Added SDK contracts, strict manifest admission, framed child-process IPC, durable SQLite execution records, deterministic and Ollama-backed bounded iterations, inspection, replay, cancellation, and approval-governed file effects.
- **Governed Examples and Quickstarts**: Added the installed governed-action quickstart and package-owned governed-run demo, scenario, evidence ledger, inspection, and replay surfaces.
- **Architectural Truth Evidence**: Added command-root, process-exit, persistence, package-data, and per-app API-runtime ownership deltas, proof records, and regression coverage.

### Changed
- **Canonical Command Root**: Moved the installed `orket` entrypoint to `orket.cli:main`, with `orket runtime` owning card execution while the source wrapper remains supported through the `0.5.x` line.
- **API Runtime Ownership**: Isolated runtime state in an app-scoped container with per-factory ownership, tracked background tasks, and idempotent teardown.
- **Extension SDK Development Line**: Advanced the unreleased SDK package to `0.5.0a1` and added the public governed-agent schema, models, broker protocols, validation, fixtures, and testing helpers.

### Security
- **Fail-Closed Agent Admission**: Agent workload discriminators now require the typed protocol declaration across author validation, install, catalog reload, and invocation, and child configuration cannot create host-bound broker capabilities.
- **Governed Effects**: File mutations require host-owned observation, approval, reservation, journal, checkpoint, reconciliation, and explicit resume paths.

### Compatibility
- `compatibility_status`: `preserved_with_additive_surfaces`
- `affected_audience`: `operators; extension_authors; API embedders`
- `migration_requirement`: `none for existing 0.5.x callers; use orket runtime for the canonical installed CLI and the 0.5.0a1 SDK governed-agent contracts for new agent extensions`

### Required Operator or Extension-Author Action
- Existing source-wrapper and non-agent extension paths remain supported. Operators should adopt `orket runtime` as the canonical installed runtime command; governed-agent extensions must use the strict SDK protocol and host capability declarations documented in the runbook.

## [0.5.9] - 2026-05-19 - "The llama.cpp First-Slice Cut"

### Added
- **llama.cpp First-Slice Provider Path**: Added unpromoted `llama_cpp` provider support for the operator-managed Qwen GGUF path, including bounded GGUF inventory, profile resolution, OpenAI-compatible invocation, request-shape telemetry, preflight support, conformance harness support, and focused regression coverage.
- **llama.cpp Closeout Archive**: Archived the completed first-slice implementation lane under `docs/projects/archive/local-provider-compatibility/2026-05-19-LLAMA-CPP-FIRST-SLICE-CLOSEOUT/` with live preflight and conformance-smoke proof.

### Changed
- **Roadmap Authority**: Cleared the completed llama.cpp Priority Now item and updated current authority plus the local-prompting contract to keep `llama_cpp` implemented but unpromoted until promotion-volume and template-audit gates pass.
- **Apophenia Model Selection Contract**: Extended the Apophenia external-extension contract with Orket-delegated model selection and model catalog endpoint expectations.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `operator_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Operators may run the first-slice `llama_cpp` path only as an unpromoted local-provider path. Promotion still requires a later explicit promotion-readiness lane with full corpus volume and ChatML template audit or whitelist evidence.

## [0.5.8] - 2026-05-09 - "The Authority Map Test Recovery Cut"

### Changed
- **Machine-Readable Authority Map**: Synchronized the `CURRENT_AUTHORITY.md` JSON payload date and active spec index with the Apophenia contract promotion so the platform authority-map contract passes again.

### Fixed
- **Root Pytest Verification Debt**: Recovered the stale authority-map contract failure and proved the canonical `python -m pytest -q` command completes successfully.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `operator_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- No immediate action required. The canonical root test command remains `python -m pytest -q`.

## [0.5.7] - 2026-05-09 - "The Apophenia Closeout Cut"

### Added
- **Apophenia Durable Contract**: Promoted the completed Apophenia external-extension contract to `docs/specs/APOPHENIA_EXTERNAL_EXTENSION_CONTRACT.md` and named it in the current authority snapshot.
- **Apophenia Closeout Archive**: Archived the completed Apophenia requirements and implementation plan under `docs/projects/archive/apophenia/2026-05-09-CLOSEOUT/` with a closeout record.

### Changed
- **Future Lane Hygiene**: Removed the completed Apophenia authority packet from the future project lane so the external implementation has one durable Orket-side contract authority.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `extension_author_only`
- `migration_requirement`: `update Apophenia contract references from docs/projects/future/apophenia/CONTRACT.md to docs/specs/APOPHENIA_EXTERNAL_EXTENSION_CONTRACT.md`

### Required Operator or Extension-Author Action
- Extension authors should use `docs/specs/APOPHENIA_EXTERNAL_EXTENSION_CONTRACT.md` as the Orket-side Apophenia contract authority. The implementation root remains `C:\Source\Orket-Extensions\Apophenia`.

## [0.5.6] - 2026-05-08 - "The Apophenia Authority Cut"

### Added
- **Apophenia Authority Packet**: Added the Apophenia requirements, implementation plan, and durable contract under `docs/projects/future/apophenia/`, pointing Phase 0+ implementation to the external root `C:\Source\Orket-Extensions\Apophenia`.
- **Phase 3 Proof Closure**: Recorded the completed live-observation, constellation-layout, browser sanitizer, and Python `defusedxml` proof gates for Apophenia.

### Changed
- **Dependency Authority**: Updated Apophenia's planned Readability dependency authority to `@mozilla/readability` `0.6.0`, matching the external implementation package and avoiding the vulnerable `0.5.0` pin.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `extension_author_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- No immediate action required. Apophenia implementation work now uses `C:\Source\Orket-Extensions\Apophenia`; Orket core remains the planning and contract authority only.

## [0.5.5] - 2026-05-04 - "The Trust Handoff And Runtime Shim Removal Cut"

### Added
- **Trust Handoff Packet 1**: Added the durable single-output policy-compatible trust handoff contract, offline package emitter and verifier, corruption suite, B-admission integration, ledger event authority, API/runtime tests, and archived Packet 1 closeout.

### Changed
- **Runtime Import Authority**: Removed the deprecated `orket.orket` compatibility shim after the post-release maintenance cycle passed and migrated live imports to `orket.runtime`.
- **Roadmap Authority**: Archived the completed Trust Handoff Packet 1 lane, cleared the completed shim-removal future lane, and refreshed the dependency graph snapshot.

### Compatibility
- `compatibility_status`: `changed`
- `affected_audience`: `legacy_import_callers; proof_operators`
- `migration_requirement`: `replace from orket.orket imports with from orket.runtime`

### Required Operator or Extension-Author Action
- Legacy callers that still import `orket.orket` must migrate to `orket.runtime`.
- Operators using Packet 1 handoff evidence should use `docs/specs/TRUST_HANDOFF_PACKET1_V1.md` and the canonical proof commands listed there.

## [0.5.4] - 2026-05-03 - "The Policy-Rejection Fixture Cut"

### Added
- **Policy-Rejection Witness Fixture**: Added the real governed-run `outward_run_write_file_policy_rejected_v1` package fixture, proof runner, verifier support, invariant checks, and contract coverage proving policy rejection before approval, tool invocation, or commitment.
- **Policy-Rejection Corruption Coverage**: Activated ORP-CORR-031 over the policy-rejected base package and extended the corruption suite to require approved, denied, and policy-rejected bases with zero blocked corruptions for admitted single-turn scopes.

### Changed
- **Outward Runtime Truth**: Changed policy-rejected outward runs to record stable `proposal_ref` evidence and complete without commitment authority when no tool effect occurred.
- **Proof Authority And Roadmap**: Archived the policy-rejection fixture slice, updated current authority and outward proof specs, and cleared the active Priority Now roadmap lane while keeping remaining extension families future-hold.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `operator_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- No immediate action required. Operators evaluating policy-rejection proof should use the frozen policy-rejected witness package and `outward_run_write_file_policy_rejected_v1` verifier scope.

## [0.5.3] - 2026-05-02 - "The Outward Run Proof Kernel Cut"

### Added
- **Outward Run Proof Kernel**: Added the approved single-turn outward run witness, invariant, claim-tier, and assurance-case contracts, plus package emission, verification, committed-artifact validation, corruption-suite, and campaign tooling for `outward_run_write_file_approved_v1`.
- **Proof Fixtures And Coverage**: Added frozen approved-path package fixtures and contract/script tests covering witness package verification, assurance validation, artifact validation, corruption detection, and campaign stability.

### Changed
- **Proposal Evidence Anchors**: Anchored redacted prompt, redacted response, and proposal-extraction hashes into `proposal_made` ledger payloads and aligned current authority plus event taxonomy with the expanded evidence surface.
- **Roadmap Authority**: Archived the completed outward run proof kernel lane and queued the denial-fixture proof extension as the active priority lane.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `operator_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- No immediate action required. Operators using outward run proof packages should use the new witness package verifier, committed-artifact validator, and corruption suite for approved-path proof claims.

## [0.5.2] - 2026-04-26 - "The Multi-Step Governed Evidence Cut"

### Added
- **Multi-Step Governed Execution**: Added ordered `governed_tool_sequence` support so outward runs can perform one live model-produced governed tool proposal per turn while preserving approval-before-effect execution.
- **Governed Negative-Path Proof Bundles**: Added denial, mixed-decision, multi-step approval, and out-of-scope policy-rejection evidence packets with ledger verification, tamper checks, and execution graphs.

### Changed
- **Approval And Policy Outcomes**: Changed denial handling to complete without invoking the denied connector effect, added `proposal_policy_rejected` ledger authority for out-of-scope model proposals, and aligned ledger export groups with the new decision event.
- **Outward Model Evidence**: Split model prompt/response/invocation evidence into turn-specific artifacts and tightened redaction for model prompt payloads.
- **Operator Contracts**: Updated current authority, API contract, event taxonomy, ledger export contract, and runbook guidance for multi-turn, denial-path, and policy-rejection proof.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `operator_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- No immediate action required. Operators using public proof bundles should keep denial-path and out-of-scope policy-rejection evidence with the same ledger verification and tamper checks as approved-path proof.

## [0.5.1] - 2026-04-26 - "The Live Governed Proof Bundle Cut"

### Added
- **Live Governed Run Proof Bundle**: Added the final `live_governed_run_bundle_v1` evidence packet proving a local outward pipeline run with live Ollama model invocation, model-output-derived proposal extraction, approval-before-effect, outward evidence graph capture, full and partial ledger verification, tamper failure, redaction, and manifest hashing.
- **Outward Model Evidence Trail**: Added sanitized outward model prompt, response, invocation, and proposal-extraction evidence files, and anchored model invocation and response hashes into the `proposal_made` ledger payload.
- **Outward Pipeline Evidence Graph**: Added direct outward `run_id` support to the run-evidence graph emitter so outward runs no longer depend on legacy `runs/<session_id>/` graph assumptions.

### Changed
- **Governed Outward Execution**: Changed the explicit outward execution slice so `acceptance_contract.governed_tool_call` constrains the governed tool family while the approval proposal is created from the validated live model-produced tool call.
- **Runbook Proof Workflow**: Documented the live governed run evidence bundle workflow, synthetic-shortcut probe pattern, outward graph command, offline ledger verification sequence, and public claim boundaries.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `operator_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- No immediate action required. Public proof operators should use the runbook workflow and keep synthetic-shortcut probes, redaction, partial-ledger verification, and tamper verification in the bundle report.

## [0.5.0] - 2026-04-26 - "The Governed Outward Pipeline Cut"

### Added
- **Outward Governed Runtime Loop**: Added the NorthstarRefocus outward-facing pipeline covering API and CLI work submission, approval queue review, approve/deny/timeout decisions, persisted run inspection, live event streaming, ledger export, offline ledger verification, built-in connector hardening, and outbound policy-gate enforcement.
- **Ledger Export v1 Contract**: Added `ledger_export.v1` as the operator-visible export and offline verification contract for outward pipeline run events, including canonical hash-chain verification, partial-view anchors, event groups, and export audit semantics.
- **Release Proof Report**: Added the `0.5.0` minor-release proof report for the completed NorthstarRefocus roadmap lane.

### Changed
- **Roadmap And Authority Posture**: Archived the completed NorthstarRefocus lane, moved the NorthStar disposable AWS smoke setup lane to paused checkpoint status pending Bedrock access, and aligned current authority, runbook, security, API, and connector docs to the shipped outward pipeline surface.
- **Startup And Outbound Safety**: Hardened outward API startup posture, CORS defaults, outbound projection redaction, connector validation, HTTP allowlisting, and policy-safe serialization before operator-visible responses.

### Stability Statement
- The stable surfaces for this release are the local outward API/CLI governed-run loop, approval decision surfaces, persisted outward run inspection, `ledger_export.v1`, and offline ledger verification. Graphical UI, third-party connector discovery, durable SSE pub/sub, legacy artifact import, and paused provider-backed AWS/Bedrock proof lanes remain outside this release.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `operator_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- No immediate action required. Operators running the outward API must configure `ORKET_API_KEY`; browser clients must explicitly configure trusted CORS origins through `ORKET_ALLOWED_ORIGINS`.

## [0.4.50] - 2026-04-25 - "The Palmyra X5 Smoke Maintenance Cut"

### Added
- **Writer Palmyra X5 Live Smoke Support**: Added Palmyra X5 direct and US geo inference-profile ids to the Terraform plan reviewer live-smoke model family, setup packet path, preflight reporting, runbook, NorthStar smoke setup plan, and contract coverage.
- **TD04252026 Maintenance Evidence**: Added the recurring maintenance report for the TD04252026 cycle with passing gate audit, docs hygiene, and canonical pytest results.

### Changed
- **Provider Attempt Truthfulness**: Tightened Terraform runtime-smoke failure summarization so Bedrock and DynamoDB failures preserve the preceding S3/Bedrock attempt sequence instead of under-reporting prior provider interactions.
- **Extension Control-Plane Test Authority**: Updated extension import-guard tests to use a real control-plane workload record and aligned the private manifest import-owner governance test with the existing extension support module.
- **Challenge Corpus Adapter Naming**: Renamed the fake attack-corpus adapter surface to the challenge-corpus adapter path and log vocabulary.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- No immediate action required. Palmyra X5 remains part of the same explicit AWS live-smoke opt-in path as the existing Terraform reviewer Bedrock smoke models.

## [0.4.49] - 2026-04-24 - "The NorthStar Smoke And Capability Trust Cut"

### Added
- **NorthStar Disposable AWS Smoke Setup**: Added the no-spend packet generator, fixture generation and validation, explicit live AWS setup/cleanup runners, credential scanning, operator runbook, and regression coverage for the disposable NorthStar S3/DynamoDB smoke path.
- **Trust Kernel Conformance Pack**: Added the finite trust-kernel model, portable conformance-pack spec and guide, proof runner, schema surfaces, and archived trust-kernel conformance closeout packet.
- **Jon IAM Migration Helper**: Added the AWS CLI-only PowerShell migration helper for moving Orket/NorthStar IAM permissions into the `OrketNorthstarWork` customer-managed policy, with backup, dry-run, quota, and same-user safety guards.

### Changed
- **Extension Capability Authority**: Expanded extension capability authorization, workload provenance, memory namespace isolation, controller observability, and control-plane projection surfaces with aligned specs, schema updates, audit generation, and runtime tests.
- **Terraform Live Smoke Truthfulness**: Tightened live setup preflight, provider-backed runtime smoke, publication gate, and NorthStar handoff behavior so setup evidence, live runtime blockers, cleanup state, and public-admission posture remain distinct.
- **Roadmap And Authority Posture**: Added the active NorthStar AWS smoke setup lane, archived completed trust-kernel conformance work, and aligned roadmap/current-authority/docs index references.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- For NorthStar live smoke, use the generated setup packet and explicit live AWS setup/cleanup flags; live runtime evidence remains blocked when Bedrock quota reports `ThrottlingException`.
- For Jon IAM cleanup, run the delete/detach phase from a separate administrator principal if the active caller is the target IAM user with no group authority.

## [0.4.48] - 2026-04-20 - "The Governed Packet And Terraform Pause Cut"

### Added
- **Governed Change Packet Authority Set**: Added the durable governed change packet specs, trusted-kernel model/verifier surfaces, operator guide, proof scripts, adversarial benchmark runner, archive closeout packet, and regression coverage for the repo-change packet path.
- **NorthStar Second-Family Lane**: Added the active-then-paused NorthStar second governed change packet family requirements and implementation-plan docs for evaluating `trusted_terraform_plan_decision_v1` as a possible second externally admitted packet family.

### Changed
- **Terraform Provider-Backed Gate Truthfulness**: Expanded the Terraform live setup and preflight support surfaces, widened truthful Bedrock summary model handling for the no-spend/live-preflight path, aligned trusted Terraform scope/trust docs and proof-foundation coverage, and kept public admission fail-closed when provider-backed evidence is still environment-blocked.
- **Roadmap And Lane Posture**: Activated the NorthStar second-family lane, ran its admission proof envelope, then paused the lane truthfully after the publication-readiness and publication-gate sequence remained blocked on missing required non-secret live inputs.
- **Authority And Staging Sync**: Synchronized current-authority metadata, docs index/roadmap references, staged benchmark catalog/readme surfaces, and recurring maintenance evidence so the committed repo reflects the current governed-packet and Terraform gate posture.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use `docs/guides/GOVERNED_REPO_CHANGE_PACKET_GUIDE.md` for the governed repo-change packet evaluator path.
- For any future Terraform public-admission reopen, provide `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI`, `ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID`, and `AWS_REGION` or `AWS_DEFAULT_REGION`, then rerun the full Workstream 2 proof envelope before proposing a trust-boundary update.

## [0.4.47] - 2026-04-19 - "The Governed Proof Terraform Gate Cut"

### Added
- **Governed-Proof Live Lane**: Added the active governed-proof implementation lane under `docs/projects/governed-proof/` together with its mechanism target map, scope candidate matrix, and scope admission/catalog drafting surfaces.
- **Trusted Terraform Compare Scope**: Added the durable `trusted_terraform_plan_decision_v1` spec, evaluator guide, contract deltas, workflow scripts, verifier/offline-claim support, shared scope-family helpers, and governed-proof regression coverage for the first externally useful non-fixture scope.
- **Terraform Provider-Backed Proof Operator Surfaces**: Added the no-spend live setup packet generator, no-spend live setup preflight, provider-backed runtime smoke wrapper, publication-readiness gate, and one-shot publication-gate sequence for the Terraform governed-proof path.

### Changed
- **Trusted-Run Authority Posture**: Expanded the admitted internal compare-scope authority to carry `trusted_terraform_plan_decision_v1`, aligned `CURRENT_AUTHORITY.md`, roadmap/docs index references, and updated trust/publication wording to keep Terraform public admission blocked until provider-backed evidence succeeds.
- **Proof Foundation And Offline Claim Wiring**: Added the canonical proof-foundation verifier path, carried the six fixed Workstream 1 targets into durable outputs, and made admitted witness/offline-verifier surfaces derive `side_effect_free_verification` from proof evidence rather than from an asserted constant.
- **Terraform Publication Gate Truthfulness**: Kept the fast-fail publication-gate path blocked by default when live AWS inputs are absent while preserving the blocked readiness result in the aggregate gate output.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- No immediate action required. Use `python scripts/proof/prepare_trusted_terraform_live_setup_packet.py`, then `python scripts/proof/check_trusted_terraform_live_setup_preflight.py`, then the Terraform publication gate only after real AWS-backed inputs are available.

## [0.4.46] - 2026-04-18 - "The Proof Witness Archive Cut"

### Added
- **Proof Witness Authority Set**: Added the durable trusted-run witness, invariant, control-plane substrate, offline verifier, first useful workflow slice, and trust-reason/publication-boundary specs together with their contract deltas, proof guide, proof scripts, and regression coverage.
- **Proof Archive Packet**: Added the archived `Proof` closeout records for the trusted-run witness, control-plane witness substrate, mathematical foundation, offline verifier, first useful workflow slice, trust-reason adoption lane, and the archived Proof packet ancestor.

### Changed
- **Proof Roadmap And Authority Posture**: Completed the full Proof packet, cleared `Priority Now`, archived the former future Proof packet under `docs/projects/archive/Proof/`, and aligned roadmap, docs index, README, and current-authority references to the bounded shipped proof surfaces.
- **Bounded Public Trust Wording**: Added the proof-backed `trusted_repo_config_change_v1` evaluator path and publication boundary, keeping public trust claims capped at `verdict_deterministic` and explicitly excluding replay and text determinism.
- **API Entrypoint Environment Bootstrap**: Made `python server.py` bootstrap the repo-root `.env` and construct the API app with the resolved project root so host-backed OrketUI calls use the expected local credentials and runtime context.
- **OrketUI Authored Card Evidence**: Preserved the additional authored-card records created during local OrketUI host-authoring verification.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- No immediate action required. Use the new proof guide and bounded trust contract when referring to the shipped `trusted_repo_config_change_v1` trust slice.

## [0.4.45] - 2026-04-10 - "The OrketUI Authoring Surface Cut"

### Added
- **Card Authoring Surface**: Added the governed host card create, save, and validate API slice with canonical revision ids, stale-save conflict handling, authored-card runtime projection, matching contract docs, and API regression coverage.
- **Flow Authoring Surface**: Added the persisted flow list, detail, create, save, validate, and bounded single-card run initiation API slice with durable SQLite storage, canonical runtime-target preflight, matching contract docs, and API regression coverage.

### Changed
- **OrketUI Authority Posture**: Moved the Orket-side OrketUI authority packet into a shipped reference project, archived the completed lane closeout, extracted write-surface specs, and aligned roadmap, docs index, API contract, current authority, and contract delta references.
- **Flow Persistence Truthfulness**: Kept corrupted persisted flow payloads fail-closed instead of silently substituting an empty payload during flow repository deserialization.
- **ControlPlane Governance Gate**: Retargeted the workload-authority matrix test to the durable governed start-path spec after the ControlPlane active-project folder was archived.
- **Local Temp Hygiene**: Ignored the documented `sandbox_temp_codex/` local temp root so repository-wide staging no longer tries to traverse an unreadable sandbox artifact.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- No immediate action required. OrketUI and host-agnostic authoring clients should use the new governed host card and flow authoring surfaces instead of minting host ids, revision ids, or run acceptance outside Orket.

## [0.4.44] - 2026-04-09 - "The ControlPlane Spec Extraction And OrketUI Staging Cut"

### Added
- **Durable ControlPlane Spec Set**: Added the durable ControlPlane packet spec files under `docs/specs/`, the governed workload start-path matrix, and the archived `CP04092026` ControlPlane closeout records so post-closeout authority no longer depends on an active project folder.
- **OrketUI Future-Lane Packet**: Added the staged OrketUI future-lane authority packet consisting of the product-definition requirements doc, host seam map, and extension object model with explicit split-repo and non-authoritative BFF posture.

### Changed
- **ControlPlane Authority Posture**: Retired the non-archive `docs/projects/ControlPlane/` packet folder, moved active ControlPlane authority references onto `docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md` plus `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`, and updated roadmap, current-authority, archive, and product-plan references to match the project closeout.
- **OrketUI Execution Gating**: Clarified that OrketUI remains staged only, that the separate extension repo must carry the selected mockups plus a source-of-truth note and initial shell/BFF scaffold before the lane is execution-ready, and that write-like UI actions remain blocked until they map to admitted host seams or new core specs are extracted first.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- No immediate action required. Future ControlPlane implementation must reopen through `docs/ROADMAP.md`, and OrketUI remains staged future-lane authority only until the separate extension repo and any missing write-seam specs exist.

## [0.4.43] - 2026-04-09 - "The ControlPlane Archive And Capability Gate Cut"

### Added
- **Capability Gate Authorities**: Added the archived Extension Capability Authorization closeout packet, the durable `EXTENSION_CAPABILITY_AUTHORIZATION_V1`, `TOOL_EXECUTION_GATE_V1`, and `CARD_VIEWER_RUNNER_SURFACE_V1` specs, matching contract deltas, operator view models and router surfaces, and audit builders for extension capability and tool-gate evidence.
- **Regression Coverage**: Added targeted regression coverage for operator views, capability authorization, tool-gate closure, local provider context reset, runtime artifact projection, and the new cards/operator runner surfaces.

### Changed
- **ControlPlane Roadmap Truth**: Archived the completed ControlPlane convergence lane under `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/`, removed it from `Priority Now`, and kept the accepted control-plane packet as reference-only active authority that now requires an explicit roadmap reopen for any future implementation work.
- **Governed Workload And Operator Surfaces**: Hardened workload execution and artifact provenance flow across cards ODR staging, workload executor/subprocess handling, run-start identity projection, run-summary/runtime-artifact generation, and operator-visible API surfaces so capability and projection authority stay explicit on the touched paths.
- **Runtime And Interface Alignment**: Updated API/frontend contracts, event taxonomy, supervisor runtime validation references, local provider behavior, logging, and extension/runtime support paths so the code, tests, and active authority docs stay synchronized after the capability-gate and runner-surface changes.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- No immediate action required. The touched capability-gate and operator-view surfaces are internal/runtime-governed updates and future ControlPlane implementation work now requires an explicit roadmap reopen.

## [0.4.42] - 2026-04-08 - "The BR04082026 Truthful Closeout Cut"

### Added
- **Techdebt Lane Archive**: Added the archived `BR04082026` closeout packet, archived requirements and implementation authorities, and the runtime-verification support-artifact contract delta for the completed seven-packet lane.
- **Live Script Regression Coverage**: Added targeted coverage for live-acceptance wrapper drift, probe runtime-settings bootstrap, replay-turn event-loop bootstrap, and compare normalization of fresh control-plane identity fields.

### Changed
- **Runtime Authority And Orchestrator Boundaries**: Completed the `BR04082026` authority-hardening lane across decision-node authority removal on touched live paths, app-scoped API runtime ownership, engine/orchestrator service extraction, and runtime registry ownership realignment.
- **Verifier And Audit Truthfulness**: Reclassified runtime verification as support-only evidence with preserved history, stopped implicit promotion of verifier artifacts to primary authored output, tightened MAR/audit validation, and made the live acceptance and audit operators behave truthfully on success, failure, divergence, and fresh-run identity noise.
- **Live Operator Reliability**: Repaired the live acceptance loop default target, probe script runtime-settings bootstrap, replay-turn bootstrap, and live compare normalization so the maintained script surfaces execute successfully against the current runtime architecture.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- No action required. Live proof was exercised against a local Ollama model and local API/webhook transport only.

## [0.4.41] - 2026-04-07 - "The Remediation Completion Closeout Cut"

### Added
- **Techdebt Closeout Archive**: Added the archived `TD04072026C` closeout packet and preserved the completed remediation plan plus review inputs outside the active maintenance lane.
- **Remediation Regression Coverage**: Added coverage for session repository initialization, review-run IDs, exception hierarchy, model-assisted provider errors, review git failures, local provider timeout validation, control-plane checkpoint persistence, and dual-write/protocol ledger idempotency.

### Changed
- **Runtime And Storage Hardening**: Completed the active remediation plan across SQLite WAL initialization, migration idempotency, structured review git failures, monotonic review run IDs, checkpoint persistence, Gitea webhook security/dedupe/persistent state, lease input validation, and secret-token masking.
- **Agent, Review, ODR, And Streaming Safety**: Tightened explicit agent config roots, fail-closed empty tool scopes, direct and dispatcher tool-gate proof, deterministic review severity defaults, malformed/unknown review policy warnings, ODR max-round acceptance/skip semantics, streaming truncation advisory events, and bounded/purged stream state.
- **Roadmap And Authority Alignment**: Cleared `Priority Now`, archived the completed finite techdebt lane, updated related authority/spec docs, and kept active techdebt scope limited to standing maintenance docs.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- No action required. No live external provider, intentional sandbox acceptance flow, or live Gitea webhook delivery was exercised.

## [0.4.40] - 2026-04-07 - "The Priority Now Techdebt Completion Cut"

### Added
- **CI Helper Script Gates**: Added named memory fixture, migration smoke validator, and sandbox leak gate scripts with regression coverage, replacing inline workflow heredoc blocks.
- **Runtime Truth Regression Coverage**: Added coverage for protocol receipt schema version defaults, turn tool run id structure, protocol ledger duplicate sequence rejection, raw-JSON acceptance, benchmark determinism validity, and cutover self-attestation reporting.
- **Techdebt Closeout Archive**: Added the archived `TD04072026B` techdebt closeout packet and moved the completed action plan and review inputs out of the active maintenance lane.

### Changed
- **Benchmark And Workflow Validity**: Raised benchmark determinism runs to two by default, recorded determinism validity warnings, separated stderr from determinism hashes, added scheduled baseline pruning, and wired the ODR determinism subset into PR workflow checks.
- **Runtime And Parser Safety**: Hardened runtime verifier cwd containment, timeout return-code handling, OOM classification, JSON assertion failures, guard evidence truncation metadata, legacy DSL parsing, and oversized `JSON.stringify` normalization.
- **API And Artifact Observability**: Made insecure no-API-key startup mode loud and non-production-only, recorded tool extraction strategy in turn artifacts and completion logs, and normalized protocol receipt schema version handling.
- **Roadmap And Authority Alignment**: Cleared `Priority Now`, archived the completed finite techdebt packet, and kept the active techdebt folder limited to standing maintenance authority.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- None.

## [0.4.39] - 2026-04-07 - "The Runtime Subpackage Techdebt Closeout Cut"

### Added
- **Runtime Subpackage Authority**: Added bounded `orket.runtime` implementation subpackages for config, evidence, execution, policy, registry, and summary behavior while keeping flat runtime modules as one-release compatibility aliases.
- **Extension Sandbox Enforcement**: Added subprocess SDK workload execution with declared-stdlib static checks, runtime import guards, manifest/template updates, and regression coverage for blocked undeclared imports.
- **Techdebt Closeout Archive**: Added the archived `TD04072026` techdebt closeout packet and preserved future adapter target notes as non-active backlog context.

### Changed
- **Priority Now Techdebt Completion**: Completed the active remediation plan through the remaining P0, P1, and P2 items, including fail-hard middleware behavior, typed tool-call failures, fail-closed partial parsing, effect journaling, strict agent configuration, settings locking, typed transcripts, OpenClaw partial results, SDK defaults, and controller invariant checks.
- **Roadmap And Authority Alignment**: Cleared `Priority Now`, archived completed techdebt authority, updated contributor/current-authority references for runtime subpackages and SDK sandbox behavior, and kept active techdebt scope limited to standing maintenance docs.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Extension authors should declare required stdlib imports through the manifest allowlist when opting into strict SDK workload sandboxing. Flat `orket.runtime.<module>` imports remain temporarily available through one-release compatibility aliases.

## [0.4.38] - 2026-04-07 - "The Governed Execution Maintenance Cut"

### Added
- **Techdebt Closeout Archive**: Added the archived `TD04062026D` remediation closeout packet and preserved the current code and behavioral review inputs as durable history outside the active maintenance lane.
- **Lifecycle And CI Regression Coverage**: Added sandbox lifecycle spool replay/dead-letter coverage, governed approval resource-reference coverage, OpenClaw torture approval coverage, quant sweep workflow smoke coverage, and changed-package detector regression coverage.

### Changed
- **Sandbox Lifecycle Truth Hardening**: Hardened event spool replay with structured replay results, retry accounting, dead-letter output, atomic spool rewrite, replay locking, and single-read mutation-result handling for lifecycle transitions.
- **Kernel Canonicalization Consolidation**: Retired the legacy ODR `canon.py` module, moved domain-specific ODR canonicalization behind the RFC 8785 canonical backend with explicit policy preprocessing, admitted finite floats only for that domain surface, and re-pinned determinism gate hashes.
- **Workflow And Script Reliability**: Added quant sweep matrix execution smoke coverage, made changed-package detection fail open to the package matrix when the configured base ref is unavailable, tightened TextMystery bridge execution path handling, and removed local path drift from Gitea backup/probe script paths.
- **Roadmap And Authority Alignment**: Cleared active non-recurring maintenance posture, advanced the authority snapshot date, and preserved future-lane idea review notes without reopening a roadmap lane.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- No action required. The closeout proof is structural/contract/integration plus local workflow smoke; ShellCheck was not available and no live sandbox resource path was intentionally executed.

## [0.4.37] - 2026-04-06 - "The Priority Techdebt Remediation Cut"

### Added
- **Remediation Closeout Archive**: Added the archived `TD04062026C` techdebt closeout packet and preserved the completed review/remediation source docs as durable history outside active techdebt scope.
- **Tool, Webhook, Model, And Reconciliation Registries**: Added the tool recovery registry, Gitea webhook payload boundary models, model-family registry, and SQLite/Gitea state reconciliation service plus on-demand script coverage.

### Changed
- **Priority Now Techdebt Completion**: Completed the active remediation plan through W1-W3, including fail-closed partial tool recovery, per-tool timeouts, typed lease and settings failures, turn retry backoff, middleware isolation, async AST validation, role-scoped tool gating, utility/app transitions, async repository locking cleanup, configurable iDesign categories, and deprecated `orket.orket` roadmap tracking.
- **Execution Pipeline And Runtime Hardening**: Split `ExecutionPipeline` into bounded coordinator/mixin files, kept public compatibility wrappers routed through `run_card`, added repository-backed Gitea state loop authority, and tightened type-only split contracts to avoid new static-analysis drift.
- **Observability And Protocol Maintenance**: Added bounded log-queue backpressure, call-time log-level resolution, payload schema failure events, float-only card priority authority with legacy migration, and maintained LPJ-C32 Castagnoli CRC-32C via the declared `google-crc32c` dependency instead of a hand-rolled table.
- **Roadmap And Authority Alignment**: Cleared the active `Priority Now` lane, updated authority/event taxonomy notes, and kept the active techdebt folder limited to standing maintenance authority plus the live-runtime recovery plan.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- No action required. The closeout proof is structural/contract/integration; live Gitea, live model-provider retry, and live sandbox paths were not rerun in this release.

## [0.4.36] - 2026-04-06 - "The Strict-Typing Techdebt Completion Cut"

### Added
- **Epic Run And Contract Typing Surfaces**: Added the extracted epic-run orchestration support, contract-schema scaffolding, local third-party stubs, and integration/policy coverage needed to make the strict type gate runnable as a repo-level authority check.
- **Techdebt Closeout Archive**: Added the archived `TD04062026B` closeout packet so the completed Priority Now remediation lane has durable history while the active techdebt folder returns to standing maintenance only.

### Changed
- **Repo-Wide Strict Typing Completion**: Hardened runtime, API, orchestration, adapter, storage, kernel, CLI, extension, streaming, and script-test typing surfaces so `python -m mypy --strict orket` exits with zero issues.
- **Runtime And API Regression Fixes**: Tightened execution-pipeline payload narrowing, orchestration helper signatures, turn-executor type aliases, and API cards-router runtime-node lookup so import/reload isolation and archive policy seams preserve truthful behavior.
- **Roadmap And Script Lifecycle Hygiene**: Cleared the active Priority Now techdebt lane, archived completed remediation authority, and marked script-test lifecycle state so standing maintenance remains explicit without stale active lane drift.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use `python -m mypy --strict orket` as the canonical strict typing gate for the closed remediation lane; future techdebt work should enter through the standing maintenance authorities unless a new roadmap lane is explicitly opened.

## [0.4.35] - 2026-04-06 - "The Truth-Hardening Techdebt Closeout Cut"

### Added
- **Runtime Context And Archive Closeouts**: Added the extracted runtime-context support, the archived `TD04062026` techdebt closeout packet, and the archived ProductFlow closeout materials so the completed remediation cycle and roadmap closeouts have one durable authority surface.

### Changed
- **Runtime And Domain Truth Hardening**: Consolidated legacy domain imports onto `orket.core.domain`, finished the active fix-plan and behavioral-remediation code path, expanded lint and coverage policy surfaces, and hardened runtime, orchestration, kernel, storage, and review flows so the repo closes the current truth-hardening cycle with tighter single-source authority and fewer async or delegation traps.
- **API Composition And Interaction Streaming**: Hardened API composition isolation, lazy engine access, task tracking, approvals surfaces, and interaction-session commit delivery so websocket and `TestClient` flows now preserve truthful `commit_final` behavior without import-time mutable-runtime drift.
- **Roadmap And Maintenance Posture**: Updated roadmap and project docs back to maintenance-only posture after completing the active non-recurring techdebt lanes, while preserving the standing live-maintenance runbook and recurring checklist as the remaining active `techdebt` authority.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use the standing maintenance authorities in `docs/projects/techdebt/` for future recurring work; the completed fix-plan and behavioral-remediation cycle now lives under `docs/projects/archive/techdebt/TD04062026/`.

## [0.4.34] - 2026-04-05 - "The Prompt Reforger Tool-Use Truth Cut"

### Added
- **Prompt Reforger Generic Service Authority**: Added the Prompt Reforger generic service contract, service/result scaffolding, proof-slice support, and the bounded structural Phase 0 staging artifacts so the service now has one explicit authority surface instead of prompt-lab-only drift.
- **Prompt Reforger Gemma Tool-Use Harness**: Added the Prompt Reforger Gemma tool-use implementation lane, frozen challenge corpus, FunctionGemma judge protocol, prompt-lab runners, score/judge/cycle test coverage, and the local-model coding challenge harness so the admitted portability evaluation path is repo-owned and rerunnable.

### Changed
- **Governed Local Prompting And Native Tool Turns**: Hardened local-model provider telemetry, prompt-compilation policy, compact turn-packet construction, response parsing, and orchestrator/runtime wiring so OpenAI-compatible Gemma tool turns use one compact model-facing packet, preserve truthful native-tool allowlists, and fail closed on undeclared or duplicate call shapes.
- **Authority And Staging Surface Alignment**: Updated `CURRENT_AUTHORITY.md`, roadmap/docs indexes, Prompt Reforger contracts, local prompt profiles, challenge assets, and staging benchmark catalog metadata so the paused Gemma portability checkpoint, new guide-model comparison surface, and structural-versus-live proof status all match the shipped runtime truth.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use the Prompt Reforger staging runners and the compact Gemma/OpenAI-compatible tool-turn path as the canonical authority for this lane; the Prompt Reforger Gemma portability lane remains paused until the frozen corpus is cleared truthfully.

## [0.4.33] - 2026-04-03 - "The Challenge Workflow Runtime Truth Hardening Cut"

### Added
- **Challenge Workflow Runtime Closeout Archive**: Added the archived `TD04032026` techdebt closeout packet under `docs/projects/archive/techdebt/TD04032026/` so the accepted hardening scope, rerun evidence, and residual-risk framing are preserved as durable history instead of active lane drift.

### Changed
- **Challenge Epic Contract Hardening**: Hardened `challenge_workflow_runtime` issue notes, semantic checks, runtime-verifier commands, local prompt profile expectations, and the `qwen` dialect guidance so generated artifacts must match the admitted workflow vocabulary, planner/validator/simulator behavior, checkpoint/resume semantics, and reporting proof surface rather than passing on compile-only or semantically false-green output.
- **Runtime Verifier And Turn Semantics**: Expanded runtime-verifier parsing, turn-contract validation, turn message/response handling, artifact semantic rules, orchestrator plumbing, and cards-runtime contracts so nested JSON assertions and issue-scoped behavioral proof commands are first-class runtime truth instead of ad hoc post-processing.
- **Regression Proof Coverage**: Extended the repo-backed application/core/platform test matrix around the hardened challenge asset contracts, verifier behavior, planner/orchestrator flows, and local prompting policy so the accepted challenge-runtime proof path is mechanically defended.
- **Roadmap Posture**: Updated `docs/ROADMAP.md` back to standing maintenance only after the finite `TD04032026` lane was archived.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Treat `runtime_verification.json` behavioral command execution as the canonical proof surface for `challenge_workflow_runtime`; compile-only verifier output is no longer sufficient evidence of success.

## [0.4.32] - 2026-04-02 - "The Runtime Challenge And Authority Rebase Cut"

### Added
- **Future Enhancement Packet Rebase**: Added the staged `docs/projects/future/EnhancementPackage/` packet as explicit future-delta material rather than live authority, keeping the packet under the future tree with baseline/delta/non-reopen framing.
- **Long-Run Runtime Challenge Assets**: Added the `challenge_workflow_runtime` epic and `challenge_coder_guard_team` so Orket has a coder-plus-guard programming challenge that should drive at least 24 happy-path turns across a deterministic workflow-runtime implementation.
- **Role Matrix Soak Asset Authority**: Added the repo-hosted role-matrix soak team/epic assets and the matching platform asset-load proof so long-run role-matrix scenarios are first-class repo config, not ad hoc workspace-only inputs.

### Changed
- **ControlPlane And Runbook Authority Cleanup**: Rebased the roadmap, runbook, ControlPlane hardening requirements, and the brainstorm authority wording so paused/staged posture and operator/runtime authority no longer imply an open active lane where one is not admitted.
- **Runtime Verifier And Cards Runtime Contracts**: Hardened runtime verification and cards-runtime contract handling so real entrypoints run under verification, control-plane closeout truth is published, comment/blocker seats stop inheriting synthetic app contracts, and role-matrix scenarios can carry one canonical scenario-truth object into prompts and run summaries.
- **Turn Contract And Graph Proof Surfaces**: Tightened turn prompt building, comment-contract enforcement, run-summary scenario projection, and evidence-graph emission coverage so the long-run soak surfaces fail closed more truthfully and expose clearer scenario-state drift.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use `python main.py --epic challenge_workflow_runtime` for the new hard coder challenge, and treat the future EnhancementPackage packet as staged planning input only rather than active roadmap authority.

## [0.4.31] - 2026-04-01 - "The Extension Publish Surface And Generic Runtime Cut"

### Added
- **Extension Publish Surface Packet 1**: Added the active Extensions publish-surface lane, the durable package/publish contract pair, contract deltas, template release scripts/workflows, and publish-surface proof coverage that standardize one tagged source-distribution release story for external extensions.
- **Generic Extension Runtime Surface**: Added `ExtensionRuntimeService` plus the `/v1/extensions/{extension_id}/runtime/*` API/router/test surface so generic extensions now have one host-owned runtime status, model, LLM, memory, voice, and TTS integration path.
- **Bounded `write_file` Approval Continuation**: Added the runtime-owned `write_file` approval continuation service and matching approval / turn-executor proof so the admitted same-governed-run continue-or-stop slice is explicit and fail-closed.

### Changed
- **Companion Runtime Consolidation**: Removed the companion-only runtime service and router aliases, routed the shipped runtime story through the generic extension-runtime surface, and aligned orchestration, approvals, scripts, and live/runtime tests with that authority.
- **Extension Publish And Operator Authority**: Updated `CURRENT_AUTHORITY.md`, `docs/RUNBOOK.md`, `docs/ROADMAP.md`, the extension authoring guide, and the external-extension template so source version, manifest version, release tag, maintainer publish steps, and operator intake back to `orket ext validate <extension_root> --strict --json` now tell one story.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use the external-extension template release scripts or tagged release workflow to publish the authoritative source distribution, then extract that artifact and run `orket ext validate <extension_root> --strict --json` before runtime use. Treat `/v1/extensions/{extension_id}/runtime/*` as the canonical API runtime surface; the old companion-only aliases are no longer canonical.

## [0.4.30] - 2026-03-31 - "The Supervisor Runtime Foundations Requirements Cut"

### Added
- **SupervisorRuntime Requirements Lane**: Added the active SupervisorRuntime project with a requirements companion and an implementation-plan authority that keeps Packet 1 intentionally cold around approval-checkpoint runtime behavior, session/context-provider boundaries, operator projections, and one host-owned extension install/validation surface.
- **Future Brainstorm Inventory Pack**: Added the March 31 brainstorm inventory sequence under `docs/projects/future/brainstorm/` as planning input only, covering repo-truth boundaries, anti-patterns, future-lane candidates, and a narrowed conditional Graphs reopen posture.
- **Graphs Checkpoint Closeout Packet**: Added the archived Graphs checkpoint-closeout packet under `docs/projects/archive/Graphs/GF03312026-CHECKPOINT-CLOSEOUT/`.

### Changed
- **Roadmap And Active Project Index**: Replaced the maintenance-only posture with the active SupervisorRuntime requirements lane in `docs/ROADMAP.md` and removed the non-archive Graphs checkpoint project from the live roadmap/project index.
- **Graphs Authority Story**: Retired the active `docs/projects/Graphs/` checkpoint files in favor of the archived closeout packet, keeping the active docs tree free of completed Graphs checkpoint authority.
- **Changelog Authority Wording**: Narrowed the prior `0.4.29` Graphs note so it no longer implies a still-active Graphs checkpoint under `docs/projects/Graphs/`.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use `docs/ROADMAP.md` and the SupervisorRuntime lane docs as the current planning authority for this work; no runtime migration step is required.

## [0.4.29] - 2026-03-31 - "The Run Evidence Graph And Maintenance Truth Cut"

### Added
- **Run Evidence Graph V1 Surface**: Added the run-evidence graph runtime, projection, rendering, operator CLI, schema registration, fixtures, and contract/runtime/script proof coverage for canonical `run_evidence_graph.json`, `.mmd`, and `.html` artifacts.
- **Graphs And Archive Authority Packets**: Added the Graphs checkpoint authority plus the matching archived Graph/Graphs/LocalPrompting closeout packets that preserve the March 30 graph-family and local-prompting maintenance decisions.

### Changed
- **Authority And Operator Docs**: Updated `CURRENT_AUTHORITY.md`, `docs/RUNBOOK.md`, `docs/README.md`, roadmap/checkpoint docs, and maintenance guidance so the active operator path, maintenance-only posture, paused checkpoints, and local-prompting promotion readiness command now match the shipped runtime and evidence roots.
- **Provider Runtime Target Truth**: Hardened local-model provider runtime-target detection so `httpx.MockTransport` clients only count as runtime-managed OpenAI-compatible targets when the provider actually owns that client instance.
- **Parallel Execution Test Stability**: Reworked the parallel orchestration throughput proof to compare parallel versus serial baselines under the same local conditions and labeled the affected tests as integration coverage instead of relying on a brittle fixed wall-clock threshold.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use `python scripts/observability/emit_run_evidence_graph.py --run-id <run_id>` as the canonical operator path for run-evidence graph emission; no other manual migration is required.

## [0.4.28] - 2026-03-29 - "The Manager-Owned Extension Eligibility Cut"

### Added
- **Focused ControlPlane Proof Slice**: Proved the extension-manager and controller-dispatch boundary with a focused governance/runtime test slice plus docs hygiene, covering the manager-owned SDK eligibility probe and the matching authority-doc sync.

### Changed
- **Extension Child Eligibility Boundary**: Added `ExtensionManager.uses_sdk_contract(...)` and moved controller child eligibility checks onto the manager-owned boolean probes `has_manifest_entry(...)` and `uses_sdk_contract(...)` instead of resolving private manifest-entry tuples directly inside controller dispatch.
- **Authority Story Alignment**: Updated `CURRENT_AUTHORITY.md` and the active ControlPlane implementation plan, closeout, and crosswalk so they now record the same narrower truth: controller dispatch no longer reaches into private extension manifest metadata.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

## [0.4.27] - 2026-03-29 - "The Canonical Card Dispatcher And Full Proof Cut"

### Added
- **Full Local Proof Sweep**: Executed the full local pytest surface, the live Docker sandbox acceptance bucket, and the provider-backed live acceptance plus live role buckets together on one machine, then re-ran the entire gated suite in one pass with those gates enabled for a final `3614 passed, 2 warnings` release proof snapshot and no remaining skipped tests.

### Changed
- **Canonical Runtime Entry Truth**: Re-established `run_card(...)` as the truthful public runtime and engine dispatcher, kept `run_issue(...)`, `run_epic(...)`, and `run_rock(...)` as thin convenience wrappers only, and routed CLI `--epic` plus legacy `--rock` through those wrappers without changing the control-plane workload authority seam.
- **Governance And Authority Alignment**: Narrowed the workload-authority governance rule so only the CLI ergonomic owner may call runtime wrapper verbs, kept `resolve_control_plane_workload(...)` as the sole workload-authority seam, and updated `CURRENT_AUTHORITY.md` plus the active ControlPlane implementation plan, closeout, and crosswalk so the docs match the shipped runtime truth.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use `python main.py --card <card_id>` as the canonical runtime entrypoint. `--epic` and legacy `--rock` remain available as thin ergonomic wrappers, and no manual migration step is required.

## [0.4.26] - 2026-03-29 - "The ControlPlane Review Truth And Live Proof Cut"

### Added
- **ControlPlane Contract Delta Pack**: Added contract-delta records for review-run control-plane identity, review-bundle identity, cards run-summary attempt identity, retry-policy report snapshot validation, answer-key score-report provenance and aggregate coherence, and review consistency-report validation.
- **Review Truth Regression Expansion**: Added deeper contract and integration coverage for review bundle validation, answer-key scoring, consistency reporting, code-review probe consumers, retry-policy acceptance gates, cards run-summary projection validation, and the previously gated live/sandbox proof buckets now exercised together in one full local pass.

### Changed
- **ReviewRun Authority Surfaces**: Hardened review manifests, deterministic/model-assisted lane artifacts, result and CLI control-plane projections, replay/scoring/consistency consumers, and workload-side probe emitters so run identity, control-plane lineage, lifecycle metadata, and score-report provenance now fail closed before serialization or trust.
- **Runtime Projection And Retry Truth**: Tightened cards `run_summary.json` projection validation, run-start retry-classification projection framing, retry-policy report normalization and acceptance-gate validation, and persisted review consistency/score report validation so malformed or contradictory projection data no longer reads as authoritative evidence.
- **Authority Docs And Closeouts**: Updated `CURRENT_AUTHORITY.md`, the active ControlPlane convergence plan/closeout/crosswalk docs, and the review-run spec/CLI guides so documented authority matches the shipped fail-closed runtime and report behavior.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use the updated ControlPlane and review-run authority docs as the source of truth for replay, scoring, consistency, and runtime-truth validation behavior; no manual migration step is required.

## [0.4.25] - 2026-03-28 - "The Run Projection And Test Truth Cut"

### Added
- **Validated Review And Run Projection Seams**: Added shared review-bundle validation, control-plane projection, run-ledger summary projection, and microservices acceptance report helpers plus new contract coverage around those normalized truth surfaces.
- **Protocol And Rollout Proof Coverage**: Added deeper protocol parity, capture, signoff, cutover-readiness, runtime-summary, and live-proof validation coverage for malformed or drifted projection payloads.

### Changed
- **Review Run And Operator Surfaces**: Hardened review-run models, CLI/API surfaces, runtime summaries, and training or audit helpers so control-plane execution authority, run-state projections, and packet-1 or packet-2 provenance now fail closed on malformed or contradictory persisted payloads instead of silently flattening them.
- **Acceptance And Runtime Policy Decisions**: Tightened monolith or microservices readiness, pilot stability, unlock, live acceptance, and dashboard/reporting logic so invalid payload signals propagate through gates and decision paths truthfully.
- **ControlPlane Authority Docs**: Updated `CURRENT_AUTHORITY.md`, the active ControlPlane convergence plan and closeouts, and the packet or runtime-truth specs so the documented authority matches the shipped projection and control-plane behavior.
- **Test And Proof Hygiene**: Removed a redundant benchmark wrapper test, replaced the nightly ODR skip wrapper with an env-driven scale path, eliminated the ODR scenario skip-at-runtime pattern, and rewrote stale live assertions to accept the truthful repaired-versus-fail-closed branches now produced by provider-backed runs.

### Removed
- **Redundant Benchmark Pytest Wrapper**: Removed `tests/live/test_benchmark_task_bank_live.py`, which only launched the standalone live benchmark job and added skip noise without distinct correctness coverage.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use the updated review-run, run-summary, acceptance, and ControlPlane authority docs as the current source of truth, and use `ODR_INCLUDE_SCALE=1` with the ODR role-matrix runner when you want the heavier scale checks that were previously hidden behind the nightly-only pytest wrapper.

## [0.4.24] - 2026-03-26 - "The Control Plane Archive And Runtime Guard Cut"

### Added
- **Kernel And Orchestrator Guard Surfaces**: Added dedicated kernel-action failure, outcome, and resource-lifecycle support seams plus deeper orchestrator, scheduler, session-status, and preflight guard coverage across the control-plane runtime.
- **ControlPlane Archive And Convergence Drafts**: Added the archived ControlPlane lane closeout packet under `docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/` and added staging-only convergence requirements and implementation-plan drafts with explicit activation gates, workstream bindings, and compatibility-exit tracking.

### Changed
- **Control-Plane Runtime Publication**: Expanded reservation, recovery, operator, checkpoint, target-ref, and final-truth publication/read-model behavior across kernel-action, coordinator, Gitea worker, orchestrator issue/scheduler, sandbox, and governed turn-tool paths.
- **Authority And Entry-Point Truth**: Updated `CURRENT_AUTHORITY.md`, roadmap and packet authority docs, `main.py`, `server.py`, `orket/webhook_server.py`, runtime settings, runbook guidance, and webhook setup docs so startup order, webhook requirements, and archived ControlPlane authority match current behavior.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use the archived ControlPlane lane closeout as the historical implementation authority, treat the new convergence docs as staging-only until roadmap activation, and configure required webhook environment variables before starting the webhook runtime; no code migration is otherwise required.

## [0.4.23] - 2026-03-24 - "The Same-Attempt Recovery And Issue Control Plane Cut"

### Added
- **Orchestrator Issue And Scheduler Control Plane**: Added first-class control-plane publication for default orchestrator issue dispatch, scheduler-owned issue mutations, and team-replan child issue creation, including namespace reservations, lease promotion, step/effect publication, and terminal closeout truth.
- **Governed Turn Replay Guards**: Added dedicated governed-turn replay and evidence helpers plus deeper integration coverage for immutable checkpoint snapshot alignment, missing snapshot artifacts, resumed-attempt dirty truth, and orphan operation evidence on resume.

### Changed
- **Governed Turn Resume Semantics**: New governed pre-effect checkpoints now publish `resume_same_attempt`, safe `resume_mode` continues on the current attempt before prompt/model work, existing older new-attempt checkpoint lineage remains consumable, and same-attempt or replacement-attempt resumes fail closed once durable step, effect, or orphan operation truth already exists.
- **Turn Tool Execution Closeout**: Governed turn closeout now releases execution reservation and lease authority on successful completion, terminal failure, and reconciliation-closed unsafe resume.
- **Authority Docs And README**: Updated `CURRENT_AUTHORITY.md`, `README.md`, and the active ControlPlane packet docs so current repo entrypoints and the live control-plane boundary match runtime behavior.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use the updated governed turn and orchestrator control-plane authority docs as the source of truth for same-attempt governed resume and default issue/scheduler publication; no manual migration is required.

## [0.4.22] - 2026-03-24 - "The Governed Turn Artifact Replay Cut"

### Added
- **Governed Turn Artifact Replay**: Added a completed-run control-plane replay helper that reconstructs successful governed turns from durable step and operation artifacts before prompt/model execution, plus deeper governed-turn integration proof for no-model and no-checkpoint-rewrite re-entry.

### Changed
- **Governed Turn Re-entry Semantics**: Successful governed re-entry now short-circuits before prompt/model work and before checkpoint snapshot rewrite instead of rerunning the model and only reusing finalized truth later.
- **Authority Docs**: Updated `CURRENT_AUTHORITY.md` and the active ControlPlane packet docs so the governed turn lane truthfully describes artifact-backed successful re-entry on the current architecture.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- No manual migration is required; use the existing governed turn observability and control-plane SQLite artifacts as the canonical replay source on successful re-entry.

## [0.4.21] - 2026-03-24 - "The Control Plane Vertical Closeout Cut"

### Added
- **Governed Turn Recovery Closeout**: Added governed turn reconciliation closeout services, fail-closed re-entry guards, and deeper integration proof for unsafe resume, terminal reconciliation closure, and early control-plane blocking on the non-Gitea governed turn lane.
- **Coordinator And Approval Reservation Authority**: Added durable coordinator claim reservation services, richer coordinator lease/control-plane response summaries, and operator-hold reservation publication for repo-backed approvals, guard-review pending gates, and governed kernel approval admission.
- **Non-Sandbox Runtime Authority Surfaces**: Added durable execution, lease, reservation, checkpoint, and failure-closeout services for the Gitea worker lane plus governed kernel and approval control-plane support modules and read models.

### Changed
- **ControlPlane Runtime Truth**: Expanded live or integration-backed publication across sandbox, governed kernel, governed turn-tool, coordinator, approval, and Gitea worker lanes for reservation, lease, checkpoint, recovery, reconciliation, operator action, and final-truth authority.
- **Governed Turn Resume Semantics**: Unsafe post-effect or observation-uncertain governed resumes now publish reconciliation evidence and close terminally instead of leaving the run stranded in a recovery intermediate state, while terminal or recovery-blocked governed runs now fail before model execution and checkpoint rewrite.
- **Authority Docs**: Updated `CURRENT_AUTHORITY.md` and the active ControlPlane packet docs so the described authority surfaces match the current durable runtime behavior.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use the current ControlPlane packet and `CURRENT_AUTHORITY.md` as the source of truth for the governed turn, approval, coordinator, sandbox, and Gitea control-plane seams; no manual migration step is required beyond consuming the updated durable records on the existing SQLite control-plane path.

## [0.4.20] - 2026-03-24 - "The Control Plane Lease Publication Cut"

### Added
- **Lease Publication Authority**: Added first-class lease publication helpers, append-only lease persistence, sandbox lease mapping services, and lease-focused contract/application coverage for the ControlPlane lane.
- **Lease Contract Delta Record**: Added `docs/architecture/CONTRACT_DELTA_CONTROL_PLANE_LEASE_PUBLICATION_2026-03-23.md` to record the authority change introducing runtime-published lease records.

### Changed
- **Sandbox Runtime Truth Surface**: Extended the default sandbox runtime to publish durable `LeaseRecord` snapshots across claim, activation, renewal, reacquire, reconciliation, expiry, lost-runtime uncertainty, and cleanup release paths.
- **ControlPlane Authority Docs**: Updated `CURRENT_AUTHORITY.md`, the ControlPlane packet, and event taxonomy docs so active authority matches the live lease-publication seam and durable control-plane SQLite storage path.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use the default sandbox orchestrator runtime path to populate `.orket/durable/db/control_plane_records.sqlite3` with lease, reconciliation, and final-truth records, and consult the updated ControlPlane packet for the current partial live authority boundary.

## [0.4.19] - 2026-03-22 - "The Terraform Reviewer Governed Lane Cut"

### Added
- **Terraform Plan Reviewer Runtime**: Added the governed Terraform plan reviewer application service, deterministic analysis, artifact emission, and advisory-only model summary handling under `orket/application/terraform_review/`.
- **Terraform Fixture And Proof Harness**: Added the locked Terraform fixture corpus, fake adapter support, targeted deterministic/service coverage, and the thin live AWS smoke runner with canonical output at `.orket/durable/observability/terraform_plan_review_live_smoke.json`.
- **Terraform Durable Contract And Archive**: Added the durable contract `docs/specs/TERRAFORM_PLAN_REVIEWER_V1.md`, the archived Terraform lane authority set under `docs/projects/archive/terraform-plan-review/TP03222026/`, and the matching contract delta record.

### Changed
- **Operator Guidance**: Updated `docs/RUNBOOK.md`, `docs/README.md`, and `CURRENT_AUTHORITY.md` so the Terraform reviewer operator path, durable contract, and smoke output location are discoverable from active repo authority docs.
- **Governed Outcome Semantics**: Preserved distinct artifact outcomes for policy-blocked execution, degraded publication, ordinary runtime failure, and environment blockers across the Terraform reviewer lane.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use the Terraform reviewer section in `docs/RUNBOOK.md` for the local governed proof command and `python scripts/reviewrun/run_terraform_plan_review_live_smoke.py` for the thin live AWS smoke path.

## [0.4.17] - 2026-03-22 - "The Bounded ODR Role-Fit Follow-Up Cut"

### Added
- **Archived ODR Lane Authority**: Added the archived ContextContinuity and ODRModelRoleFit closeout/authority sets under `docs/projects/archive/ContextContinuity/CC03212026/` and `docs/projects/archive/ODRModelRoleFit/MRF03212026/`.
- **ODR Role-Fit Follow-Up Lane**: Added a new active follow-up lane under `docs/projects/odr_role_fit_followup/` with a frozen reviewer-anchored plan, lane config, and narrowed architect matrix for `Command-R:35B`, `llama-3.3-70b-instruct`, and `mistralai/magistral-small-2509` against `gemma3:27b`.
- **ODR Script Coverage Expansion**: Added contract/integration coverage for continuity compare/verdict/live-metric surfaces, model-role-fit triple runtime normalization, and the reviewer-anchored follow-up lane config.

### Changed
- **ContextContinuity Completion And Archive**: Completed the bounded ContextContinuity lane through compare/verdict/live-proof surfaces, archived the active lane docs, and updated the runtime defaults/tests to point at the archived authority paths.
- **Model-Role Fit Harness Hardening**: Implemented the serial pair/triple role-fit harnesses, truthful execution-blocked reporting, resume-safe artifact handling, triple-config normalization for reused V1 state contracts, and narrower follow-up pair selection against the archived continuity substrate.
- **V1 Shared-State Quality**: Hardened compiled shared-state extraction so fenced `orket-constraints` blocks are parsed deterministically, explicit unresolved issue summaries are preserved, and invariant/rejected-path state no longer degrades into JSON-fragment identities.
- **Repo Hygiene**: Added top-level `pytest_tmp/` and `sandbox_pytest/` ignores so `git status` no longer emits permission warnings when unreadable temp subtrees are present.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use `python scripts/odr/prepare_odr_model_role_fit_live_proof.py --config docs/projects/odr_role_fit_followup/odr_role_fit_followup_lane_config.json` for the active reviewer-anchored architect bakeoff lane.

## [0.4.18] - 2026-03-22 - "The ODR Closeout And Hardening Cut"

### Added
- **Archived ODR Follow-On Lanes**: Added the archived authority and closeout sets for the round-cap probe, loop-shape hardening, and reviewer-anchored role-fit follow-up lanes under `docs/projects/archive/ODRRoundCapProbe/`, `docs/projects/archive/ODRLoopShapeHardening/`, and `docs/projects/archive/ODRRoleFitFollowup/`.
- **Round-Cap Probe Harness**: Added the bounded serial rerun harness and coverage for replaying prior `MAX_ROUNDS` cases at a higher cap while preserving lane-scoped config and verdict discipline.
- **Loop-Shape Contract Proof**: Added targeted prompt-contract and loop-shape lane coverage for injecting lane-scoped hardening rules into the live ODR path.

### Changed
- **ODR Roadmap Cleanup**: Closed the remaining active ODR lanes, removed them from `Priority Now`, and returned the roadmap to no active implementation lanes after bounded closeout.
- **Live ODR Truthfulness**: Fixed the model-role-fit live runner so loop-shape `protocol_hardening` is actually passed into per-scenario runtime config, preventing mislabeled hardened runs.
- **Archived Lane Path Repair**: Corrected archived ODR lane config references so archived loop-shape and role-fit authorities remain runnable after archive relocation.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use the archived ODR lane authorities under `docs/projects/archive/` for historical replay and closeout evidence; there are no active ODR implementation lanes on the roadmap after this cut.

## [0.4.16] - 2026-03-21 - "The Context Continuity Bootstrap Cut"

### Added
- **Context Continuity Lane Authority**: Added the new ContextContinuity lane requirements, implementation plan, pair pre-registration snapshot, machine-readable lane config, output schema, and a config-driven bootstrap harness for the active roadmap execution lane.
- **Continuity Bootstrap Coverage**: Added targeted unit, contract, and integration coverage for continuity pair-budget reducers, control-mode isolation, and config-driven bootstrap execution.

### Changed
- **Mixed-Provider ODR Benchmarking**: Hardened the local model provider, ODR runtime-control path, and ODR benchmark scripts for per-role provider selection, truthful mixed-provider residency handling, and more accurate baseline interpretation.
- **OpenAI-Compatible Reasoning Recovery**: Improved LM Studio/OpenAI-compatible response extraction and local prompting policy handling for reasoning-content-only responses and Qwen-family no-think prompt shaping, with expanded adapter test coverage.
- **Roadmap And Archive Hygiene**: Promoted the ContextContinuity implementation lane into `Priority Now`, updated the project index, and archived the previous future techdebt `game-plan.md` under `docs/projects/archive/techdebt/game-plan.md`.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use `python scripts/odr/prepare_odr_context_continuity_lane.py` to materialize the locked ContextContinuity bootstrap artifact before executing later continuity slices.

## [0.4.15] - 2026-03-19 - "The Governed Workload Proof Cut"

### Added
- **Phase 3 Standalone Workload Probes**: Added new bounded workload probes under `scripts/workloads/` for S-04 code review, S-05 generate-and-verify, and S-06 decompose-and-route, along with dedicated fixtures and targeted application coverage.
- **Determinism Gate Policy Authority**: Added `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md` as the canonical claim-tier and gate-policy document for determinism, replay, verdict stability, and publication wording.

### Changed
- **S-04 Review Probe Hardening**: Reworked the code-review probe around governed prompt/method profiles, a deterministic static-fingerprint lane, and truthful provider-usage accounting so must-catch coverage and stability can be evaluated independently from raw prose quality.
- **Structured Review Scoring**: Hardened `scripts/reviewrun/score_answer_key.py` to score structured review artifacts semantically instead of relying on brittle whole-blob matching, restoring reasoning and fix credit when the model review is materially correct.
- **Authority Indexing**: Updated `docs/README.md` and `CURRENT_AUTHORITY.md` so the new determinism policy is tracked as an active governance source.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md` when making determinism, replay, or verdict-stability claims for proof, release, and publication artifacts.

## [0.4.14] - 2026-03-17 - "The Behavioral Review Closure Cut"

### Added
- **Behavioral Review Archive Closeout**: Added the archived remediation closeout record under `docs/projects/archive/techdebt/BR03172026/Closeout.md` for the completed behavioral-review cycle.
- **Regression Coverage For Behavioral Review Findings**: Added targeted regression coverage for run-ledger naming/parity behavior, protocol timestamp/run reconstruction, process-rules object access, provider timeout/cancel handling, reprompt artifact overwrite, and the fake OpenClaw empty-corpus edge.

### Changed
- **Behavioral Review Remediation Completion**: Completed the remaining Wave 2 and Wave 3 fixes across the turn executor, run ledger, protocol ledger, execution pipeline, streaming providers, ODR tooling, and challenge-corpus adapter paths.
- **Run Ledger Authority Naming**: Renamed the dual-write compatibility repository implementation to a protocol-primary, SQLite-lifecycle-mirror authority while preserving the external `dual_write` runtime policy mode for config compatibility.
- **Roadmap And Techdebt Lane Closeout**: Archived the behavioral review source and remediation plan, removed the completed non-recurring lane from `Priority Now`, and returned `docs/projects/techdebt/` to standing maintenance only.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use `docs/projects/archive/techdebt/BR03172026/Closeout.md` and the archived remediation artifacts for historical proof; the active roadmap no longer carries this lane.

## [0.4.13] - 2026-03-17 - "The Nervous System Closure Cut"

### Added
- **NervousSystem Operator Lifecycle Coverage**: Added operator-surface API coverage for approval queue inspection, ledger inspection, replay, and audit across a single governed action lifecycle, plus the archived NervousSystem closeout record under `docs/projects/archive/nervous-system/NS03172026-V1-CLOSEOUT/`.
- **Techdebt Remediation Lane Authority**: Added the code-review finding record and active remediation plan under `docs/projects/techdebt/code_review_orket.md` and `docs/projects/techdebt/remediation_plan.md`.

### Changed
- **Resolver-Canonical NervousSystem Admission**: The NervousSystem action path now treats the policy/tool-profile resolver as the canonical admission path, keeps pre-resolved flags as compatibility-only behavior, and exposes the operator surfaces through the kernel API/router/engine stack instead of temporary harness-only behavior.
- **NervousSystem Lane Closeout**: Closed and archived the NervousSystem roadmap lane after live evidence completion, removed it from active roadmap execution, and refreshed the archive docs so they no longer claim active authority.
- **Roadmap Priority Now**: Promoted the techdebt remediation plan to the first `Priority Now` slot while keeping standing techdebt maintenance as a separate recurring lane.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use `docs/projects/techdebt/remediation_plan.md` as the canonical execution plan for the active techdebt lane.

## [0.4.12] - 2026-03-17 - "The Truth Lane Closure Cut"

### Added
- **Truthful Runtime Phase D-E Contracts**: Added the durable memory trust and conformance governance contracts in `docs/specs/TRUTHFUL_RUNTIME_MEMORY_TRUST_CONTRACT.md` and `docs/specs/TRUTHFUL_RUNTIME_CONFORMANCE_GOVERNANCE_CONTRACT.md`.
- **Truthful Runtime Governance Checks And Live Proof**: Added the conformance governance snapshot/checker, live Phase D-E acceptance coverage, and the corresponding archive closeout records and contract deltas for the final truthful-runtime phases.

### Changed
- **Governed Memory Trust Handling**: Memory writes and governed synthesis now stamp canonical memory-policy metadata, fail closed on stale or contradictory durable fact updates unless explicit user correction is provided, and filter stale/unverified memory from prompt-context rendering.
- **Runtime Truth Contract Inventory And Gate Enforcement**: Run-start contract emission and the truthful-runtime acceptance gate now include `conformance_governance_contract.json` and enforce the new conformance-governance check alongside existing runtime-truth gates.
- **Lane Authority Cleanup**: Archived the truthful-runtime lane after Phase E completion, updated the active docs indexes for the new durable contracts, and retired the archived controller-workload v1 planning handoff from the active roadmap.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Promotion evidence that is otherwise eligible now still requires explicit operator sign-off as defined by `docs/specs/TRUTHFUL_RUNTIME_CONFORMANCE_GOVERNANCE_CONTRACT.md`.

## [0.4.11] - 2026-03-16 - "The Phase C Truth Cut"

### Added
- **Truthful Runtime Phase C Contracts**: Added the durable narration-effect audit and source-attribution contracts in `docs/specs/TRUTHFUL_RUNTIME_NARRATION_EFFECT_AUDIT_CONTRACT.md` and `docs/specs/TRUTHFUL_RUNTIME_SOURCE_ATTRIBUTION_CONTRACT.md`.
- **Phase C Governance Checks**: Added policy check scripts, contract snapshots, and live acceptance coverage for narration/effect auditing and source-attribution enforcement.

### Changed
- **Phase C Runtime Truth Enforcement**: Extended the execution pipeline, packet-2 summary surfaces, and run-truth acceptance gate so live runs now reconstruct packet-2 facts from runtime-owned evidence, fail closed on missing source-attribution receipts, and record machine-readable failure reasons instead of success-shaped drift.
- **Truthful Runtime Lane Authority**: Closed and archived the active Phase C plans, extracted the remaining durable contracts, and updated roadmap/lane authority so only Phases D-E remain staged after the Phase C closeout.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- None.

## [0.4.10] - 2026-03-16 - "The Sandbox Lifecycle Hardening Cut"

### Added
- **Sandbox Runtime Inspection Service**: Added `SandboxRuntimeInspectionService` so sandbox startup, health checks, and recovery can read live Docker container state directly from project labels instead of relying on compose-file-local `docker-compose ps` output.
- **Lifecycle Hardening Coverage**: Added contract and integration coverage for legacy host-id cleanup matching, retryable cleanup scheduling, startup-failure terminalization, and active runtime restart-loop detection.

### Changed
- **Sandbox Startup And Recovery**: Sandbox creation now waits for initial core-service health, starting records only become active after verified running state, and recovery terminalizes non-running or restart-looping runtimes with cleanup scheduling instead of leaving them in false-active state.
- **Cleanup Claiming And Retention**: Cleanup authority now accepts legacy `host:pid` host ids on the same daemon, cleanup claims can retry terminal records stuck in `cleanup_state=failed`, and failed/blocked/canceled/reclaimable cleanup retention defaults now expire after one hour.
- **Routine Live Proof Sandbox Guarding**: Updated contributor guidance, recorder scripts, and provider-backed live tests so non-acceptance proof runs set `ORKET_DISABLE_SANDBOX=1` and do not leave routine `orket-sandbox-*` resources behind.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Only explicit sandbox acceptance work should run without `ORKET_DISABLE_SANDBOX=1`; routine provider-backed live proof should keep sandbox creation disabled.

## [0.4.9] - 2026-03-15 - "The Provenance Ledger Cut"

### Added
- **Truthful Runtime Packet-2 Contracts**: Added the durable repair-ledger and artifact-provenance contracts in `docs/specs/TRUTHFUL_RUNTIME_REPAIR_LEDGER_CONTRACT.md` and `docs/specs/TRUTHFUL_RUNTIME_ARTIFACT_PROVENANCE_CONTRACT.md`.
- **Truthful Runtime Live Proof Recorders**: Added recorder scripts, staged candidate artifacts, and live proof coverage for packet-1 boundary cleanup, packet-2 repair history, and artifact provenance.

### Changed
- **Run Summary Truth Surfaces**: Extended `run_summary.json`, finalization, and run-ledger reconstruction so finalized runs can emit packet-1 provenance/conformance, packet-2 repair-ledger history, and artifact provenance derived from runtime-owned facts.
- **Truthful Runtime Lane Authority**: Archived the completed packet-1 cleanup and frozen Phase C cycle-1 slices, extracted the packet-1 boundary realignment delta, and left only the remaining packet-2 backlog plus Phases D-E staged.
- **Benchmark Artifact Workflow**: Added staging-catalog authority and sync rules so agent-proposed benchmark artifacts stay in `benchmarks/staging/` until explicit publication approval.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Stage new benchmark proof candidates under `benchmarks/staging/` and promote them to `benchmarks/published/` only after explicit approval.

## [0.4.8] - 2026-03-14 - "The Packet-1 Lane Cut"

### Added
- **Truthful Runtime Packet-1 Contract**: Added the durable packet-1 runtime truth contract in `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md` covering provenance, truth classification, silent fallback defects, and packet-1 conformance.
- **Truthful Runtime Project Lane**: Added the active truthful-runtime project lane under `docs/projects/truthful-runtime/` with the bounded Phase C packet-1 requirements and active implementation plan plus staged continuation plans for the remaining hardening backlog.

### Changed
- **Roadmap And Project Authority**: Updated the active roadmap and archived truthful-runtime closeout/staging references so the current packet-1 work now points at the new truthful-runtime project paths instead of the old future-lane locations.
- **Root UI Surface Cleanup**: Removed the leftover root `UI/` stub, stale contributor/vendor-tree references, and orphaned dashboard/UI env-template entries now that the UI will live in another codebase.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- None.

## [0.4.7] - 2026-03-14 - "The Claim E Closure Cut"

## [0.4.6] - 2026-03-14 - "The Causal Basis Cut"

### Added
- **Deterministic Drift Remediation Authority**: Added the active `DD03142026` deterministic-drift requirements and remediation plan so Claim E implementation can proceed from a single governed techdebt lane with anti-flake closure gates, explicit compare-surface rules, and a publishable resolution package contract.
- **Live Sandbox Maintenance Baseline Runner**: Added `scripts/techdebt/run_live_maintenance_baseline.py` plus contract coverage so maintenance work now has one canonical live sandbox baseline command with evidence payloads, diff-ledger output, and strict failure behavior.
- **Recurring Maintenance Cycle Report**: Added the `2026-03-14_cycle-a` recurring maintenance report artifact recording gate audit, docs hygiene, and canonical pytest freshness results.

### Changed
- **Roadmap And Staging Authority**: Activated `DD03142026` in `Priority Now`, superseded the older staged Claim E future plan as a staging ancestor, and kept the future lane scoped to the remaining staged truthful-runtime work only.
- **Maintenance Workflow Guidance**: Updated contributor and recurring-maintenance authority so live sandbox baseline proof now has a canonical command and checklist section instead of ad hoc maintenance handling.
- **Deterministic Test Fixtures**: Updated prompt-compiler monkeypatches to accept keyword arguments across orchestrator tests and fixed sandbox recovery tests to pin lifecycle timestamps deterministically.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Use `python scripts/techdebt/run_live_maintenance_baseline.py --baseline-id <baseline_id> --strict` when maintenance work needs canonical live sandbox baseline proof.

## [0.4.5] - 2026-03-13 - "The Archived Recovery Cut"

### Added
- **Claim E Drift Diff Summary**: Added a published operator-surface diff summary for the fresh append-only live Claim E rerun so the remaining nondeterminism is shareable without referring back to hidden proof roots.
- **Staged Claim E Hardening Lane**: Added a dedicated staged follow-on plan for runtime-stability live deterministic-compare hardening after the recovery lane was truthfully closed.

### Changed
- **Governed Prompt Contract**: Updated governed prompt compilation, message building, corrective prompts, and strict response parsing so protocol-governed turns require a single JSON envelope without false `E_MARKDOWN_FENCE` hits from fenced content inside JSON strings.
- **Governed Read Cardinality**: Relaxed governed `read_file` cardinality to required-path coverage while keeping single-shot required tools fail-closed, and aligned the corresponding runtime contract/error-code authority.
- **Runtime Retry and Policy Enforcement**: Allowed system retry requeues from `in_progress` back to `ready`, tightened governance handling after corrective reprompts, and removed the stale `reforger_inspect` requirement from the requirements-analyst governed seat.
- **Live Proof Closeout Truthfulness**: Archived the runtime-stability live recovery lane, refreshed the accepted published proof with fresh append-only Claim E drift evidence plus Claim G success evidence, and moved the remaining Claim E work into a staged hardening lane instead of leaving it as fake active closeout work.
- **Release Tag Range Enforcement**: Tightened the core release guard and workflow so pushed `main` ranges require matching annotated release tags on each governed post-`0.4.0` commit, not just the branch head.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Continue pushing each `main` release commit with its matching annotated `v<version>` tag.

## [0.4.4] - 2026-03-13 - "The Tag Truth Cut"

### Added
- **Head Tag Enforcement**: Added release-policy enforcement for matching annotated `v<version>` tags on pushed `main` `HEAD` commits, with targeted guard coverage for the required head-tag path.

### Changed
- **Release Workflow Truthfulness**: Clarified contributor and release-policy authority so a core version bump is not complete until the matching annotated tag is created and pushed.
- **Commit Discipline Enforcement**: Removed the stale docs-only exemption from the core release policy guard so docs-only `main` commits must advance version and tag just like any other release step.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- Ensure each `main` commit is pushed with its matching annotated `v<version>` tag.

## [0.4.3] - 2026-03-13 - "The Published Proof Bundle"

### Added
- **Published Live Proof Support Bundle**: Added the published support folder for the `2026-03-13` live runtime-stability proof so the curated artifact now ships with its referenced evidence files.

### Changed
- **Published Artifact Self-Containment**: Repointed the published live runtime-stability proof JSON away from `benchmarks/results/...` and into `benchmarks/published/General/...` so the published lane no longer depends on non-exposed result paths.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- None.

## [0.4.2] - 2026-03-13 - "The Live Proof Cut"

### Added
- **Live Runtime Proof Coverage**: Added provider-backed live runtime-stability proof nodes for illegal state transitions, path traversal, and strict replay compatibility on missing workspace snapshots.
- **Published Live Runtime Proof Artifact**: Added a curated published artifact for the 2026-03-13 Ollama `qwen2.5-coder:7b` runtime-stability proof package.

### Changed
- **Live Acceptance Truthfulness**: Tightened the live acceptance fixture and assertions so provider-backed runs must emit fresh run roots, protocol-capable artifacts, and runtime verification payloads before claiming success.
- **Testing Authority**: Updated the testing policy so live provider-backed proof is the highest-authority evidence, unit tests are minimal support proof, and non-live lanes cannot be presented as live proof.
- **Live Proof Recovery Tracking**: Reduced the active runtime-stability recovery plan to the actual remaining work only, with closed claims moved to canonical evidence references and open claims limited to B, E, and G.
- **Release Discipline**: Removed the docs-only version-bump exemption from contributor and release-versioning policy so every commit on `main` must advance the core version and changelog.
- **Repository Hygiene**: Collapsed pytest temp ignore rules to `.pytest_*` to reduce git noise from live proof runs.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- None.

## [0.4.1] - 2026-03-13 - "The Structural Closeout"

### Added
- **Canonical Run Summary Contract**: Added the runtime `run_summary.json` implementation, schema, deterministic reconstruction proof, and replay-parity coverage for finalized runs.
- **Runtime-Stability Archive Summary**: Added the archived closeout summary for the completed runtime-stability structural lane and archived its supporting requirements packets.
- **Recurring Maintenance Evidence**: Recorded the `2026-03-13_cycle-a` techdebt maintenance cycle evidence with gate audit, docs hygiene, and full-suite pytest results.

### Changed
- **Boundary and Replay Truth**: Narrowed the active runtime-stability requirements to the shipped v0 boundary and protocol-replay operator surfaces, and fixed replay compatibility handling so missing workspace snapshots fail closed instead of scanning the current repo.
- **Minimal Tool Baseline Authority**: Narrowed the active core-tool baseline contract to the shipped minimal registry and invocation-manifest surfaces, added the matching contract delta, and aligned proof accordingly.
- **Roadmap State**: Archived the completed runtime-stability closeout and green-requirements projects, removed the lane from `Priority Now`, and left only active maintenance plus staged/future items in the roadmap.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- None.

## [0.4.0] - 2026-03-13 - "The Semantic Gate"

### Added
- **Core Release Governance**: Added canonical core release/versioning policy, release gate checklist, proof report template, release policy CI workflow, and release preparation tooling for governed core releases.
- **Release Authority Indexing**: Added explicit release authority references in current workflow and authority docs so release prep, proof storage, and tag discipline now have canonical paths.
- **Runtime Stability Closeout Plans**: Added direct closeout implementation plans for the currently active runtime-stability slices, including decision locks for SPC-01, SPC-02, SPC-05, and SPC-06.

### Changed
- **Core Version Baseline**: Promoted the core engine to `0.4.0` as the first process-backed semantic release milestone.
- **Semantic Versioning Start**: Core release discipline now starts at `0.4.0`; subsequent non-exempt commits on `main` are governed by the release/versioning policy rather than the previous ad hoc cut pattern.
- **Roadmap and Requirements Authority**: Kept runtime-stability closeout and supporting requirements lanes active under `docs/projects/` while direct closeout plans iterate, instead of treating decision packets as automatically archive-ready.

### Compatibility
- `compatibility_status`: `preserved`
- `affected_audience`: `internal_only`
- `migration_requirement`: `none`

### Required Operator or Extension-Author Action
- None.

## [0.3.18] - 2026-03-12 - "The License Cut"

### Added
- **Source-Available Licensing**: Added the Orket Business Source License 1.1 bundle, including the root license text and companion commercial licensing guidance.

### Changed
- **Package Metadata**: Updated package metadata and repository docs to point to the canonical license files.

## [0.3.17] - 2026-03-12 - "Runner Lifecycle Truth"

### Added
- **Local Runner Lifecycle Proof**: Added local Gitea runner lifecycle inspection and proof scripts plus contract tests for cleanup classification and proof output.

### Changed
- **Governance Guidance**: Tightened CI/process guidance around self-hosted runner lifecycle boundaries and corrected Docker closeout scope so sandbox cleanup is not overclaimed.
- **Archive Evidence**: Archived the local Gitea runner lifecycle implementation and closeout documents with live-proof references.

## [0.3.16] - 2026-02-11 - "The Dogfood Cut"

### Added
- **Decision Node Architecture**: Introduced planner, router, prompt-strategy, and evaluator decision-node contracts with plugin registry and default built-ins.
- **Contract Tests**: Added decision-node contract/registry tests and expanded policy + webhook DB test coverage.
- **Load Evidence Artifacts**: Archived benchmark evidence under `benchmarks/results/`.

### Changed
- **Orchestrator Decomposition**: Candidate planning, seat routing, model/dialect strategy, and success/failure evaluation now route through decision-node boundaries.
- **Governance Hardening**: Replaced broad exception handling across the main `orket/` runtime paths with typed handling where practical; true CLI/API entry boundaries still retain top-level crash logging handlers by policy.
- **Release Pipeline**: Added CI Docker smoke and migration smoke jobs, plus runbook release checklist alignment.

### Removed
- **Legacy Review Doc**: Deleted `CODE_REVIEW.md` from tracked repository during cleanup.

## [0.3.11] - 2026-02-10 - "The Clean Sweep"

### Changed
- **Repository Cleanup**: Removed obsolete roadmaps and internal agent logs from the tracked repository.
- **Documentation**: Established `docs/ROADMAP.md` as the single source of truth.
- **Security**: Hardened webhook secret handling (fails fast if secret is missing).
- **API**: Added Pydantic models for better request validation.

## [0.3.9] - 2026-02-09 - "The Async Sovereignty"

### Added
- **Async Native Core**: Migrated all I/O to `aiofiles`, `aiosqlite`, and `httpx`.
- **Security Sovereignty**: Implemented strict `Path.is_relative_to()` checks and directory isolation (`agent_output/` vs `verification/`).
- **TurnExecutor**: Decomposed the monolithic loop into a specialized async executor.
- **PolicyViolationReport**: Mechanical reporting for governance failures.
- **Gitea Webhook**: Fully functional webhook server for PR automation.

### Changed
- **Dependency Management**: Consolidated all versions into `pyproject.toml`.
- **Datetime**: Replaced `datetime.utcnow()` with `datetime.now(UTC)` globally.
- **Exception Handling**: Removed all bare `except:` clauses.

## [0.3.8] - 2025-02-09 - "The Diagnostic Intelligence"

### Added
- **WaitReason Enum**: Explicit diagnostic tracking for blocked/waiting cards (RESOURCE, DEPENDENCY, REVIEW, INPUT)
- **BottleneckThresholds Configuration**: Configurable thresholds for bottleneck detection to prevent alert fatigue
- **Priority Migration**: Automatic conversion from legacy string priorities ("High"/"Medium"/"Low") to numeric values (3.0/2.0/1.0)
- **Multi-Role State Validation**: State machine now supports validating transitions against multiple roles
- **Golden Flow Test**: Comprehensive end-to-end sanity test for orchestration engine (`tests/test_golden_flow.py`)
- **Wait Reason Enforcement**: State machine now requires explicit wait_reason when transitioning to BLOCKED or WAITING_FOR_DEVELOPER states
- **iDesign Validator Service**: New service for enforcing architectural boundaries (`orket/services/idesign_validator.py`)

### Changed
- **Priority System**: Migrated from string-based ("High"/"Medium"/"Low") to float-based (3.0/2.0/1.0) for precise sorting
- **Schema Field Validation**: Improved alias handling in verification fields using AliasChoices
- **State Machine Governance**: Enhanced role-based enforcement with multi-role support (allows agents with multiple roles)
- **Verification System**: Refactored verification logic for better diagnostics and error handling
- **Agent Factory**: Improved agent creation with better role resolution
- **Tool Parser**: Enhanced tool extraction and validation logic
- **Critical Path**: Improved priority-based sorting and dependency resolution
- **Test Suite**: Cleaned up test files, removed obsolete examples

### Fixed
- **Schema Migration**: Fixed backward compatibility issues with legacy priority strings
- **Verification Aliases**: Corrected field alias mappings for verification fixtures
- **Line Ending Warnings**: Normalized line endings across core modules (LF → CRLF on Windows)

### Removed
- **Obsolete Tests**: Removed deprecated test files (`test_examples_tictactoe.py`, `test_flow_loads.py`)

## [0.3.7] - 2025-02-08 - "The Stabilization Recovery"

### Added
- Critical Path sorting implementation
- Audit Ledger (Transactions) tracking
- Mechanical Failure Reporting

### Changed
- Hardened React UI against runtime crashes
- Fixed backend schema mismatches
- Optimized Epic mapping with AliasChoices for robust data hydration

### Fixed
- WorkStation stability issues

## [0.3.6] - 2025-02-08 - "The Enforcement Pivot" / "The Integrity Release"

### Added
- Core StateMachine for mechanical governance
- Atomic Roles implementation
- Exponential backoff retry logic for LLM calls
- Hardware-aware multi-modal support (CUDA/CPU auto-detection)

### Changed
- Merged Skills into atomic Roles
- Simplified project structure
- Ignored local dev scripts
- **Tool Decomposition:** Refactored monolithic ToolBox into specialized toolsets (FileSystem, Vision, Cards)
- **SRP-Based Schema:** Decoupled metrics from verification logic in IssueConfig
- Pivoted from descriptive orchestration to mechanical enforcement model

### Security
- Environment-based credential management with `.env` files
- `.gitignore` guards for sensitive files

### Removed
- Legacy Skills system (consolidated into Roles)

## [0.3.5] - 2025-02-08 - "The McElyea Reforge"

### Added
- Centralized orchestration engine
- Atomic Roles system
- NoteStore for session state
- Structural Reconciler for data consistency
- Collapsible tree view in WorkStation
- Binocular Preview feature

### Changed
- Strategic refactor into decoupled, data-driven architecture
- Restored WorkStation with improved UI

## [0.3.1] - 2025-02-07

### Changed
- Polymorphic refactor for Orket EOS
- Market Edge Suite integration

## [0.3.0] - 2025-02-07 - "iDesign Victory"

### Added
- iDesign enforcement framework
- Prompt Engine updates
- Book → Card terminology migration

### Changed
- Major architectural alignment with iDesign principles
- Venue interface for Traction integration

---

## Version Strategy

- **v0.3.x**: Internal runtime, governance, and release-process hardening.
- **v0.4.x**: Governed semantic-release era beginning with the first process-backed core release milestone. Runtime closeout lanes continue under normal roadmap control instead of blocking semantic versioning from starting.
