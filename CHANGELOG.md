# Changelog

All notable changes to Orket will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- **Behavioral Review Remediation Completion**: Completed the remaining Wave 2 and Wave 3 fixes across the turn executor, run ledger, protocol ledger, execution pipeline, streaming providers, ODR tooling, and OpenClaw torture adapter paths.
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
