# Control-Plane Convergence Workstream 1 Closeout
Last updated: 2026-03-29
Status: Partial closeout artifact
Owner: Orket Core
Workstream: 1 - Canonical workload, run, and attempt promotion

## Objective

Record the slices already landed under Workstream 1 without over-claiming workstream completion.

Closed or narrowed slices captured here:
1. canonical workload projection family for cards, ODR, and extension workloads
2. shared governed workload catalog for the main control-plane publishers
3. canonical sandbox workload publication on the default runtime path
4. invocation-scoped top-level cards epic run, attempt, and start-step publication
5. manual review-run run, attempt, and start-step publication plus control-plane-backed read projection
6. cards `run_summary.json` read projection of durable cards-epic run, attempt, and start-step truth
7. fresh `run_start_artifacts` `run_identity.json` demotion to explicit session-bootstrap projection-only evidence, with bootstrap reuse plus summary consumers now failing closed if that framing drifts
8. fresh `retry_classification_policy` demotion to explicit projection-only, non-authoritative attempt-history guidance
9. fresh review-run manifests now explicitly point execution-state authority at durable control-plane records while marking lane outputs non-authoritative for run/attempt state
10. governed kernel direct API and async engine responses now surface canonical durable `control_plane_step_id` refs when step truth exists instead of dropping that step identity on the response contract
11. governed turn-tool protocol receipt invocation manifests now surface canonical durable `control_plane_step_id` refs when governed step truth exists instead of leaving step authority only as a bare protocol `step_id`
12. reconstructed protocol run-graph tool-call nodes now preserve canonical durable turn-tool control-plane refs, including `control_plane_step_id`, when manifest evidence exists
13. receipt-derived artifact provenance entries now preserve canonical governed turn-tool `control_plane_run_id`, `control_plane_attempt_id`, and `control_plane_step_id` refs when authoritative receipt-manifest provenance exists for the generated artifact
14. packet-2 source-attribution summaries now preserve those same canonical governed run, attempt, and step refs when the source-attribution receipt artifact already has authoritative artifact-provenance evidence
15. packet-2 narration/effect-audit entries and idempotency summaries now preserve those same canonical governed run, attempt, and step refs when authoritative protocol receipt-manifest evidence exists for the narrated effect
16. packet-1 provenance now preserves those same canonical governed run, attempt, and step refs when the selected primary artifact output is backed by authoritative artifact-provenance evidence
17. persisted review-lane deterministic-decision and model-assisted-critique artifacts now explicitly mark execution-state authority as `control_plane_records`, mark lane outputs non-authoritative for execution state, and carry canonical review-run run, attempt, and step refs when durable review-run publication exists
18. human review CLI output now reads the durable review control-plane summary strongly enough to surface run/attempt state, start-step kind, and canonical run/attempt/step refs instead of compressing that surface to state-only text
19. cards `run_summary.json` `control_plane` block now explicitly fails closed unless it keeps declaring `projection_only=true` with `projection_source=control_plane_records`
20. review-run result and CLI `control_plane` summary now explicitly declares `projection_only=true` with `projection_source=control_plane_records` and fails closed if that framing drifts, if lower-level projected attempt or step refs survive after parent run or attempt refs drop, if projected `attempt_state` or `attempt_ordinal` survives after projected `attempt_id` drops, if projected `step_kind` survives after projected `step_id` drops, if projected run/attempt/step ids drift from the enclosing review result run identity and manifest control-plane refs, if it keeps projected run/attempt/step ids while dropping projected run metadata, attempt state, or step kind, or if the embedded manifest drops control-plane refs still carried by the returned summary
21. review-run manifest plus deterministic/model-assisted lane artifacts now fail closed if their `execution_state_authority=control_plane_records` and non-authoritative execution-state markers drift, or if lower-level manifest or lane `control_plane_attempt_id` / `control_plane_step_id` refs survive after parent run or attempt refs drop
22. `orket review replay --run-dir` now validates persisted review manifest and lane-artifact execution-authority markers before replay and fails closed if those persisted markers drift
23. review answer-key scoring now validates persisted review manifest and lane-artifact execution-authority markers before treating review bundle JSON as trustworthy evidence and fails closed if those persisted markers drift
24. review consistency-signature extraction now validates persisted review manifest and lane-artifact execution-authority markers before treating review bundle JSON as trustworthy evidence and fails closed if those persisted markers drift
25. embedded review-result `manifest` output now validates persisted execution-authority markers before leaving the process and fails closed if those markers drift or if a returned `control_plane` projection still carries control-plane refs the embedded manifest has dropped
26. legacy cards `run_summary` and finalize consumers now validate reused `run_identity.json` projection framing instead of silently consuming drifted bootstrap run evidence
27. code-review probe artifact bundles now emit review-bundle execution-authority markers plus a bundle manifest and aligned bundle-local `run_id` values on deterministic/model-assisted lane payloads so shared answer-key scoring stays aligned with fail-closed review bundle validation
28. shared probe/workload helpers, MAR audit completeness and compare surfaces, and training-data extraction now consume one shared validated legacy `run_summary.json` loader before trusting summary JSON as run evidence
29. review answer-key scoring, review consistency-signature extraction including the truncation-bounds snapshot path, and `orket review replay --run-dir` now consume shared validated review-bundle payload or artifact loaders instead of validating persisted review-bundle authority markers and then rereading lane JSON, snapshot inputs, or replay inputs ad hoc
30. governance dashboard seed metrics now validate persisted `run_ledger.summary_json` payloads against the canonical run-summary contract and sanitize persisted `run_ledger.artifact_json` through the shared validated run-ledger projection seam before deriving session-status or degrade signals, so malformed legacy summary or artifact rows register as invalid-payload signals instead of silently shaping fallback or degrade heuristics
31. API run-detail and session-status surfaces now validate persisted `run_ledger.summary_json` payloads against the canonical run-summary contract before exposing summary blocks, and run detail now also sanitizes the nested `run_ledger.summary_json` projection, so malformed legacy summary payloads fail closed to empty summary projections instead of silently shaping API-visible run state
32. API run-detail and session-status surfaces now also sanitize persisted `run_ledger.artifact_json` through the shared validated run-ledger record seam, so malformed legacy artifact payloads fail closed to empty artifact projections instead of leaking raw invalid run-ledger artifact state through API-visible run surfaces
33. direct `orket review replay --snapshot ... --policy ...` now also reuses the shared validated review-bundle artifact loader when those files target canonical bundle artifacts from one review-run directory, so replay fails closed on drifted persisted review authority markers instead of bypassing bundle validation through raw replay inputs
34. protocol/sqlite run-ledger parity consumers now also consume the shared validated run-ledger projection family, and the SQLite run-ledger adapter now preserves malformed persisted summary/artifact payload text long enough for that seam to detect it, so malformed `summary_json` or `artifact_json` payloads fail closed as explicit parity drift instead of disappearing inside the adapter or being normalized away into false-green parity
35. protocol/sqlite run-ledger parity-campaign rows and campaign telemetry now preserve side-specific invalid projection-field detail instead of collapsing malformed persisted run-ledger projection drift into generic mismatch counts
36. protocol rollout evidence bundle summaries now preserve those side-specific invalid projection-field counts instead of collapsing malformed parity drift back to generic mismatch totals
37. protocol enforce-window signoff payloads and capture manifests now preserve those same side-specific invalid projection-field counts instead of reducing malformed parity drift back to generic signoff or manifest pass-fail summaries
38. protocol cutover-readiness outputs now preserve those same side-specific invalid projection-field counts instead of flattening malformed parity drift back to generic ready or passing-window totals
39. protocol rollout, signoff, and cutover outputs now consume one shared invalid-projection detail helper instead of carrying divergent local parsing logic
40. live-acceptance pattern reporting now validates persisted `metrics_json` and `db_summary_json` row payloads and records explicit invalid-payload signals instead of silently flattening malformed rows into empty state
41. microservices unlock gating now fails closed when the live-acceptance report is missing or malformed on `run_count`, `session_status_counts`, `pattern_counters`, or `invalid_payload_signals`, or reports any non-zero invalid source-row counts instead of allowing stale or malformed live-report payloads to produce false-green unlock decisions
42. monolith variant matrix summaries now preserve normalized live-report `invalid_payload_signals`, and both monolith readiness plus matrix-stability gates now fail closed when those matrix summary counts are missing, malformed, or non-zero instead of trusting rate-only matrix summaries derived from malformed live-report rows
43. architecture pilot matrix comparison now preserves side-specific invalid-payload totals, detailed per-architecture invalid-payload maps, and failures from the underlying pilot summaries, and microservices pilot stability now fails closed when that persisted comparison detail is missing, malformed, non-zero, or internally inconsistent with its own per-architecture invalid-payload maps instead of trusting architecture delta summaries or stored totals alone
44. runtime-policy pilot-stability reads now fail closed when the persisted pilot-stability artifact is structurally malformed instead of trusting a bare `stable` flag
45. microservices pilot decision now fails closed when the persisted unlock artifact is structurally malformed instead of trusting a bare `unlocked` flag
46. runtime-policy microservices unlock reads now fail closed when the persisted unlock artifact is structurally malformed, reuse the same structural unlock-report validator as microservices pilot decision, and default to the canonical acceptance artifact paths instead of stale pre-acceptance output paths
47. runtime-policy pilot-stability reads now also fail closed when the persisted pilot-stability artifact is internally inconsistent, with the shared acceptance-report validator rejecting drift between top-level `stable` / `failures`, per-check stability evidence, and `artifact_count`
48. runtime-policy microservices unlock reads and microservices pilot decision now also fail closed when the persisted unlock artifact is internally inconsistent, with the shared acceptance-report validator rejecting drift between top-level `unlocked` / `failures` and per-criterion `ok` / `failures` detail
49. persisted `run_summary.json` validators, shared summary loaders, summary builders, finalize helpers, and reconstruction now also reject drifted `run_identity` projection framing plus mismatched `run_identity.run_id`, and finalize-time bootstrap validation now degrades cleanly instead of aborting closeout while excluding transient invalid bootstrap identity from degraded summary output
50. review consistency-signature report validation now also rejects malformed nested baseline/default/strict/replay signature contract fields including required digests, deterministic finding-row code/severity/message/path/span/details shape, deterministic-lane version, executed-check lists, and truncation framing before producer write or persisted report trust
51. fresh review manifest plus deterministic/model-assisted lane artifact serialization and shared validated review-bundle payload and artifact loaders now also reject missing manifest or lane-payload `run_id`, fresh manifest or lane-payload `control_plane_run_id` that drifts from the same artifact `run_id`, manifest or lane attempt or step refs that drift outside the declared `control_plane_run_id` lineage, missing lane-payload `control_plane_run_id` / `control_plane_attempt_id` / `control_plane_step_id` when the manifest declares them, lower-level manifest or lane `control_plane_attempt_id` / `control_plane_step_id` refs that survive after parent run or attempt refs drop, plus manifest or lane-payload `run_id`, `control_plane_run_id`, `control_plane_attempt_id`, and `control_plane_step_id` drift, instead of validating execution-authority markers alone
52. review diff, PR, and files CLI paths now surface review-result serialization drift at this boundary as structured `E_REVIEW_RUN_FAILED` output instead of leaking an uncaught exception when embedded manifest control-plane refs have been dropped
53. cards `run_summary.json` `control_plane` projections now also fail closed when projected `current_attempt_id` drifts from projected `attempt_id` when both are present, and finalize-time degradation preserves the durable run/attempt records while dropping that invalid transient summary projection
54. cards `run_summary.json` `control_plane` projections now also fail closed when projected `attempt_id` drifts outside the projected run lineage, and finalize-time degradation preserves the durable run/attempt records while dropping that invalid transient summary projection
55. cards `run_summary.json` `control_plane` projections now also fail closed when projected `step_id` drifts outside the projected run lineage, and finalize-time degradation preserves the durable run/attempt/step records while dropping that invalid transient summary projection
56. cards `run_summary.json` `control_plane` projections now also fail closed when a projected cards run carries `run_id` but drops core run metadata such as `run_state`, workload identity, or policy/config snapshot refs, and finalize-time degradation preserves the durable run record while dropping that invalid transient summary projection
57. review-run result and CLI `control_plane` summaries now also fail closed when they keep projected run, attempt, or step ids while dropping projected run metadata, attempt state, or step kind, when lower-level projected attempt or step refs survive after parent run or attempt refs drop, when projected `attempt_state` or `attempt_ordinal` survives after projected `attempt_id` drops, when projected `step_kind` survives after projected `step_id` drops, or when projected attempt or step refs drift outside the projected run lineage
58. review consistency report production now also fails closed before report serialization when default, strict, replay, or baseline `run_id` is empty, and now validates shared contract framing before write while still allowing truthful failed outcomes to persist as failed reports, instead of either emitting a blank run-like field or misclassifying failed outcomes as malformed contract drift
59. persisted review consistency-report validation now also fails closed before trusting report JSON when `contract_version` drifts or when default, strict, replay, or baseline report `run_id` is empty instead of trusting shallow `ok` or counter fields alone
60. review answer-key scoring now also emits explicit `reviewrun_answer_key_score_v1` report payloads with required top-level `run_id` plus fixture/snapshot/policy provenance fields, required nested deterministic/model-assisted score blocks whose aggregate totals must stay aligned with the per-issue rows they summarize, explicit model reasoning/fix weights needed to prove reasoning and fix subtotals against those same rows, required per-issue row shape, and disabled model blocks that cannot carry derived model activity, and workload-side code-review probe score consumers now fail closed if that score-report contract drifts at the nested block, aggregate, issue-row, or top-level provenance level instead of trusting ad hoc dict shape
61. review consistency-signature report validation now also rejects malformed scenario-local `truncation_check` contract fields including snapshot digests, byte counts, and boolean flags before producer write or persisted report trust
62. cards, ODR, and extension workload execution now all resolve through `orket/application/services/control_plane_workload_catalog.py`, with the former `orket/runtime/workload_adapters.py` shim retired entirely, extension models reduced to raw manifest data only with manifest metadata now living behind the private `_ExtensionManifestEntry` type in `orket.extensions.models`, `ExtensionRecord` now storing that metadata on `manifest_entries`, installed extension catalog persistence now writing `manifest_entries` and only compatibility-reading legacy persisted `workloads` rows while the external extension manifest contract still truthfully keeps its `workloads` array, the older private `_ExtensionManifestWorkload` noun, the public `ExtensionManifestWorkload` noun, the older `ExtensionWorkloadDescriptor` noun, the old `manifest_workloads` field, the old installed-catalog `workloads` field, and the old manifest `WorkloadRecord` alias retired from active extension surfaces, no outward `ExtensionManifestWorkload` re-export through `orket.extensions`, no outward `ExtensionManifestWorkload` runtime attribute on `orket.extensions.manager`, the former generic `ExtensionManager.resolve_workload(...)` surface retired in favor of a validation-only `has_manifest_entry(...)` probe plus the private manifest-entry lookup helper `_resolve_manifest_entry(...)`, the interaction sessions router now validates extension workload ids through that boolean probe instead of depending on a metadata-returning workload lookup surface, the former public-looking `ExtensionCatalog.resolve_manifest_entry(...)` surface retired in favor of the private catalog helper `_resolve_manifest_entry(...)`, `ExtensionManager.run_workload(...)` resolving one canonical extension `WorkloadRecord` before execution and reusing that record in extension provenance instead of minting it later, the low-level workload builders renamed private and removed from `orket.core.contracts` re-exports, and a negative governance test now failing if non-allowed modules import or call `_build_control_plane_workload_record(...)` or `_build_control_plane_workload_record_from_workload_contract(...)`
63. the legacy CLI `--rock` alias now preserves compatibility while routing through `OrchestrationEngine.run_rock(...)`, a thin wrapper over `run_card(...)`; the named runtime recommendation surface now points to `python main.py --card <card_id>` instead of blessing `--rock` as a first-class runtime noun, the legacy module-level `orchestrate_rock` helper is retired entirely, the `run_rock(...)` wrappers on `ExecutionPipeline` and `OrchestrationEngine` now survive only as thin convenience wrappers over `run_card(...)`, internal rock routing now flows through a generic epic-collection entry plus generic epic-collection runtime selectors instead of a rock-named helper seam, that generic entry now emits collection-shaped runtime payloads instead of returning a `rock` field, and rock execution remains tracked as routing-only retirement debt rather than a separate workload-authority blocker
64. touched catalog-resolved publishers for kernel action, manual review-run, governed turn-tool, orchestrator issue dispatch, orchestrator scheduler mutation and child composition, and Gitea worker execution now carry canonical catalog `WorkloadRecord` objects through run-publication and namespace-mutation helpers instead of restating workload authority as local `workload_id` / `workload_version` string-pair aliases, and the workload-authority governance test now fails if those alias constants reappear on those touched publishers
65. `run_card(...)` is now re-established as the sole public runtime execution surface, with `ExecutionPipeline.run_card(...)` dispatching through one normalized runtime-target resolver, `run_issue(...)`, `run_epic(...)`, and `run_rock(...)` reduced to thin compatibility wrappers, the extension run-action adapter now treating `run_rock` only as explicit legacy alias normalization onto `run_card(...)`, the `run_rock(...)` wrappers on `ExecutionPipeline` and `OrchestrationEngine` now surviving only as thin convenience wrappers over `run_card(...)`, internal rock routing collapsed to a generic epic-collection entry plus generic epic-collection runtime selectors that now emit collection-shaped runtime payloads instead of a `rock` field, known runtime callers such as the organization loop, PR-opened webhook path, Gitea state loop, runtime orchestration shims, touched probe/workload scripts, and live benchmark tooling now routing through `run_card(...)` or the canonical `--card` CLI entrypoint, with the live benchmark runner now also emitting card-mode runtime metadata instead of rock-named runtime identifiers or `run_mode="rock"` and the benchmark runner plus suite now defaulting their execution-mode metadata to `live-card`, and governance failing if non-CLI runtime callsites drift back onto those compatibility wrappers, if wrappers stop collapsing to that canonical surface, if the extension run-action adapter drifts back to treating `run_rock` as part of its primary run-op set instead of explicit legacy alias normalization, or if the dispatcher starts minting workload authority directly instead of routing into the workload seam through its internal entries
66. the former `orket/runtime/workload_adapters.py` surface is now retired entirely, and extension manifest metadata now lives behind the private `_ExtensionManifestEntry` type in `orket.extensions.models` with `ExtensionRecord` storing that metadata on `manifest_entries`, installed extension catalog persistence now writing `manifest_entries` and only compatibility-reading legacy persisted `workloads` rows while the external extension manifest contract still truthfully keeps its `workloads` array, the older private `_ExtensionManifestWorkload` noun, the public `ExtensionManifestWorkload` noun, the older `ExtensionWorkloadDescriptor` noun, the old `manifest_workloads` field, the old installed-catalog `workloads` field, and the old manifest `WorkloadRecord` alias retired entirely from active extension surfaces, no outward `ExtensionManifestWorkload` re-export through `orket.extensions`, no outward `ExtensionManifestWorkload` runtime attribute on `orket.extensions.manager`, the former generic `ExtensionManager.resolve_workload(...)` surface retired in favor of a validation-only `has_manifest_entry(...)` probe plus the private manifest-entry lookup helper `_resolve_manifest_entry(...)`, and the former public-looking `ExtensionCatalog.resolve_manifest_entry(...)` surface retired in favor of the private catalog helper `_resolve_manifest_entry(...)`; governance fails if the retired workload-adapter shim reappears or non-test repo code imports it, if non-test repo code imports the retired extension-manifest alias, if the retired generic extension manifest field, the retired public `ExtensionManifestWorkload` noun, the retired generic lookup surface, or the generic `workloads` key on installed catalog serialization reappears, or if `orket.core.contracts` re-exports the private workload builders
67. the cards runtime path now resolves its `WorkloadRecord` through the catalog-local helper `_resolve_cards_control_plane_workload_from_contract(...)` instead of assembling `WorkloadAuthorityInput(...)` directly inside `orket/runtime/execution_pipeline.py`, and governance now fails if that runtime entrypoint drifts back to direct cards workload-authority input construction
68. extension workload start now resolves its `WorkloadRecord` through the catalog-local helper `_resolve_extension_control_plane_workload(...)` instead of assembling `WorkloadAuthorityInput(...)` directly inside `orket/extensions/manager.py`, and governance now fails if that extension start path drifts back to direct extension workload-authority input construction
69. the private catalog-local helper names `_resolve_cards_control_plane_workload_from_contract(...)`, `_resolve_odr_arbiter_control_plane_workload_from_contract(...)`, and `_resolve_extension_control_plane_workload(...)` are no longer exported from `orket/application/services/control_plane_workload_catalog.py` `__all__`, governance now fails if production code outside their exact runtime owner paths imports them, governance now also fails if production code outside `orket/extensions/` imports the private `_ExtensionManifestEntry` type, the internal generic epic-collection runtime path now emits collection-shaped runtime payloads instead of a `rock` field, and the default generic epic-collection build token now uses `epic-collection-build-...` instead of the older `rock-build-...` prefix
70. the remaining private extension manifest metadata surfaces now use manifest-entry language instead of workload-authority language: the private `_ExtensionManifestWorkload` type is retired in favor of `_ExtensionManifestEntry`, `ExtensionRecord.manifest_workloads` is retired in favor of `manifest_entries`, installed extension catalog persistence now writes `manifest_entries` and only compatibility-reads legacy persisted `workloads` rows, the private lookup helper `_resolve_manifest_workload(...)` is retired in favor of `_resolve_manifest_entry(...)`, the former public-looking catalog lookup `ExtensionCatalog.resolve_manifest_entry(...)` is retired in favor of the private catalog helper `_resolve_manifest_entry(...)`, and the external manifest contract still truthfully keeps its `workloads` array
71. the ODR arbiter path now resolves its `WorkloadRecord` through the catalog-local helper `_resolve_odr_arbiter_control_plane_workload_from_contract(...)` instead of assembling `WorkloadAuthorityInput(...)` directly inside `scripts/odr/run_arbiter.py`, and governance now fails if that production script drifts back to direct ODR workload-authority input construction
72. the extension catalog no longer exposes a public-looking manifest lookup surface: `ExtensionCatalog.resolve_manifest_entry(...)` is retired entirely, `ExtensionManager` now calls the private catalog helper `_resolve_manifest_entry(...)`, and governance plus runtime tests now fail if the public-looking catalog lookup is reintroduced

## Touched crosswalk rows

| Row | Previous status | New status | Migration-note delta |
| --- | --- | --- | --- |
| `Workload` | `conflicting` | `conflicting` | Added one canonical projection family plus a shared governed workload catalog covering cards, ODR, extensions, sandbox, top-level cards epic execution, and manual review-run execution. Cards and ODR now route through the shared resolver, the cards runtime path now resolves its `WorkloadRecord` through the catalog-local helper `_resolve_cards_control_plane_workload_from_contract(...)` instead of assembling `WorkloadAuthorityInput(...)` directly inside `ExecutionPipeline`, the ODR arbiter path now resolves its `WorkloadRecord` through the catalog-local helper `_resolve_odr_arbiter_control_plane_workload_from_contract(...)` instead of assembling `WorkloadAuthorityInput(...)` directly inside `scripts/odr/run_arbiter.py`, extension workload execution now resolves one canonical extension `WorkloadRecord` at workload start and reuses that record in provenance, with extension workload start now resolving its `WorkloadRecord` through the catalog-local helper `_resolve_extension_control_plane_workload(...)` instead of assembling `WorkloadAuthorityInput(...)` directly inside `ExtensionManager`, those private catalog-local helper names are no longer exported from the catalog `__all__` and are now locked to their exact production owner paths, touched catalog-resolved publishers now carry canonical `WorkloadRecord` objects through run-publication and namespace-mutation helpers instead of restating workload authority as local string-pair aliases, `run_card(...)` is now the sole public runtime surface with `run_issue(...)`, `run_epic(...)`, and `run_rock(...)` reduced to thin compatibility wrappers over one normalized dispatcher, active runtime callsites such as the legacy CLI `--rock` alias, the extension run-action adapter now treating `run_rock` only as explicit legacy alias normalization onto `run_card(...)`, runtime orchestration shims, touched probe/workload scripts, and live benchmark tooling now routing directly through `run_card(...)` or the canonical `--card` CLI surface, with the benchmark runner no longer emitting rock-named runtime identifiers or `run_mode="rock"` in its own run metadata, the named runtime recommendation surface now points to `python main.py --card <card_id>`, the legacy module-level `orchestrate_rock` helper is retired entirely, the `run_rock(...)` wrappers now survive only as thin convenience wrappers over `run_card(...)`, internal rock routing now flows through a generic epic-collection entry plus generic epic-collection runtime selectors instead of a rock-named helper seam, that generic entry now emits collection-shaped runtime payloads instead of returning a `rock` field, the default generic epic-collection build token now uses `epic-collection-build-...` instead of `rock-build-...`, the old runtime workload-adapter shim is retired entirely, extension manifest metadata now lives behind the private `_ExtensionManifestEntry` type in `orket.extensions.models` with `ExtensionRecord` storing that metadata on `manifest_entries`, installed extension catalog persistence now writes `manifest_entries` and only compatibility-reads legacy persisted `workloads` rows while the external extension manifest contract still truthfully keeps its `workloads` array, the older private `_ExtensionManifestWorkload` noun, the public `ExtensionManifestWorkload` noun, the older `ExtensionWorkloadDescriptor` noun, the old `manifest_workloads` field, the old installed-catalog `workloads` field, and the old manifest `WorkloadRecord` alias retired from active extension surfaces, no outward `ExtensionManifestWorkload` re-export through `orket.extensions`, no outward `ExtensionManifestWorkload` runtime attribute on `orket.extensions.manager`, the former generic `ExtensionManager.resolve_workload(...)` surface retired in favor of a validation-only `has_manifest_entry(...)` probe plus the private manifest-entry lookup helper `_resolve_manifest_entry(...)`, the interaction sessions router now validates extension workload ids through that boolean probe instead of depending on a metadata-returning workload lookup surface, the former public-looking `ExtensionCatalog.resolve_manifest_entry(...)` surface retired in favor of the private catalog helper `_resolve_manifest_entry(...)`, extension models no longer construct control-plane workload records, the low-level builders are now private internals instead of public core-contract exports, rock execution remains routing-only retirement debt rather than a separate workload-authority blocker, and governance now fails if non-allowed modules import or call those private builders, if those touched publishers reintroduce workload string-pair aliases, if the retired workload-adapter shim reappears or non-test repo code imports it, if non-test repo code imports the retired extension manifest alias, if production code outside `orket/extensions/` imports the private `_ExtensionManifestEntry` type, if the retired generic extension `manifest_workloads` field, the retired generic extension `workloads` field, the retired public `ExtensionManifestWorkload` noun, `ExtensionManager.resolve_workload(...)`, or the retired generic catalog lookup surface reappears, if the interaction sessions router drifts back to a metadata-returning extension workload lookup instead of the validation-only `has_manifest_entry(...)` probe, if installed extension catalog serialization reintroduces the generic `workloads` key, if `ExecutionPipeline` drifts back to direct cards workload-authority input construction, if `scripts/odr/run_arbiter.py` drifts back to direct ODR workload-authority input construction, if `ExtensionManager` drifts back to direct extension workload-authority input construction, if production code outside the exact runtime owner paths imports those private catalog-local helpers, if non-CLI runtime callsites drift back onto `run_epic(...)`, `run_issue(...)`, or `run_rock(...)` compatibility wrappers, if public wrappers drift away from `run_card(...)`, if the extension run-action adapter drifts back to treating `run_rock` as part of its primary run-op set instead of explicit legacy alias normalization, if live benchmark tooling drifts back onto the legacy `--rock` CLI alias or back to rock-named runtime identifiers or `run_mode="rock"` in benchmark run metadata, if `orket.core.contracts` re-exports the private builders, or if rock routing regains standalone workload-authority status, but universal start-path authority still does not exist. |
| `Run` | `partial` | `partial` | Added first-class top-level cards epic run publication and first-class manual review-run publication, with review manifests, results, CLI projection, and persisted review lane decision/critique artifacts now reading from or pointing at durable control-plane state, and human review CLI output now surfacing canonical run refs plus durable run state instead of reducing that surface to state-only text, review-run result and CLI `control_plane` summaries now explicitly declaring `projection_only=true` with source `control_plane_records` and failing closed if that framing drifts, if lower-level projected attempt or step refs survive after parent run or attempt refs drop, if projected `attempt_state` or `attempt_ordinal` survives after projected `attempt_id` drops, if projected `step_kind` survives after projected `step_id` drops, if projected attempt or step refs drift outside the projected run lineage, if projected run/attempt/step ids drift from the enclosing review result run identity and manifest control-plane refs, if they keep projected run/attempt/step ids while dropping projected run metadata, attempt state, or step kind, or if the embedded manifest drops control-plane refs still carried by the returned summary, while diff/PR/files CLI commands now surface that serialization failure as structured `E_REVIEW_RUN_FAILED` output instead of an uncaught exception, review-run manifests plus deterministic/model-assisted lane artifacts now also fail closed if their `execution_state_authority=control_plane_records` and non-authoritative execution-state markers drift, if manifest or lane attempt or step refs drift outside the declared `control_plane_run_id` lineage, or if lower-level manifest or lane control-plane refs survive after parent run or attempt refs drop, direct `orket review replay --snapshot ... --policy ...` now also reuses the same shared validated review-bundle artifact loader when those files target canonical bundle artifacts from one review-run directory instead of bypassing bundle validation through raw replay inputs, fresh review manifest plus deterministic/model-assisted lane artifact serialization and persisted review-bundle loaders now also fail closed when manifest or lane-payload `run_id` is missing, when fresh manifest or lane-payload `control_plane_run_id` drifts from the same artifact `run_id`, when manifest or lane attempt or step refs drift outside the declared `control_plane_run_id` lineage, when lower-level manifest or lane control-plane refs survive after parent run or attempt refs drop, or when manifest-to-lane run/control-plane ids drift instead of validating markers alone, the review consistency report producer now also fails closed before report serialization when default, strict, replay, or baseline `run_id` is empty instead of emitting a blank run-like field, and the persisted `check_1000_consistency.py` validator now also fails closed before trusting report JSON when `contract_version` drifts or those default, strict, replay, or baseline report `run_id` values are empty instead of trusting shallow `ok` or counter fields alone, cards `run_summary.json` now projecting persisted cards-epic run or attempt or step truth instead of inventing a separate cards-summary run state and now failing closed if its `control_plane` block stops declaring `projection_only=true` with source `control_plane_records`, if it drops core run metadata while still carrying `run_id`, if projected `current_attempt_id` drifts from projected `attempt_id` when both are present, if projected `attempt_id` drifts outside the projected run lineage, or if projected `step_id` drifts outside the projected run lineage, shared probe/workload helpers plus MAR audit completeness and training-data extraction now also validate legacy `run_summary.json` projection framing before trusting summary JSON as evidence, persisted run-summary validators, shared summary loaders, summary builders, finalize helpers, and reconstruction now also reject drifted `run_identity` projection framing plus mismatched `run_identity.run_id`, and finalize-time bootstrap validation now degrades cleanly instead of aborting closeout while excluding transient invalid bootstrap identity from degraded summary output, governance dashboard seed metrics now also sanitize persisted `run_ledger.artifact_json` through the shared validated run-ledger projection seam instead of silently trusting malformed artifact rows, live-acceptance pattern reporting now validates persisted `metrics_json` and `db_summary_json` row payloads before deriving counters or issue-status totals and records explicit invalid-payload signals instead of silently flattening malformed rows into empty state, monolith variant matrix summaries now preserve those normalized live-report `invalid_payload_signals`, monolith readiness plus matrix-stability gates now fail closed when those matrix summary counts are missing, malformed, or non-zero instead of trusting rate-only matrix summaries derived from malformed live-report rows, architecture pilot matrix comparison now preserves side-specific invalid-payload totals, detailed per-architecture invalid-payload maps, and failures from the underlying pilot summaries, and microservices pilot stability now fails closed when that persisted comparison detail is missing, malformed, non-zero, or internally inconsistent with its own per-architecture invalid-payload maps instead of trusting architecture delta summaries or stored totals alone, runtime-policy pilot-stability reads now fail closed when the persisted pilot-stability artifact is structurally malformed or internally inconsistent instead of trusting top-level `stable` / `failures` fields, runtime-policy unlock reads and microservices pilot decision now also fail closed when the persisted unlock artifact is structurally malformed or internally inconsistent, with the shared acceptance-report validator rejecting drift between top-level `unlocked` / `failures` and per-criterion `ok` / `failures` detail instead of trusting top-level unlock state alone, microservices unlock gating now fails closed when the live-acceptance report is missing or malformed on `run_count`, `session_status_counts`, `pattern_counters`, or `invalid_payload_signals`, or reports any non-zero invalid source-row counts instead of allowing stale or malformed live-report payloads to produce false-green unlock decisions, API run-detail and session-status surfaces now also sanitize persisted `run_ledger.artifact_json` through the same validated run-ledger record seam that already guards summary projections, protocol/sqlite run-ledger parity consumers now also fail closed on malformed persisted run-ledger summary or artifact projections while the SQLite run-ledger adapter preserves malformed persisted payload text long enough for that validation seam to detect it instead of normalizing the drift away into false-green parity, protocol/sqlite parity-campaign rows plus campaign telemetry now preserve side-specific invalid projection-field detail instead of collapsing malformed persisted projection drift into generic mismatch counts, protocol rollout evidence bundle markdown now preserves those same side-specific invalid projection-field counts instead of reducing malformed parity drift back to generic mismatch totals, protocol enforce-window signoff plus capture-manifest outputs now preserve those same invalid projection-field counts instead of flattening malformed parity drift back to generic signoff or manifest pass-fail summaries, protocol cutover-readiness outputs now preserve those same invalid projection-field counts instead of flattening malformed parity drift back to generic ready or passing-window totals, and rollout/signoff/cutover now consume one shared invalid-projection detail helper instead of carrying divergent local parsers, fresh receipt-derived artifact provenance entries plus packet-1 provenance and packet-2 source-attribution, narration/effect-audit, and idempotency summaries now preserving canonical governed `control_plane_run_id` refs when authoritative receipt-manifest provenance exists, and fresh `run_start_artifacts` now explicitly mark `run_identity` as session-bootstrap `projection_only` evidence while bootstrap reuse plus legacy run-summary builders, finalize helpers, reconstruction, validators, and loaders now fail closed if that framing drifts or if `run_identity.run_id` mismatches the enclosing summary `run_id`. Legacy observability and broader summary surfaces still remain. |
| `Attempt` | `partial` | `partial` | Added first-class top-level cards epic attempt publication and manual review-run attempt publication, persisted review lane decision/critique artifacts now preserving canonical review-run `control_plane_attempt_id` while explicitly marking execution state non-authoritative, human review CLI output now surfacing canonical attempt refs plus durable attempt state instead of reducing that surface to state-only text, fresh receipt-derived artifact provenance entries plus packet-1 provenance and packet-2 source-attribution, narration/effect-audit, and idempotency summaries now preserving canonical governed `control_plane_attempt_id` refs when authoritative receipt-manifest provenance exists, and fresh retry-classification snapshots now explicitly declare `projection_only=true` with `projection_source=retry_classification_rules` plus `attempt_history_authoritative=false` so retry policy stops looking like hidden attempt truth, with run-start contract capture now validating that framing before persisting `retry_classification_policy.json`, the retry-policy checker now normalizing malformed report payloads into fail-closed error reports before diff-ledger write, rejecting invalid embedded retry-policy snapshots in both green and failure reports, falling back to the canonical retry-policy snapshot when malformed producer output omits or drifts that embedded snapshot, and the runtime-truth acceptance gate now validating both the retry-policy report contract and the persisted run-level `retry_classification_policy.json` artifact against the current canonical snapshot before trusting top-level green signals while preserving explicit fail-closed error detail from validated retry-policy reports instead of collapsing them into generic false state. Broader retry and resume behavior still remains service-local in some runtime paths. |
| `Step` | `partial` | `partial` | Added top-level cards epic invocation-start step publication and manual review-run `review_run_start` step publication, governed kernel direct API/async engine responses now surface canonical durable `control_plane_step_id` refs when step truth exists, governed turn-tool protocol receipt invocation manifests now preserve canonical `control_plane_step_id` refs instead of leaving step authority only as a bare protocol-local field, reconstructed protocol run-graph tool-call nodes now preserve those canonical refs during graph projection, persisted review lane decision/critique artifacts now preserve canonical review-run `control_plane_step_id` while explicitly marking execution state non-authoritative, human review CLI output now surfaces canonical step refs plus start-step kind instead of reducing that surface to state-only text, cards `run_summary.json` now also fails closed if projected `step_id` drifts outside the projected cards run lineage, and receipt-derived artifact provenance plus packet-1 provenance and packet-2 source-attribution, narration/effect-audit, and idempotency summaries now preserve canonical governed `control_plane_step_id` refs when authoritative receipt-manifest provenance exists. Broader runtime execution still lacks one shared step surface. |

## Code, entrypoints, tests, and docs changed

Code and entrypoints changed across the recorded Workstream 1 slices:
1. `orket/core/contracts/workload_identity.py`
2. `orket/application/services/control_plane_workload_catalog.py`
3. `orket/application/services/cards_epic_control_plane_service.py`
4. `orket/application/services/review_run_control_plane_service.py`
5. `orket/application/review/run_service.py`
6. `orket/runtime/workload_adapters.py`
7. `orket/runtime/execution_pipeline.py`
8. `orket/services/sandbox_orchestrator.py`
9. `orket/application/services/sandbox_control_plane_execution_service.py`
10. `scripts/odr/run_arbiter.py`
11. extension workload and provenance surfaces under `orket/extensions/`
12. governed workload consumers under `orket/application/services/` for kernel action, orchestrator issue, orchestrator scheduler, turn-tool, and Gitea worker execution
13. review CLI projection path in `orket/interfaces/orket_bundle_cli.py`
14. cards run-summary control-plane projection path in `orket/runtime/run_summary.py` and `orket/runtime/run_summary_control_plane.py`
15. run-start bootstrap identity demotion path in `orket/runtime/run_start_artifacts.py`
16. retry classification demotion, run-start capture validation, and acceptance-gate report validation path in `orket/runtime/retry_classification_policy.py`, `orket/runtime/run_start_contract_artifacts.py`, `scripts/governance/check_retry_classification_policy.py`, and `scripts/governance/run_runtime_truth_acceptance_gate.py`
17. review manifest execution-authority demotion path in `orket/application/review/models.py` and `orket/application/review/run_service.py`
18. governed kernel response-step projection path in `orket/application/services/kernel_action_control_plane_view_service.py`, `orket/interfaces/routers/kernel.py`, and `orket/orchestration/engine.py`
19. governed turn-tool protocol manifest control-plane step projection path in `orket/application/workflows/tool_invocation_contracts.py` and `orket/application/workflows/turn_tool_dispatcher_protocol.py`
20. governed protocol run-graph control-plane ref projection path in `orket/runtime/run_graph_reconstruction.py`
21. receipt-derived artifact provenance control-plane ref projection path in `orket/runtime/execution_pipeline.py` and `orket/runtime/run_summary_artifact_provenance.py`
22. packet-1 provenance control-plane ref projection path in `orket/runtime/execution_pipeline.py` and `orket/runtime/run_summary.py`
23. packet-2 source-attribution, narration/effect-audit, and idempotency control-plane ref projection path in `orket/runtime/phase_c_runtime_truth.py` and `orket/runtime/run_summary_packet2.py`
24. review-lane decision and critique artifact execution-authority demotion path in `orket/application/review/models.py` and `orket/application/review/run_service.py`
25. human review CLI control-plane ref projection path in `orket/interfaces/orket_bundle_cli.py`
26. review-run control-plane summary projection validation helper in `orket/application/review/control_plane_projection.py`
27. review replay bundle authority validation plus shared replay-artifact loader path in `orket/application/review/bundle_validation.py` and `orket/interfaces/orket_bundle_cli.py`, including direct `--snapshot` plus `--policy` replay when those files target canonical bundle artifacts from one run directory
28. review answer-key scoring authority validation plus shared bundle-artifact consumption path in `scripts/reviewrun/score_answer_key.py` and `scripts/reviewrun/score_answer_key_contract.py`
29. review consistency-signature authority validation plus shared replay-artifact consumption path, including truncation-bounds snapshot loading plus producer-side consistency-report contract validation before write while still allowing truthful failed outcomes to persist as failed reports, in `scripts/reviewrun/run_1000_consistency.py`, plus persisted consistency-report contract validation in `scripts/reviewrun/check_1000_consistency.py`
30. review-result manifest authority validation path in `orket/application/review/models.py`
31. run-identity projection validation path in `orket/runtime/run_start_artifacts.py`, `orket/runtime/run_summary.py`, and `orket/runtime/execution_pipeline.py`
32. code-review probe bundle authority alignment path in `scripts/workloads/code_review_probe.py`, `scripts/workloads/code_review_probe_support.py`, and `scripts/workloads/code_review_probe_reporting.py`, including aligned bundle-local lane-payload `run_id` emission before shared answer-key scoring plus fail-closed score-report contract validation before workload-side verdict shaping
33. shared validated legacy run-summary loader in `scripts/common/run_summary_support.py` plus consumer adoption in `scripts/probes/probe_support.py`, `scripts/audit/audit_support.py`, `scripts/audit/compare_two_runs.py`, and `scripts/training/extract_training_data.py`
34. shared validated review-bundle payload and artifact loaders in `orket/application/review/bundle_validation.py`, now including manifest-to-lane run/control-plane identifier alignment
35. governance dashboard seed run-ledger summary/artifact validation path in `scripts/governance/build_runtime_truth_dashboard_seed.py`
36. workload-authority governance and start-path matrix gate test in `tests/application/test_control_plane_workload_authority_governance.py`
36. API run-ledger summary validation and nested run-detail run-ledger summary sanitization path in `orket/application/services/run_ledger_summary_projection.py` and `orket/interfaces/api.py`
37. API run-ledger artifact projection sanitization path in `orket/application/services/run_ledger_summary_projection.py` and `orket/interfaces/api.py`
38. direct review replay canonical bundle-path validation reuse in `orket/application/review/bundle_validation.py` and `orket/interfaces/orket_bundle_cli.py`
39. shared runtime run-ledger projection normalization plus fail-closed parity/read path in `orket/runtime/run_ledger_projection.py`, `orket/application/services/run_ledger_summary_projection.py`, `orket/runtime/run_ledger_parity.py`, and `orket/adapters/storage/async_repositories.py`
40. protocol/sqlite run-ledger parity-campaign invalid-projection detail preservation path in `orket/runtime/protocol_ledger_parity_campaign.py`
41. protocol rollout evidence markdown invalid-projection detail preservation path in `scripts/protocol/publish_protocol_rollout_artifacts.py`
42. protocol enforce-window signoff and capture-manifest invalid-projection detail preservation path in `scripts/protocol/record_protocol_enforce_window_signoff.py` and `scripts/protocol/run_protocol_enforce_window_capture.py`
43. protocol cutover-readiness invalid-projection detail preservation path in `scripts/protocol/check_protocol_enforce_cutover_readiness.py`
44. shared protocol invalid-projection detail normalization path in `scripts/protocol/parity_projection_support.py`
45. live-acceptance row payload validation and invalid-signal reporting path in `scripts/acceptance/report_live_acceptance_patterns.py`
46. shared live-acceptance report contract validation plus microservices unlock fail-closed path in `orket/application/services/microservices_acceptance_reports.py` and `scripts/acceptance/check_microservices_unlock.py`
47. monolith variant matrix invalid-signal preservation plus monolith readiness and matrix-stability fail-closed path in `scripts/acceptance/run_monolith_variant_matrix.py`, `scripts/acceptance/check_monolith_readiness_gate.py`, and `scripts/acceptance/check_microservices_unlock.py`
48. architecture pilot matrix comparison invalid-signal preservation plus shared comparison-validation and microservices pilot stability fail-closed path in `scripts/acceptance/run_architecture_pilot_matrix.py`, `scripts/acceptance/check_microservices_pilot_stability.py`, and `orket/application/services/microservices_acceptance_reports.py`
49. runtime-policy pilot-stability report validation path in `orket/application/services/runtime_policy.py`
50. microservices pilot decision unlock-report validation path in `scripts/acceptance/decide_microservices_pilot.py`
51. shared microservices acceptance-report normalization plus runtime-policy unlock-report validation path in `orket/application/services/microservices_acceptance_reports.py`, `orket/application/services/runtime_policy.py`, and `scripts/acceptance/decide_microservices_pilot.py`
52. shared microservices acceptance-report internal-consistency validation plus runtime-policy pilot-stability hardening path in `orket/application/services/microservices_acceptance_reports.py` and `orket/application/services/runtime_policy.py`
53. shared microservices acceptance-report internal-consistency validation plus runtime-policy and pilot-decision unlock-report hardening path in `orket/application/services/microservices_acceptance_reports.py`
54. catalog-resolved workload publication paths in `orket/application/services/kernel_action_control_plane_service.py`, `orket/application/services/review_run_control_plane_service.py`, `orket/application/services/turn_tool_control_plane_service.py`, `orket/application/services/orchestrator_issue_control_plane_service.py`, `orket/application/services/orchestrator_scheduler_control_plane_service.py`, `orket/application/services/orchestrator_scheduler_control_plane_mutation.py`, and `orket/application/services/gitea_state_control_plane_execution_service.py`
55. explicit atomic-issue runtime entrypoint routing in `orket/runtime/execution_pipeline.py`, `orket/orchestration/engine.py`, `orket/organization_loop.py`, and `orket/adapters/vcs/gitea_webhook_handlers.py`
56. interaction-session extension workload validation path in `orket/interfaces/routers/sessions.py`

Representative tests changed or added:
1. `tests/core/test_workload_contract_models.py`
2. `tests/runtime/test_cards_workload_adapter.py`
3. `tests/runtime/test_extension_components.py`
4. `tests/runtime/test_extension_manager.py`
5. `tests/application/test_control_plane_workload_catalog.py`
6. `tests/application/test_execution_pipeline_workload_shell.py`
7. `tests/application/test_execution_pipeline_cards_epic_control_plane.py`
8. `tests/application/test_review_run_service.py`
9. `tests/integration/test_review_run_live_paths.py`
10. `tests/interfaces/test_review_cli.py`
11. existing integration coverage for turn executor, Gitea worker, orchestrator issue, orchestrator scheduler, and sandbox lifecycle paths
12. `tests/interfaces/test_api_kernel_lifecycle.py`
13. `tests/interfaces/test_api_kernel_lifecycle_control_plane_refs.py`
14. `tests/application/test_orchestration_engine_kernel_async.py`
15. `tests/application/test_turn_artifact_writer.py`
16. `tests/application/test_async_protocol_run_ledger.py`
17. `tests/runtime/test_protocol_receipt_materializer.py`
18. `tests/integration/test_turn_executor_control_plane.py`
19. `tests/runtime/test_run_graph_reconstruction.py`
20. `tests/runtime/test_run_summary_artifact_provenance.py`
21. `tests/runtime/test_run_summary_packet2.py`
22. `tests/application/test_execution_pipeline_run_ledger.py`
23. `tests/runtime/test_run_summary_packet1.py`
24. `tests/application/test_review_run_service.py`
25. `tests/interfaces/test_review_cli.py`
26. `tests/runtime/test_run_summary.py`
27. `tests/runtime/test_run_summary_projection_validation.py`
28. `tests/application/test_reviewrun_answer_key_scoring.py`
29. `tests/application/test_reviewrun_consistency.py`
30. `tests/application/test_review_run_result_contract.py`
31. `tests/runtime/test_run_identity_projection.py`
32. `tests/application/test_code_review_probe.py`
33. `tests/scripts/test_audit_phase2.py`
34. `tests/scripts/test_run_summary_projection_consumers.py`
35. `tests/application/test_review_bundle_validation.py`
36. `tests/scripts/test_common_run_summary_support.py`
37. `tests/scripts/test_check_retry_classification_policy.py`
38. `tests/scripts/test_run_runtime_truth_acceptance_gate.py`
39. `tests/scripts/test_build_runtime_truth_dashboard_seed.py`
40. `tests/application/test_reviewrun_consistency.py`
41. `tests/interfaces/test_api.py`
42. `tests/interfaces/test_review_cli.py`
43. `tests/runtime/test_run_ledger_parity.py`
44. `tests/scripts/test_compare_run_ledger_backends.py`
45. `tests/runtime/test_protocol_ledger_parity_campaign.py`
46. `tests/interfaces/test_cli_protocol_parity_campaign.py`
47. `tests/interfaces/test_sessions_router_protocol_replay.py`
48. `tests/scripts/test_run_protocol_ledger_parity_campaign.py`
49. `tests/scripts/test_publish_protocol_rollout_artifacts.py`
50. `tests/scripts/test_record_protocol_enforce_window_signoff.py`
51. `tests/scripts/test_run_protocol_enforce_window_capture.py`
52. `tests/scripts/test_check_protocol_enforce_cutover_readiness.py`
53. `tests/scripts/test_protocol_parity_projection_support.py`
54. `tests/application/test_live_acceptance_reporting.py`
55. `tests/application/test_microservices_unlock_gate.py`
56. `tests/application/test_monolith_matrix_and_gate.py`
57. `tests/application/test_architecture_pilot_matrix_script.py`
58. `tests/application/test_microservices_pilot_stability.py`
59. `tests/application/test_microservices_pilot_decision.py`
60. `tests/application/test_microservices_acceptance_reports.py`
61. `tests/interfaces/test_api.py`
62. `tests/application/test_orchestrator_issue_control_plane_service.py`
63. `tests/application/test_orchestrator_scheduler_control_plane_service.py`
64. `tests/application/test_orchestrator_scheduler_control_plane_mutation_guards.py`
65. `tests/application/test_execution_pipeline_issue_entrypoints.py`
66. `tests/application/test_engine_refactor.py`
67. `tests/application/test_organization_loop.py`
68. `tests/adapters/test_gitea_webhook.py`
69. `tests/application/test_control_plane_workload_authority_governance.py`
70. `tests/application/test_execution_pipeline_gitea_state_loop.py`
71. `tests/interfaces/test_sessions_router_protocol_replay.py`

Docs changed:
1. `docs/specs/WORKLOAD_CONTRACT_V1.md`
2. `docs/specs/REVIEW_RUN_V0.md`
3. `docs/guides/REVIEW_RUN_CLI.md`
4. `docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`
5. `CURRENT_AUTHORITY.md`
6. `docs/specs/TRUTHFUL_RUNTIME_ARTIFACT_PROVENANCE_CONTRACT.md`
7. `docs/specs/TRUTHFUL_RUNTIME_SOURCE_ATTRIBUTION_CONTRACT.md`
8. `docs/specs/TRUTHFUL_RUNTIME_NARRATION_EFFECT_AUDIT_CONTRACT.md`
9. `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
10. `docs/architecture/CONTRACT_DELTA_REVIEW_RUN_CONTROL_PLANE_IDENTITY_2026-03-28.md`
11. `docs/architecture/CONTRACT_DELTA_REVIEW_RUN_BUNDLE_IDENTITY_2026-03-28.md`
12. `docs/architecture/CONTRACT_DELTA_RETRY_POLICY_REPORT_SNAPSHOT_VALIDATION_2026-03-29.md`
13. `docs/architecture/CONTRACT_DELTA_REVIEWRUN_CONSISTENCY_REPORT_VALIDATION_2026-03-29.md`
14. `docs/architecture/CONTRACT_DELTA_REVIEWRUN_ANSWER_KEY_SCORE_REPORT_2026-03-29.md`
15. `docs/architecture/CONTRACT_DELTA_RUN_SUMMARY_CONTROL_PLANE_ATTEMPT_IDENTITY_2026-03-28.md`
16. `docs/specs/PROTOCOL_LEDGER_PARITY_CAMPAIGN_SCHEMA.md`
17. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`
18. `docs/projects/ControlPlane/CONTROL_PLANE_CONVERGENCE_WORKSTREAM_1_CLOSEOUT.md`

## Proof executed

Proof type: `structural`
Observed result: `success`

Commands executed for the slices recorded here:
1. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/core/test_workload_contract_models.py tests/runtime/test_cards_workload_adapter.py tests/application/test_execution_pipeline_workload_shell.py tests/application/test_run_arbiter_workload_contract.py tests/runtime/test_extension_components.py tests/runtime/test_extension_manager.py`
   Result: `46 passed`
2. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_control_plane_workload_catalog.py tests/application/test_kernel_action_control_plane_service.py tests/application/test_orchestrator_issue_control_plane_service.py tests/application/test_orchestrator_scheduler_control_plane_service.py tests/integration/test_turn_executor_control_plane.py tests/integration/test_gitea_state_worker_control_plane.py`
   Result: `41 passed`
3. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_control_plane_workload_catalog.py tests/application/test_sandbox_control_plane_execution_service.py tests/application/test_sandbox_control_plane_effect_service.py tests/integration/test_sandbox_lifecycle_reconciliation_service.py tests/integration/test_sandbox_orchestrator_lifecycle.py`
   Result: `22 passed`
4. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_execution_pipeline_cards_epic_control_plane.py tests/application/test_execution_pipeline_workload_shell.py tests/application/test_execution_pipeline_session_status.py`
   Result: `8 passed`
5. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_execution_pipeline_run_ledger.py -k "runtime_contract_bootstrap_artifacts or keeps_run_identity_immutable"`
   Result: `2 passed, 12 deselected`
6. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_review_run_service.py tests/integration/test_review_run_live_paths.py tests/interfaces/test_review_cli.py tests/application/test_control_plane_workload_catalog.py`
   Result: `14 passed`
7. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_summary.py tests/application/test_execution_pipeline_cards_epic_control_plane.py tests/application/test_execution_pipeline_run_ledger.py -k "control_plane or summary or incomplete or failed or terminal_failure or runtime_contract_bootstrap_artifacts or keeps_run_identity_immutable"`
   Result: `14 passed, 8 deselected`
8. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
9. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_start_artifacts.py tests/application/test_execution_pipeline_run_ledger.py -k "run_identity or runtime_contract_bootstrap_artifacts or keeps_run_identity_immutable"`
   Result: `4 passed, 38 deselected`
10. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_summary.py tests/runtime/test_run_start_artifacts.py tests/application/test_execution_pipeline_cards_epic_control_plane.py tests/application/test_execution_pipeline_run_ledger.py -k "control_plane or summary or run_identity or incomplete or failed or terminal_failure or runtime_contract_bootstrap_artifacts or keeps_run_identity_immutable"`
    Result: `16 passed, 34 deselected`
11. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_retry_classification_policy.py tests/runtime/test_run_start_artifacts.py tests/application/test_execution_pipeline_run_ledger.py -k "retry_classification_policy or run_identity or runtime_contract_bootstrap_artifacts"`
    Result: `8 passed, 38 deselected`
12. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_review_run_service.py tests/integration/test_review_run_live_paths.py tests/interfaces/test_review_cli.py`
    Result: `13 passed`
13. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_kernel_action_control_plane_view_service.py tests/interfaces/test_api_kernel_lifecycle.py tests/interfaces/test_api_kernel_lifecycle_control_plane_refs.py tests/application/test_orchestration_engine_kernel_async.py`
    Result: `34 passed`
14. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_graph_reconstruction.py tests/application/test_turn_artifact_writer.py tests/application/test_async_protocol_run_ledger.py tests/runtime/test_protocol_receipt_materializer.py tests/integration/test_turn_executor_control_plane.py tests/application/test_kernel_action_control_plane_view_service.py tests/interfaces/test_api_kernel_lifecycle.py tests/interfaces/test_api_kernel_lifecycle_control_plane_refs.py tests/application/test_orchestration_engine_kernel_async.py`
    Result: `81 passed`
15. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_summary_artifact_provenance.py tests/runtime/test_run_summary_packet2.py tests/application/test_execution_pipeline_run_ledger.py -k "artifact_provenance or source_attribution or narration_to_effect_audit or idempotency"`
    Result: `8 passed, 16 deselected`
16. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_summary.py -k "control_plane_projection or control_plane_reconstruction"`
    Result: `2 passed, 4 deselected`
17. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_summary_packet1.py -k "provenance_preserves_control_plane_refs or reconstruction_matches_emitted_summary"`
    Result: `2 passed, 12 deselected`
18. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_summary_packet2.py -k "phase_c_contract_allows_non_repair_sections or source_attribution_preserves_control_plane_refs or reconstruction_matches_emitted_summary_for_phase_c_sections"`
   Result: `3 passed, 3 deselected`
19. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_summary.py tests/runtime/test_run_summary_projection_validation.py -k "control_plane_projection or control_plane_reconstruction or control_plane_projection_source_invalid or control_plane_projection_only_invalid"`
   Result: `4 passed, 10 deselected`
20. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_review_run_service.py tests/interfaces/test_review_cli.py tests/integration/test_review_run_live_paths.py -k "control_plane or projection"`
   Result: `3 passed, 11 deselected`
21. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_review_run_service.py -k "execution_state_authority or authoritative or control_plane"`
   Result: `6 passed, 4 deselected`
22. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_review_cli.py -k "replay or control_plane"`
   Result: `4 passed, 2 deselected`
23. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_reviewrun_answer_key_scoring.py`
   Result: `4 passed`
24. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_reviewrun_consistency.py`
   Result: `2 passed`
25. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_review_run_result_contract.py`
   Result: `1 passed`
26. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_identity_projection.py tests/runtime/test_run_start_artifacts.py tests/runtime/test_run_summary.py tests/runtime/test_run_summary_packet1.py tests/runtime/test_run_summary_packet2.py tests/runtime/test_run_summary_artifact_provenance.py tests/runtime/test_run_summary_projection_validation.py tests/application/test_execution_pipeline_run_ledger.py -k "run_identity or summary or packet1 or packet2 or artifact_provenance or projection"`
   Result: `50 passed, 34 deselected`
27. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_code_review_probe.py`
   Result: `8 passed`
28. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_audit_phase2.py tests/scripts/test_run_summary_projection_consumers.py`
   Result: `11 passed`
29. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_reviewrun_consistency.py`
   Result: `8 passed`
30. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_common_run_summary_support.py tests/scripts/test_run_summary_projection_consumers.py tests/scripts/test_truthful_runtime_live_proof_summary_validation.py tests/live/test_run_summary_support.py`
   Result: `9 passed`
31. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_reviewrun_consistency.py tests/interfaces/test_review_cli.py tests/application/test_code_review_probe.py`
   Result: `24 passed`
32. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_build_runtime_truth_dashboard_seed.py`
   Result: `4 passed`
33. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_reviewrun_consistency.py`
   Result: `4 passed`
34. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_api.py -k "run_detail_and_session_status"`
   Result: `2 passed, 94 deselected`
35. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_api.py -k "run_detail_and_session_status"`
   Result: `3 passed, 94 deselected`
36. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_build_runtime_truth_dashboard_seed.py tests/interfaces/test_api.py -k "build_runtime_truth_dashboard_seed or run_detail_and_session_status"`
   Result: `8 passed, 94 deselected`
37. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_review_cli.py -k "replay"`
   Result: `5 passed, 3 deselected`
38. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_ledger_parity.py tests/scripts/test_compare_run_ledger_backends.py tests/scripts/test_build_runtime_truth_dashboard_seed.py tests/interfaces/test_api.py -k "run_ledger_parity or compare_run_ledger_backends or build_runtime_truth_dashboard_seed or run_detail_and_session_status"`
   Result: `21 passed, 94 deselected`
39. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_protocol_ledger_parity_campaign.py tests/interfaces/test_cli_protocol_parity_campaign.py tests/interfaces/test_sessions_router_protocol_replay.py -k "ledger_parity_campaign"`
   Result: `9 passed, 18 deselected`
40. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_run_protocol_ledger_parity_campaign.py tests/scripts/test_publish_protocol_rollout_artifacts.py`
   Result: `7 passed`
41. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_record_protocol_enforce_window_signoff.py tests/scripts/test_run_protocol_enforce_window_capture.py`
   Result: `8 passed`
42. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_record_protocol_enforce_window_signoff.py tests/scripts/test_run_protocol_enforce_window_capture.py tests/scripts/test_check_protocol_enforce_cutover_readiness.py`
   Result: `12 passed`
43. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_protocol_parity_projection_support.py tests/scripts/test_publish_protocol_rollout_artifacts.py tests/scripts/test_record_protocol_enforce_window_signoff.py tests/scripts/test_check_protocol_enforce_cutover_readiness.py`
   Result: `12 passed`
44. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_live_acceptance_reporting.py tests/application/test_microservices_unlock_evidence_script.py`
   Result: `12 passed`
45. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_microservices_unlock_gate.py tests/application/test_live_acceptance_reporting.py tests/application/test_microservices_unlock_evidence_script.py`
   Result: `17 passed`
46. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_monolith_matrix_and_gate.py tests/application/test_microservices_unlock_gate.py tests/application/test_microservices_unlock_evidence_script.py`
   Result: `18 passed`
47. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_architecture_pilot_matrix_script.py tests/application/test_microservices_pilot_stability.py tests/application/test_microservices_pilot_decision.py`
   Result: `13 passed`
48. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_api.py -k "runtime_policy"`
   Result: `6 passed, 92 deselected`
49. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_microservices_pilot_decision.py tests/application/test_microservices_unlock_evidence_script.py tests/application/test_microservices_unlock_gate.py`
   Result: `12 passed`
50. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_api.py -k "runtime_policy"`
   Result: `8 passed, 92 deselected`
51. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_microservices_pilot_decision.py`
   Result: `4 passed`
52. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_microservices_acceptance_reports.py tests/interfaces/test_api.py -k "runtime_policy or pilot_stability_report or microservices_acceptance_reports"`
   Result: `11 passed, 92 deselected`
53. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_microservices_acceptance_reports.py tests/application/test_microservices_pilot_decision.py tests/interfaces/test_api.py -k "unlock_report or microservices_acceptance_reports or runtime_policy"`
   Result: `16 passed, 94 deselected`
54. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_microservices_acceptance_reports.py tests/application/test_architecture_pilot_matrix_script.py tests/application/test_microservices_pilot_stability.py`
   Result: `18 passed`
55. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_microservices_acceptance_reports.py tests/application/test_microservices_unlock_gate.py`
   Result: `16 passed`
56. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_microservices_pilot_decision.py tests/interfaces/test_api.py -k "runtime_policy or unlock_report or microservices_acceptance_reports"`
   Result: `12 passed, 94 deselected`
57. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_control_plane_authority_service.py tests/integration/test_turn_executor_control_plane.py tests/integration/test_async_control_plane_execution_repository.py tests/runtime/test_run_summary_projection_validation.py tests/scripts/test_common_run_summary_support.py`
   Result: `34 passed`
58. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_control_plane_authority_service.py tests/integration/test_turn_executor_control_plane.py tests/integration/test_async_control_plane_execution_repository.py tests/runtime/test_run_summary.py tests/runtime/test_run_summary_projection_validation.py tests/scripts/test_common_run_summary_support.py`
   Result: `42 passed`
59. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_summary_packet1.py tests/runtime/test_run_summary_packet2.py tests/runtime/test_run_summary_artifact_provenance.py`
   Result: `23 passed`
60. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_execution_pipeline_run_ledger.py -k "summary_fallback or invalid_run_identity_finalize or run_identity_immutable or contract_bootstrap"`
   Result: `2 passed, 14 deselected`
61. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_review_run_service.py tests/application/test_review_run_result_contract.py tests/integration/test_review_run_live_paths.py tests/interfaces/test_review_cli.py`
   Result: `25 passed`
62. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_reviewrun_consistency.py`
   Result: `15 passed`
63. `python -m pytest -q tests/application/test_review_bundle_validation.py -k "identifier_drift or authority_checked_payloads"`
   Result: `2 passed, 3 deselected`
64. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_reviewrun_consistency.py tests/application/test_code_review_probe.py`
   Result: `25 passed`
65. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
66. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_reviewrun_consistency.py tests/interfaces/test_review_cli.py`
   Result: `28 passed`
67. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_review_run_service.py tests/application/test_review_run_result_contract.py tests/integration/test_review_run_live_paths.py tests/interfaces/test_review_cli.py`
   Result: `28 passed`
68. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/runtime/test_run_summary.py tests/runtime/test_run_summary_projection_validation.py tests/scripts/test_common_run_summary_support.py`
   Result: `27 passed`
69. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_execution_pipeline_run_ledger.py -k "summary_fallback or invalid_run_identity_finalize or invalid_control_plane_finalize or run_identity_immutable or contract_bootstrap or attempt_alignment"`
   Result: `3 passed, 14 deselected`
70. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
71. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/runtime/test_run_summary_projection_validation.py tests/application/test_execution_pipeline_run_ledger.py -k "attempt_lineage or attempt_alignment or invalid_control_plane_finalize or current_attempt_id_mismatch"`
   Result: `4 passed, 32 deselected`
72. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/runtime/test_run_summary.py tests/runtime/test_run_summary_projection_validation.py tests/scripts/test_common_run_summary_support.py`
   Result: `29 passed`
73. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_execution_pipeline_run_ledger.py -k "summary_fallback or invalid_run_identity_finalize or invalid_control_plane_finalize or run_identity_immutable or contract_bootstrap or attempt_alignment or attempt_lineage"`
   Result: `4 passed, 14 deselected`
74. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
75. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/runtime/test_run_summary_projection_validation.py tests/application/test_execution_pipeline_run_ledger.py -k "step_lineage or attempt_lineage or attempt_alignment or invalid_control_plane_finalize or current_attempt_id_mismatch"`
   Result: `5 passed, 34 deselected`
76. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/runtime/test_run_summary.py tests/runtime/test_run_summary_projection_validation.py tests/scripts/test_common_run_summary_support.py`
   Result: `31 passed`
77. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_execution_pipeline_run_ledger.py -k "summary_fallback or invalid_run_identity_finalize or invalid_control_plane_finalize or run_identity_immutable or contract_bootstrap or attempt_alignment or attempt_lineage or step_lineage"`
   Result: `5 passed, 14 deselected`
78. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
79. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/runtime/test_run_summary_projection_validation.py tests/application/test_execution_pipeline_run_ledger.py -k "run_projection or step_lineage or attempt_lineage or attempt_alignment or invalid_control_plane_finalize or current_attempt_id_mismatch"`
   Result: `8 passed, 34 deselected`
80. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/runtime/test_run_summary.py tests/runtime/test_run_summary_projection_validation.py tests/scripts/test_common_run_summary_support.py`
   Result: `33 passed`
81. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_execution_pipeline_run_ledger.py -k "summary_fallback or invalid_run_identity_finalize or invalid_control_plane_finalize or run_identity_immutable or contract_bootstrap or attempt_alignment or attempt_lineage or step_lineage or run_projection"`
   Result: `6 passed, 14 deselected`
82. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
83. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
84. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_review_run_service.py tests/application/test_review_run_result_contract.py tests/integration/test_review_run_live_paths.py tests/interfaces/test_review_cli.py`
   Result: `32 passed`
85. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_reviewrun_consistency.py tests/application/test_code_review_probe.py`
   Result: `28 passed`
86. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
87. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/runtime/test_run_summary_projection_validation.py tests/application/test_execution_pipeline_run_ledger.py -k "attempt_ordinal or attempt_state_required or step_kind_required or run_projection or step_lineage or attempt_lineage or attempt_alignment or invalid_control_plane_finalize or current_attempt_id_mismatch"`
   Result: `17 passed, 34 deselected`
88. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_review_run_service.py tests/application/test_review_run_result_contract.py tests/integration/test_review_run_live_paths.py tests/interfaces/test_review_cli.py`
   Result: `34 passed`
89. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/runtime/test_run_summary.py tests/runtime/test_run_summary_projection_validation.py tests/scripts/test_common_run_summary_support.py`
   Result: `39 passed`
90. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_execution_pipeline_run_ledger.py -k "summary_fallback or invalid_run_identity_finalize or invalid_control_plane_finalize or run_identity_immutable or contract_bootstrap or attempt_alignment or attempt_lineage or step_lineage or run_projection or attempt_ordinal or step_kind_required"`
   Result: `8 passed, 15 deselected`
91. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
92. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/runtime/test_run_summary_projection_validation.py tests/application/test_execution_pipeline_run_ledger.py -k "identity_hierarchy or run_id_required or attempt_id_required or attempt_ordinal or step_kind_required or run_projection or step_lineage or attempt_lineage or attempt_alignment or invalid_control_plane_finalize or current_attempt_id_mismatch"`
   Result: `20 passed, 37 deselected`
93. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/runtime/test_run_summary.py tests/runtime/test_run_summary_projection_validation.py tests/scripts/test_common_run_summary_support.py`
   Result: `43 passed`
94. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_reviewrun_consistency.py`
   Result: `25 passed`
95. `python -m pytest -q tests/application/test_review_bundle_validation.py -k "orphaned"`
   Result: `4 passed, 7 deselected`
96. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_review_run_service.py tests/application/test_review_run_result_contract.py tests/interfaces/test_review_cli.py`
   Result: `36 passed`
97. `python -m pytest -q tests/application/test_review_run_result_contract.py -k "orphaned"`
   Result: `2 passed, 8 deselected`
98. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_review_run_service.py tests/application/test_review_run_result_contract.py tests/interfaces/test_review_cli.py tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_reviewrun_consistency.py`
   Result: `67 passed`
99. `python -m pytest -q tests/application/test_review_run_result_contract.py -k "manifest_control_plane"`
   Result: `3 passed, 9 deselected`
100. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_review_run_service.py tests/application/test_review_run_result_contract.py tests/interfaces/test_review_cli.py tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_reviewrun_consistency.py`
   Result: `74 passed`
101. `python -m pytest -q tests/application/test_review_bundle_validation.py -k "run_id_missing"`
   Result: `2 passed, 10 deselected`
102. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_review_run_service.py tests/application/test_review_run_result_contract.py tests/interfaces/test_review_cli.py tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_reviewrun_consistency.py`
   Result: `79 passed`
103. `python -m pytest -q tests/application/test_review_run_service.py tests/application/test_review_run_result_contract.py tests/application/test_review_bundle_validation.py -k "control_plane_run_id_mismatch or control_plane_run_id_drift"`
   Result: `5 passed, 47 deselected`
104. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_review_run_service.py tests/application/test_review_run_result_contract.py tests/integration/test_review_run_live_paths.py tests/interfaces/test_review_cli.py`
   Result: `65 passed`
105. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_reviewrun_consistency.py tests/application/test_code_review_probe.py`
   Result: `40 passed`
106. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_summary_projection_validation.py`
   Result: `34 passed`
107. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_execution_pipeline_run_ledger.py -k "current_attempt_outlives_attempt_projection or identity_hierarchy_drops_parent_refs or current_attempt_id_mismatch or attempt_lineage or step_lineage"`
   Result: `5 passed, 21 deselected`
108. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
109. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_run_summary_projection_validation.py tests/scripts/test_common_run_summary_support.py`
   Result: `44 passed`
110. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_execution_pipeline_run_ledger.py -k "orphaned_projection_metadata or current_attempt_outlives_attempt_projection or identity_hierarchy_drops_parent_refs or attempt_lineage or step_lineage"`
   Result: `8 passed, 21 deselected`
111. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
112. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_review_run_service.py tests/application/test_review_run_result_contract.py tests/interfaces/test_review_cli.py`
   Result: `69 passed`
113. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/integration/test_review_run_live_paths.py`
   Result: `3 passed`
114. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
115. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/runtime/test_retry_classification_policy.py tests/runtime/test_run_start_artifacts.py tests/runtime/test_run_start_retry_classification_policy_immutability.py tests/application/test_execution_pipeline_run_ledger.py -k "retry_classification_policy or runtime_contract_bootstrap_artifacts"`
   Result: `9 passed, 56 deselected`
116. `python -m pytest -q tests/scripts/test_check_retry_classification_policy.py tests/runtime/test_runtime_truth_drift_checker.py -k "retry_classification_policy"`
   Result: `3 passed, 15 deselected`
117. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
118. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/runtime/test_retry_classification_policy.py tests/runtime/test_run_start_artifacts.py tests/runtime/test_run_start_retry_classification_policy_immutability.py tests/application/test_execution_pipeline_run_ledger.py -k "retry_classification_policy or invalid_retry_projection or runtime_contract_bootstrap_artifacts"`
   Result: `10 passed, 56 deselected`
119. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
120. `python -m pytest -q tests/scripts/test_check_retry_classification_policy.py tests/scripts/test_run_runtime_truth_acceptance_gate.py -k "retry_policy"`
   Result: `2 passed, 55 deselected`
121. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
122. `python -m pytest -q tests/scripts/test_check_retry_classification_policy.py -k "report or main or diff_ledger"`
   Result: `5 passed, 1 deselected`
123. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
124. `python -m pytest -q tests/scripts/test_run_runtime_truth_acceptance_gate.py -k "retry_policy_artifact or valid_retry_artifact"`
   Result: `3 passed, 52 deselected`
125. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
126. `python -m pytest -q tests/runtime/test_retry_classification_policy.py tests/scripts/test_check_retry_classification_policy.py -k "retry_policy or report or main or diff_ledger or snapshot or empty_payload"`
   Result: `13 passed, 3 deselected`
127. `python -m pytest -q tests/scripts/test_run_runtime_truth_acceptance_gate.py -k "retry_policy_report or retry_policy_artifact or valid_retry_artifact or snapshot"`
   Result: `5 passed, 51 deselected`
128. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
129. `python -m pytest -q tests/scripts/test_run_runtime_truth_acceptance_gate.py -k "retry_policy_report or retry_policy_artifact or valid_retry_artifact or snapshot or preserves_valid_retry_policy_failure_detail"`
   Result: `6 passed, 51 deselected`
130. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
131. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_code_review_probe.py tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_reviewrun_consistency.py`
   Result: `43 passed`
132. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
133. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_reviewrun_consistency.py tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_code_review_probe.py`
   Result: `45 passed`
134. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
135. `python -m pytest -q tests/scripts/test_check_1000_consistency.py tests/application/test_reviewrun_consistency.py tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_code_review_probe.py`
   Result: `50 passed`
136. `python scripts/governance/check_docs_project_hygiene.py`
   Result: passed
137. `python -m pytest -q tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_code_review_probe.py tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_consistency.py`
    Result: `47 passed`
138. `python scripts/governance/check_docs_project_hygiene.py`
    Result: passed
139. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_reviewrun_consistency.py tests/scripts/test_check_1000_consistency.py tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_code_review_probe.py`
    Result: `54 passed`
140. `python scripts/governance/check_docs_project_hygiene.py`
    Result: passed
141. `python scripts/governance/check_docs_project_hygiene.py`
    Result: passed
142. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_code_review_probe.py tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_consistency.py`
    Result: `50 passed`
143. `python scripts/governance/check_docs_project_hygiene.py`
    Result: passed
144. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/scripts/test_check_1000_consistency.py tests/application/test_reviewrun_consistency.py tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_code_review_probe.py`
     Result: `58 passed`
145. `python scripts/governance/check_docs_project_hygiene.py`
     Result: passed
146. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/scripts/test_check_1000_consistency.py tests/application/test_reviewrun_consistency.py tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_code_review_probe.py`
     Result: `61 passed`
147. `python scripts/governance/check_docs_project_hygiene.py`
     Result: passed
148. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/scripts/test_check_1000_consistency.py tests/application/test_reviewrun_consistency.py tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_code_review_probe.py`
     Result: `64 passed`
149. `python scripts/governance/check_docs_project_hygiene.py`
     Result: passed
150. `python scripts/governance/check_docs_project_hygiene.py`
     Result: passed
151. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_code_review_probe.py tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_consistency.py`
     Result: `56 passed`
152. `python scripts/governance/check_docs_project_hygiene.py`
     Result: passed
153. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_code_review_probe.py`
     Result: `28 passed`
154. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_code_review_probe.py tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_consistency.py`
     Result: `58 passed`
155. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_code_review_probe.py`
     Result: `31 passed`
156. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_reviewrun_answer_key_scoring.py tests/application/test_code_review_probe.py tests/application/test_review_bundle_validation.py tests/application/test_reviewrun_consistency.py`
     Result: `61 passed`
157. `python -m pytest -q tests/application/test_control_plane_workload_catalog.py tests/application/test_control_plane_workload_authority_governance.py tests/application/test_run_arbiter_workload_contract.py tests/runtime/test_cards_workload_adapter.py tests/runtime/test_extension_components.py tests/runtime/test_extension_manager.py`
     Result: `51 passed`
158. `python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py tests/interfaces/test_cli_startup_semantics.py`
     Result: `9 passed`
159. `python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py tests/application/test_orchestrator_issue_control_plane_service.py tests/application/test_orchestrator_scheduler_control_plane_service.py tests/application/test_orchestrator_scheduler_control_plane_mutation_guards.py tests/application/test_kernel_action_control_plane_service.py tests/application/test_review_run_service.py tests/integration/test_turn_executor_control_plane.py tests/integration/test_gitea_state_worker_control_plane.py`
     Result: `85 passed`
160. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
161. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_execution_pipeline_issue_entrypoints.py tests/application/test_engine_refactor.py tests/application/test_organization_loop.py tests/adapters/test_gitea_webhook.py tests/application/test_control_plane_workload_authority_governance.py`
     Result: `27 passed`
162. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_execution_pipeline_gitea_state_loop.py tests/application/test_execution_pipeline_issue_entrypoints.py tests/application/test_engine_refactor.py tests/application/test_organization_loop.py tests/adapters/test_gitea_webhook.py tests/application/test_control_plane_workload_authority_governance.py`
     Result: `30 passed`
163. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
164. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_execution_pipeline_issue_entrypoints.py tests/application/test_execution_pipeline_gitea_state_loop.py tests/application/test_engine_refactor.py tests/application/test_organization_loop.py tests/adapters/test_gitea_webhook.py tests/application/test_control_plane_workload_authority_governance.py tests/interfaces/test_cli_startup_semantics.py`
     Result: `35 passed`
165. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
166. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py tests/application/test_execution_pipeline_issue_entrypoints.py tests/application/test_engine_refactor.py tests/application/test_execution_pipeline_gitea_state_loop.py tests/application/test_organization_loop.py tests/adapters/test_gitea_webhook.py tests/interfaces/test_cli_startup_semantics.py tests/runtime/test_extension_components.py tests/platform/test_runtime_shim_compat.py`
     Result: `52 passed`
167. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
168. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py tests/interfaces/test_cli_startup_semantics.py tests/runtime/test_extension_components.py tests/runtime/test_extension_import_guard.py tests/runtime/test_cards_workload_adapter.py tests/platform/test_runtime_shim_compat.py tests/application/test_execution_pipeline_issue_entrypoints.py tests/application/test_engine_refactor.py tests/application/test_execution_pipeline_gitea_state_loop.py tests/application/test_organization_loop.py tests/adapters/test_gitea_webhook.py tests/runtime/test_controller_dispatcher.py -k "not integration_runtime_path_and_determinism"`
     Result: `62 passed, 1 deselected`
169. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
170. `python -m pytest -q tests/core/test_workload_contract_models.py tests/application/test_control_plane_workload_authority_governance.py tests/runtime/test_extension_components.py tests/runtime/test_cards_workload_adapter.py`
     Result: `35 passed`
171. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
172. `python -m pytest -q tests/core/test_workload_contract_models.py tests/application/test_control_plane_workload_authority_governance.py tests/runtime/test_extension_components.py tests/runtime/test_cards_workload_adapter.py tests/platform/test_runtime_shim_compat.py`
     Result: `37 passed`
173. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
174. `python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py tests/runtime/test_extension_components.py tests/platform/test_runtime_shim_compat.py tests/core/test_workload_contract_models.py tests/runtime/test_cards_workload_adapter.py`
     Result: `38 passed`
175. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
176. `python -m pytest -q tests/application/test_control_plane_workload_catalog.py tests/application/test_control_plane_workload_authority_governance.py tests/runtime/test_extension_components.py tests/platform/test_runtime_shim_compat.py tests/core/test_workload_contract_models.py`
     Result: `41 passed`
177. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
178. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
179. `python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py tests/runtime/test_extension_components.py`
     Result: `29 passed`
180. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
181. `python -m pytest -q tests/platform/test_runtime_shim_compat.py tests/application/test_control_plane_workload_authority_governance.py`
     Result: `15 passed`
182. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
183. `python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py tests/runtime/test_extension_components.py`
     Result: `30 passed`
184. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
185. `python -m pytest -q tests/platform/test_runtime_shim_compat.py tests/application/test_control_plane_workload_authority_governance.py`
     Result: `16 passed`
186. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
187. `python -m pytest -q tests/platform/test_runtime_shim_compat.py tests/application/test_control_plane_workload_authority_governance.py`
     Result: `17 passed`
188. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
189. `python -m pytest -q tests/application/test_engine_refactor.py tests/application/test_control_plane_workload_authority_governance.py`
     Result: `21 passed`
190. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
191. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py tests/runtime/test_extension_components.py tests/runtime/test_extension_import_guard.py tests/runtime/test_controller_dispatcher.py tests/runtime/test_extension_manager.py`
     Result: `60 passed`
192. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
193. `python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py tests/application/test_decision_nodes_planner.py tests/application/test_decision_node_override_matrix.py tests/application/test_execution_pipeline_issue_entrypoints.py`
     Result: `69 passed`
194. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
195. `python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py tests/application/test_decision_nodes_planner.py tests/application/test_decision_node_override_matrix.py tests/application/test_execution_pipeline_issue_entrypoints.py`
     Result: `69 passed`
196. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
197. `python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py tests/runtime/test_extension_components.py tests/runtime/test_extension_import_guard.py tests/runtime/test_controller_dispatcher.py tests/runtime/test_extension_manager.py`
     Result: `62 passed in 15.66s`
198. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
199. `python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py tests/runtime/test_extension_components.py tests/runtime/test_extension_import_guard.py tests/runtime/test_controller_dispatcher.py tests/runtime/test_extension_manager.py`
     Result: `62 passed in 15.82s`
200. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
201. `python -m pytest -q tests/application/test_control_plane_workload_catalog.py tests/application/test_control_plane_workload_authority_governance.py tests/application/test_execution_pipeline_issue_entrypoints.py`
     Result: `29 passed in 6.21s`
202. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
203. `python -m pytest -q tests/application/test_control_plane_workload_catalog.py tests/application/test_control_plane_workload_authority_governance.py tests/runtime/test_extension_manager.py tests/runtime/test_extension_components.py`
     Result: `66 passed in 12.56s`
204. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
205. `python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py tests/application/test_control_plane_workload_catalog.py tests/application/test_decision_nodes_planner.py tests/application/test_decision_node_override_matrix.py`
     Result: `80 passed in 8.39s`
206. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
207. `python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py tests/runtime/test_extension_manager.py tests/runtime/test_extension_components.py tests/runtime/test_extension_import_guard.py tests/runtime/test_controller_dispatcher.py`
     Result: `67 passed in 17.69s`
208. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
209. `python -m pytest -q tests/application/test_control_plane_workload_catalog.py tests/application/test_control_plane_workload_authority_governance.py tests/application/test_run_arbiter_workload_contract.py`
     Result: `35 passed in 9.16s`
210. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
211. `python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py tests/runtime/test_extension_components.py tests/runtime/test_extension_manager.py tests/runtime/test_controller_dispatcher.py`
     Result: `67 passed in 18.15s`
212. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
213. `python -m pytest -q tests/interfaces/test_cli_startup_semantics.py tests/platform/test_current_authority_map.py`
     Result: `11 passed in 0.42s`
214. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
215. `python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py tests/runtime/test_extension_components.py tests/runtime/test_extension_manager.py tests/application/test_register_meta_breaker_extension.py tests/application/test_register_textmystery_bridge_extension.py tests/interfaces/test_cli_extensions.py`
     Result: `71 passed in 20.42s`
216. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
217. `python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py`
     Result: `27 passed in 12.24s`
218. `python scripts/governance/check_docs_project_hygiene.py`
     Result: `passed`
219. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/interfaces/test_api_interactions.py tests/interfaces/test_sessions_router_protocol_replay.py tests/application/test_control_plane_workload_authority_governance.py`
    Result: `56 passed in 14.65s`
220. `python scripts/governance/check_docs_project_hygiene.py`
    Result: `passed`
221. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/runtime/test_extension_components.py tests/application/test_control_plane_workload_authority_governance.py`
    Result: `48 passed in 14.23s`
222. `python scripts/governance/check_docs_project_hygiene.py`
    Result: `passed`
223. `python -m pytest -q tests/platform/test_current_authority_map.py`
    Result: `6 passed in 0.04s`
224. `python scripts/governance/check_docs_project_hygiene.py`
    Result: `passed`
225. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py`
    Result: `29 passed in 9.15s`
226. `python -m pytest -q tests/platform/test_current_authority_map.py`
    Result: `6 passed in 0.03s`
227. `python scripts/governance/check_docs_project_hygiene.py`
    Result: `passed`
228. `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/application/test_control_plane_workload_authority_governance.py`
    Result: `29 passed in 9.12s`
229. `python -m pytest -q tests/platform/test_current_authority_map.py`
    Result: `6 passed in 0.03s`
230. `python scripts/governance/check_docs_project_hygiene.py`
    Result: `passed`
231. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_execution_pipeline_issue_entrypoints.py tests/application/test_control_plane_workload_authority_governance.py tests/platform/test_current_authority_map.py`
    Result: `40 passed in 9.20s`
232. `python scripts/governance/check_docs_project_hygiene.py`
    Result: `passed`
233. `python scripts/governance/check_docs_project_hygiene.py`
    Result: `passed`
234. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q tests/application/test_engine_refactor.py tests/application/test_execution_pipeline_issue_entrypoints.py tests/application/test_execution_pipeline_gitea_state_loop.py tests/application/test_organization_loop.py tests/adapters/test_gitea_webhook.py tests/application/test_control_plane_workload_authority_governance.py tests/interfaces/test_cli_startup_semantics.py tests/platform/test_current_authority_map.py`
    Result: `68 passed in 12.26s`
235. `python scripts/governance/check_docs_project_hygiene.py`
    Result: `passed`
236. `python scripts/governance/check_docs_project_hygiene.py`
    Result: `passed`
237. `python scripts/governance/check_docs_project_hygiene.py`
    Result: `passed`
238. `$env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q -rs`
    Result: `3577 passed, 37 skipped in 323.86s`
239. `$env:ORKET_RUN_SANDBOX_ACCEPTANCE='1'; Remove-Item Env:ORKET_DISABLE_SANDBOX -ErrorAction SilentlyContinue; python -m pytest -q -rs tests/acceptance/test_sandbox_cleanup_leak_gate.py tests/acceptance/test_sandbox_orchestrator_live_docker.py tests/acceptance/test_sandbox_orphan_reconciliation_live_docker.py tests/acceptance/test_sandbox_restart_reclaim_live_docker.py tests/acceptance/test_sandbox_runtime_recovery_live_docker.py tests/acceptance/test_sandbox_terminal_evidence_cleanup_live_docker.py`
    Result: `11 passed in 26.90s`
240. `$env:ORKET_LIVE_ACCEPTANCE='1'; $env:ORKET_LIVE_ROLE_TESTS='1'; $env:ORKET_DISABLE_SANDBOX='1'; python -m pytest -q -rs tests/live/test_auditability_phase2_live.py tests/live/test_companion_voice_truth_live.py tests/live/test_model_stream_v1_live.py tests/live/test_role_unit_live.py tests/live/test_runtime_stability_closeout_live.py tests/live/test_system_acceptance_pipeline.py tests/live/test_truthful_runtime_artifact_provenance_live.py tests/live/test_truthful_runtime_packet1_live.py tests/live/test_truthful_runtime_phase_c_completion_live.py tests/live/test_truthful_runtime_phase_d_completion_live.py tests/live/test_truthful_runtime_phase_e_completion_live.py`
    Result: `28 passed, 2 warnings in 183.13s`
241. `$env:ORKET_LIVE_ACCEPTANCE='1'; $env:ORKET_LIVE_ROLE_TESTS='1'; $env:ORKET_RUN_SANDBOX_ACCEPTANCE='1'; Remove-Item Env:ORKET_DISABLE_SANDBOX -ErrorAction SilentlyContinue; python -m pytest -q -rs`
    Result: `3614 passed, 2 warnings in 462.06s`

## Compatibility exits

Workstream 1 compatibility exits affected by the slices recorded here:
1. `CE-01` narrowed, not closed
   Reason: a canonical projection family and shared governed workload catalog now exist, cards start-path builders plus the touched extension-manifest workload projection now route through that shared catalog, the cards runtime path now resolves its `WorkloadRecord` through the catalog-local helper `_resolve_cards_control_plane_workload_from_contract(...)` instead of assembling `WorkloadAuthorityInput(...)` directly inside `ExecutionPipeline`, the ODR arbiter path now resolves its `WorkloadRecord` through the catalog-local helper `_resolve_odr_arbiter_control_plane_workload_from_contract(...)` instead of assembling `WorkloadAuthorityInput(...)` directly inside `scripts/odr/run_arbiter.py`, extension workload start now resolves its `WorkloadRecord` through the catalog-local helper `_resolve_extension_control_plane_workload(...)` instead of assembling `WorkloadAuthorityInput(...)` directly inside `ExtensionManager`, those private catalog-local helper names are no longer exported from the catalog `__all__` and are locked to their exact production owner paths, `run_card(...)` is again the sole public runtime execution surface with compatibility wrappers delegating back to it, the extension run-action adapter now treats `run_rock` only as explicit legacy alias normalization onto that canonical surface, active runtime callsites such as the legacy CLI `--rock` alias, runtime orchestration shims, touched probe/workload scripts, and live benchmark tooling now route directly through that canonical surface or the canonical `--card` CLI entrypoint, with the live benchmark runner no longer emitting rock-named runtime identifiers or `run_mode="rock"` in its own run metadata, the named runtime recommendation surface now points to `python main.py --card <card_id>`, touched catalog-resolved publishers now carry canonical `WorkloadRecord` objects through their publication helpers instead of restating workload identity as string-pair aliases, the former `orket/runtime/workload_adapters.py` shim is retired entirely, interaction-session extension workload validation now uses a validation-only `has_manifest_entry(...)` probe instead of a metadata-returning workload lookup surface, extension workload models now keep manifest metadata behind the private `_ExtensionManifestEntry` type with `ExtensionRecord` storing that metadata on `manifest_entries`, installed extension catalog persistence now writes `manifest_entries` and only compatibility-reads legacy persisted `workloads` rows while the external extension manifest contract still truthfully keeps its `workloads` array, the older private `_ExtensionManifestWorkload` noun, the public `ExtensionManifestWorkload` noun, the older `ExtensionWorkloadDescriptor` noun, the old `manifest_workloads` field, the old installed-catalog `workloads` field, and the old manifest `WorkloadRecord` alias retired from active extension surfaces, the former generic `ExtensionManager.resolve_workload(...)` surface retired in favor of a validation-only `has_manifest_entry(...)` probe plus the private manifest-entry lookup helper `_resolve_manifest_entry(...)`, the former public-looking `ExtensionCatalog.resolve_manifest_entry(...)` surface retired in favor of the private catalog helper `_resolve_manifest_entry(...)`, no outward `ExtensionManifestWorkload` re-export through `orket.extensions` or `orket.extensions.manager` `__all__` exports, production imports of the private `_ExtensionManifestEntry` type are now contained inside `orket/extensions/`, internal rock routing now flows through a generic epic-collection entry plus generic epic-collection runtime selectors instead of a rock-named helper seam, that generic entry now emits collection-shaped runtime payloads instead of returning a `rock` field, the default generic epic-collection build token no longer carries the older `rock-build-...` prefix, and the low-level builders are now private internals instead of public core-contract exports, but the `Workload` row remains `conflicting` because start-path authority is not yet universal.
2. `CE-02` narrowed, not closed
   Reason: manual review runs now publish first-class run, attempt, and step truth, fresh review manifests plus persisted review lane decision/critique artifacts now explicitly point execution-state authority at durable control-plane records while marking lane outputs non-authoritative for execution state and now fail closed if those review artifact markers drift, if manifest or lane-payload `run_id` is missing, if fresh manifest or lane-payload `control_plane_run_id` drifts from the same artifact `run_id`, if manifest or lane attempt or step refs drift outside the declared `control_plane_run_id` lineage, or if lower-level manifest or lane control-plane refs survive after parent run or attempt refs drop, the embedded review-result `manifest` surface now also validates those persisted execution-authority markers before leaving the process and fails closed if they drift, if its attempt or step refs drift outside the declared `control_plane_run_id` lineage, or if a returned `control_plane` projection still carries control-plane refs the embedded manifest has dropped, `orket review replay --run-dir`, direct `--snapshot` plus `--policy` replay when those files target canonical bundle artifacts from one review-run directory, the review answer-key scoring path, the review consistency-signature path, and the persisted `check_1000_consistency.py` validator now also validate those persisted review bundle authority markers plus required manifest and lane-payload `run_id` presence, required lane-payload `control_plane_*` refs when the manifest declares them, lower-level manifest or lane `control_plane_*` refs that survive after parent run or attempt refs drop, manifest or lane attempt or step refs that drift outside the declared `control_plane_run_id` lineage, and manifest-to-lane run/control-plane identifier alignment before treating bundle artifacts or report-backed review evidence as trustworthy and fail closed if those markers or refs drift, with replay, scoring, consistency, and persisted consistency-report validation now also consuming shared validated review-bundle payload or artifact loaders, including truncation-bounds snapshot inputs, instead of validating markers and then rereading lane JSON or replay inputs ad hoc, review answer-key scoring now also emits explicit `reviewrun_answer_key_score_v1` score reports with required top-level `run_id` plus fixture/snapshot/policy provenance fields, required nested deterministic/model-assisted score blocks whose aggregate totals plus reasoning/fix subtotals stay aligned with the per-issue rows they summarize through explicit model reasoning/fix weights, and required per-issue row shape, workload-side code-review probe score consumers now fail closed if that score-report contract drifts at the nested block, aggregate, issue-row, or top-level provenance level instead of trusting ad hoc dict shape, workload-side code-review probe bundles now emit the same non-authoritative execution-state markers plus a bundle manifest and aligned bundle-local `run_id` values on deterministic/model-assisted lane payloads and now fail closed before artifact write when that bundle-local `run_id` is empty instead of waiting for persisted bundle validation to catch the omission, the review consistency report producer now also fails closed before report serialization when default, strict, replay, or baseline `run_id` is empty instead of emitting a blank run-like field, and the persisted `check_1000_consistency.py` validator now also fails closed before trusting report JSON when `contract_version` drifts, when those default, strict, replay, or baseline report `run_id` values are empty, or when required nested baseline/default/strict/replay signature digests, deterministic finding-row code/severity/message/path/span/details shape, or scenario-local `truncation_check` snapshot digests, byte counts, or boolean flags drift instead of trusting shallow `ok` or counter fields alone, the review result and CLI paths now read durable control-plane refs plus lifecycle state from persisted records and now fail closed if that review-summary projection drifts away from explicit `control_plane_records` framing, if lower-level projected attempt or step refs survive after parent run or attempt refs drop, if projected `attempt_state` or `attempt_ordinal` survives after projected `attempt_id` drops, if projected `step_kind` survives after projected `step_id` drops, if projected attempt or step refs drift outside the projected run lineage, if its projected run/attempt/step ids drift from the enclosing review result run identity and manifest control-plane refs, if it keeps projected run/attempt/step ids while dropping projected run metadata, attempt state or ordinal, or step kind, or if the embedded manifest drops those returned control-plane refs, while diff/PR/files CLI commands surface that serialization failure as structured `E_REVIEW_RUN_FAILED` output instead of an uncaught exception, cards `run_summary.json` now projects durable cards-epic run or attempt or step state from persisted control-plane records and now fails closed if that `control_plane` block drifts away from explicit projection framing, if lower-level projected ids survive after dropping parent run or attempt ids, if it drops core run metadata while still carrying `run_id`, if projected attempt ids survive without attempt state or a positive attempt ordinal, if projected attempt state or ordinal survives after projected `attempt_id` drops, if projected `current_attempt_id` survives after projected `attempt_id` drops, if projected `current_attempt_id` drifts from projected `attempt_id` when both are present, if projected `attempt_id` drifts outside the projected run lineage, or if projected `step_id` drifts outside the projected run lineage or survives without `step_kind` or if projected `step_kind` survives after projected `step_id` drops, shared probe/workload helpers plus MAR audit completeness and compare surfaces, training-data extraction, governance dashboard seed metrics, live-acceptance pattern reporting, monolith variant matrix summaries, monolith readiness plus matrix-stability gates, architecture pilot matrix comparison, microservices pilot stability, runtime-policy pilot-stability reads, microservices pilot decision, microservices unlock gating, API run-detail/session-status surfaces, protocol/sqlite run-ledger parity consumers, protocol/sqlite parity-campaign reporting surfaces, protocol rollout evidence bundle summaries, protocol enforce-window signoff plus capture-manifest outputs, and protocol cutover-readiness outputs now also consume validated legacy run-summary or run-ledger projection evidence before trusting summary JSON, artifact JSON, persisted `metrics_json` or `db_summary_json` rows, rate-only matrix summaries, architecture delta summaries, bare pilot-stability flags, bare unlock flags, unlock eligibility, parity heuristics, campaign mismatch summaries, rollout-summary shorthand, signoff/manifest pass-fail summaries, or cutover-ready totals, with governance dashboard seed metrics now also sanitizing persisted `run_ledger.artifact_json` through the shared validated run-ledger projection seam, live-acceptance pattern reporting now recording explicit invalid-payload signals when malformed `metrics_json` or `db_summary_json` rows drift instead of flattening them into clean empty state, monolith variant matrix summaries now preserving those normalized live-report invalid-payload counts instead of dropping them, monolith readiness plus matrix-stability gates now failing closed when those matrix summary counts are missing, malformed, or non-zero instead of producing false-green matrix readiness from malformed live-report rows, architecture pilot matrix comparison now preserving side-specific invalid-payload totals and failures from the underlying pilot summaries instead of flattening malformed source-row drift back into plain architecture deltas, microservices pilot stability now failing closed when that comparison detail is missing, malformed, or non-zero instead of producing false-green pilot stability from malformed live-report rows, runtime-policy pilot-stability reads now failing closed when the persisted pilot-stability artifact is structurally malformed instead of trusting a bare `stable` flag, microservices pilot decision now failing closed when the persisted unlock artifact is structurally malformed instead of trusting a bare `unlocked` flag, microservices unlock gating now failing closed when the live report is missing or malformed on `run_count`, `session_status_counts`, `pattern_counters`, or `invalid_payload_signals`, or reports any non-zero invalid source-row counts instead of producing false-green unlock decisions, run detail also sanitizing the nested `run_ledger.summary_json` projection, both API surfaces now sanitizing persisted `run_ledger.artifact_json` through the same validated run-ledger record seam instead of leaking raw invalid summary or artifact payloads, parity now failing closed on malformed persisted summary or artifact projections instead of normalizing them away into false-green equality while the SQLite run-ledger adapter preserves malformed persisted payload text long enough for that detection to happen, parity-campaign rows plus campaign telemetry now preserving side-specific invalid projection-field detail instead of collapsing malformed persisted projection drift into generic mismatch counts, rollout evidence markdown now preserving those same invalid projection-field counts instead of reducing malformed parity drift back to generic mismatch totals, signoff plus capture-manifest outputs now preserving those same invalid projection-field counts instead of flattening malformed parity drift back to generic pass-fail summaries, cutover-readiness outputs now preserving those same invalid projection-field counts instead of flattening malformed parity drift back to generic ready or passing-window totals, and rollout/signoff/cutover now also consume one shared invalid-projection detail helper instead of carrying divergent local parsers, fresh `run_start_artifacts` now explicitly mark `run_identity` as session-bootstrap projection-only evidence, bootstrap reuse plus legacy run-summary builders, finalize helpers, reconstruction, validators, and loaders now also fail closed if that framing drifts or if `run_identity.run_id` mismatches the enclosing summary `run_id`, with finalize-time bootstrap validation now degrading cleanly instead of aborting closeout while excluding transient invalid bootstrap identity from degraded summary output, fresh retry-classification snapshots now explicitly declare `projection_only=true` with `projection_source=retry_classification_rules` plus `attempt_history_authoritative=false`, run-start contract capture now validates that framing before persisting `retry_classification_policy.json`, the retry-policy checker now normalizes malformed report payloads into fail-closed error reports before diff-ledger write, rejects invalid embedded retry-policy snapshots in both green and failure reports, falls back to the canonical retry-policy snapshot when malformed producer output omits or drifts that embedded snapshot, the runtime-truth acceptance gate now validates both the retry-policy report contract and the persisted run-level `retry_classification_policy.json` artifact against the current canonical snapshot before trusting top-level green signals while preserving explicit fail-closed error detail from validated retry-policy reports instead of collapsing them into generic false state, and cards summary projection validation now also rejects transient run-projection incompleteness, id-hierarchy incompleteness, current-attempt hierarchy incompleteness, orphaned attempt or step metadata, attempt-metadata incompleteness, attempt-alignment drift, attempt-lineage drift, step-metadata incompleteness, or step-lineage drift without rewriting the durable run, attempt, or step records. Broader `run_summary.py` closure projections, legacy retry or lane behavior, and broader observability surfaces still survive.

## Workload Authority Decision Lock

The slices recorded here now use this lock:
1. exactly one repo seam may mint governed `WorkloadRecord` objects for start paths: `orket/application/services/control_plane_workload_catalog.py`
2. all other workload surfaces may only provide raw input data, call that seam, or read/project an already-built canonical workload record
3. runtime-local adapters, extension models, and workload-specific entrypoints may not import or call low-level control-plane workload builders directly
4. the governed start-path matrix below is a closure gate, not passive inventory: any non-test module that directly consumes workload authority from `control_plane_workload_catalog.py` must appear there with a truthful classification, and rock wrappers must remain routing-only retirement debt rather than regaining standalone workload-authority status
5. touched catalog-resolved publishers may not reintroduce local `workload_id` / `workload_version` authority aliases after receiving canonical `WorkloadRecord` objects from the shared catalog
6. `run_card(...)` is the sole public runtime execution surface, so `run_issue(...)`, `run_epic(...)`, and `run_rock(...)` may survive only as thin compatibility wrappers that normalize inputs and delegate back to it, while rock execution may remain only as routing-only retirement debt rather than a standalone workload-authority surface

## Governed Start-Path Matrix

The current workload-authority matrix for governed start paths is:

This matrix is now machine-enforced by `tests/application/test_control_plane_workload_authority_governance.py`. That governance test fails if a non-test module directly consumes workload authority from `control_plane_workload_catalog.py` without explicit matrix coverage, if touched catalog-resolved publishers reintroduce local `workload_id` / `workload_version` authority aliases, if the retired workload-adapter shim reappears or non-test repo code imports it, if non-test repo code imports the retired extension manifest alias, if non-CLI runtime callsites drift back onto `run_epic(...)`, `run_issue(...)`, or `run_rock(...)` compatibility wrappers, if public runtime wrappers stop collapsing back to `run_card(...)`, if the extension run-action adapter drifts back to treating `run_rock` as part of its primary run-op set instead of explicit legacy alias normalization, if the canonical `run_card(...)` dispatcher starts minting workload authority directly instead of routing into internal entrypoints, if the interaction sessions router drifts back to a metadata-returning extension workload lookup instead of the validation-only `has_manifest_entry(...)` probe, if live benchmark tooling drifts back onto the legacy `--rock` CLI alias, back to rock-named runtime identifiers or `run_mode="rock"` in benchmark run metadata, or back to default `live-rock` execution-mode metadata, or if rock routing regains standalone workload-authority status.

| Start path | Current authority status | Truthful note |
| --- | --- | --- |
| cards epic execution | `projection-resolved` | `run_card(...)` is now the canonical public runtime surface, and its normalized dispatcher still resolves cards-epic `workload.contract.v1` payloads plus `WorkloadRecord` projection through `control_plane_workload_catalog.py`. |
| atomic issue execution | `projection-resolved` | `run_card(...)` is now the canonical public runtime surface for issue execution too; its normalized dispatcher resolves issue cards onto the cards-epic path and `ExecutionPipeline._run_issue_entry(...)` routes those starts through `_run_epic_entry(..., target_issue_id=...)`, so the cards workload projection still resolves through `control_plane_workload_catalog.py`. |
| ODR / run arbiter | `projection-resolved` | `scripts/odr/run_arbiter.py` now emits raw `workload.contract.v1` payload and resolves its `WorkloadRecord` through the catalog-local helper `_resolve_odr_arbiter_control_plane_workload_from_contract(...)`. |
| manual review-run | `catalog-resolved` | `ReviewRunControlPlaneService` consumes `REVIEW_RUN_WORKLOAD` from the shared catalog and now carries that canonical `WorkloadRecord` directly into run publication instead of restating workload string pairs. |
| sandbox runtime | `catalog-resolved` | sandbox start paths consume `sandbox_runtime_workload_for_tech_stack(...)` from the shared catalog. |
| kernel action | `catalog-resolved` | `KernelActionControlPlaneService` consumes `KERNEL_ACTION_WORKLOAD` and now carries that canonical `WorkloadRecord` directly into run publication instead of restating workload string pairs. |
| governed turn-tool | `catalog-resolved` | `TurnToolControlPlaneService` consumes `TURN_TOOL_WORKLOAD` and now carries that canonical `WorkloadRecord` directly into run publication instead of restating workload string pairs. |
| orchestrator issue dispatch | `catalog-resolved` | `OrchestratorIssueControlPlaneService` consumes `ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD` and now carries that canonical `WorkloadRecord` directly into run publication instead of restating workload string pairs. |
| orchestrator scheduler mutation | `catalog-resolved` | `OrchestratorSchedulerControlPlaneService` consumes `ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD` and now carries that canonical `WorkloadRecord` through namespace-mutation helpers instead of restating workload string pairs. |
| orchestrator child workload composition | `catalog-resolved` | `OrchestratorSchedulerControlPlaneService` consumes `ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD` and now carries that canonical `WorkloadRecord` through namespace-mutation helpers instead of restating workload string pairs. |
| Gitea state worker | `catalog-resolved` | `GiteaStateControlPlaneExecutionService` consumes `GITEA_STATE_WORKER_EXECUTION_WORKLOAD` and now carries that canonical `WorkloadRecord` directly into run publication instead of restating workload string pairs. |
| extension workload execution | `projection-resolved` | `ExtensionManager.run_workload(...)` now resolves one canonical extension `WorkloadRecord` through the canonical seam at workload start and carries that same record through the returned extension result and provenance instead of minting it later in provenance generation. |
| rock entrypoints that initiate governed execution | `routing-only` | the legacy CLI `--rock` alias now routes through `run_rock(...)`, a thin wrapper over `run_card(...)`, while the named runtime recommendation surface points to `python main.py --card <card_id>`; the `run_rock(...)` wrappers now survive only as thin convenience wrappers over `run_card(...)` while the module-level `orchestrate_rock` helper is retired entirely, internal rock routing now flows through a generic epic-collection entry plus generic epic-collection runtime selectors that emit collection-shaped runtime payloads instead of a `rock` field, and rock paths still do not mint standalone rock `WorkloadRecord` authority. |

## Surviving projection-only or still-temporary surfaces

Surviving surfaces that remain allowed for now:
1. extension-manifest workload metadata surfaces under `orket/extensions/`
   Reason: extension manifest parsing now stays separated from canonical control-plane workload authority, the old runtime workload-adapter shim is retired entirely, and extension manifest metadata now lives behind the private `_ExtensionManifestEntry` type with `ExtensionRecord` storing that metadata on `manifest_entries`, installed extension catalog persistence now writes `manifest_entries` and only compatibility-reads legacy persisted `workloads` rows while the external extension manifest contract still truthfully keeps its `workloads` array, the older private `_ExtensionManifestWorkload` noun, the public `ExtensionManifestWorkload` noun, the older `ExtensionWorkloadDescriptor` noun, the old `manifest_workloads` field, the old installed-catalog `workloads` field, and the old manifest `WorkloadRecord` alias retired from active extension surfaces, no outward `ExtensionManifestWorkload` re-export through `orket.extensions`, no outward `ExtensionManifestWorkload` runtime attribute on `orket.extensions.manager`, and no outward generic `ExtensionManager.resolve_workload(...)` or `ExtensionCatalog.resolve_manifest_entry(...)` surface beyond the private manifest-entry helpers `_resolve_manifest_entry(...)`, but these remaining manifest-facing surfaces are still temporary because broader runtime start paths, rocks, and extension entrypoints do not yet consume one universal governed workload authority surface directly.
2. `orket/runtime/run_start_artifacts.py`
   Reason: immutable session-scoped runtime bootstrap evidence is still valid as a projection and evidence package. Fresh `run_identity` payloads now explicitly mark that surface as session-bootstrap projection-only evidence and bootstrap reuse plus summary builders, reconstruction, validators, and consumers now reject framing drift or enclosing-summary `run_id` mismatch, but it still cannot truthfully hold invocation-scoped cards epic run ids.
3. `orket/runtime/run_summary.py`
   Reason: legacy runtime summary output remains an active projection surface for cards runs and other runtime proof paths. Cards summaries now project durable cards-epic run or attempt or step state from persisted records, the dedicated `control_plane` block now fails closed if explicit projection framing drifts, if projected lower-level ids survive after dropping parent run or attempt ids, if projected runs drop core run metadata while still carrying `run_id`, if projected attempts survive without attempt state or a positive attempt ordinal, if projected attempt state or ordinal survives after projected `attempt_id` drops, if projected `current_attempt_id` survives after projected `attempt_id` drops, if projected `current_attempt_id` drifts from projected `attempt_id`, or if projected attempts or steps drift outside the projected run lineage or projected steps survive without `step_kind` or if projected `step_kind` survives after projected `step_id` drops, and shared probe/workload, audit, and training consumers now validate the summary contract before trusting it, but the broader summary surface is not yet demoted lane-wide to projection-only closure behavior.
4. `orket/application/review/lanes/`
   Reason: deterministic and model-assisted review lanes remain valid evidence-producing review components. Fresh review manifests plus persisted decision/critique artifacts now explicitly mark those lane outputs non-authoritative for execution state, but not all touched read paths or replay surfaces are fully framed that way yet.
5. `orket/runtime/retry_classification_policy.py`, `orket/runtime/run_start_contract_artifacts.py`, `scripts/governance/check_retry_classification_policy.py`, and `scripts/governance/run_runtime_truth_acceptance_gate.py`
   Reason: retry policy still exists outside one universal append-only attempt history model for all runtime paths. Fresh snapshots now explicitly declare `projection_only=true` with `projection_source=retry_classification_rules` plus non-authoritative attempt history, run-start contract capture now validates that framing before persisting `retry_classification_policy.json`, the retry-policy checker now normalizes malformed report payloads into fail-closed error reports before diff-ledger write, rejects invalid embedded retry-policy snapshots in both green and failure reports, falls back to the canonical retry-policy snapshot when malformed producer output omits or drifts that embedded snapshot, and the runtime-truth acceptance gate now validates both the retry-policy report contract and the persisted run-level `retry_classification_policy.json` artifact against the current canonical snapshot before trusting top-level green signals while preserving explicit fail-closed error detail from validated retry-policy reports instead of collapsing them into generic false state, but service-local retry behavior still survives.
6. review-run result and CLI JSON `control_plane` summary
   Reason: this review-facing summary now explicitly declares `control_plane_records` projection framing, rejects malformed summaries, rejects lifecycle-incomplete projections that keep run/attempt/step ids while dropping projected run metadata, attempt state or positive attempt ordinal, or step kind, rejects projected `attempt_state` or `attempt_ordinal` when projected `attempt_id` has dropped, rejects projected `step_kind` when projected `step_id` has dropped, rejects lower-level projected attempt or step refs when parent run or attempt refs are missing, rejects projected attempt or step refs when they drift outside the projected run lineage, rejects embedded-manifest ref omission when the returned summary still carries those refs, and now reaches the user through structured `E_REVIEW_RUN_FAILED` CLI output instead of uncaught exceptions, but broader review-lane and replay surfaces still remain around that durable execution truth.
7. review-run manifest and review-lane decision/critique artifacts
   Reason: these review-facing artifact surfaces now fail closed on malformed execution-authority markers, required manifest-declared control-plane refs, manifest or lane attempt or step refs that drift outside the declared `control_plane_run_id` lineage, and orphaned lower-level manifest or lane control-plane refs that survive after parent run or attempt refs drop, but broader review-lane and replay surfaces still remain around that durable execution truth.
8. review answer-key scoring
   Reason: this scoring surface now validates persisted review-bundle authority markers, required lane-payload `run_id`, required lane-payload `control_plane_*` refs when the manifest declares them, manifest or lane attempt or step refs that drift outside the declared `control_plane_run_id` lineage, orphaned lower-level manifest or lane control-plane refs, and manifest-to-lane run/control-plane identifier alignment through one shared review-bundle loader before trusting lane JSON, now emits explicitly versioned `reviewrun_answer_key_score_v1` reports with required top-level `run_id` plus fixture/snapshot/policy provenance fields, required nested deterministic/model-assisted score blocks whose aggregate totals must stay aligned with the per-issue rows they summarize, explicit model reasoning/fix weights needed to prove reasoning and fix subtotals against those same rows, required per-issue row shape, and disabled model blocks that cannot carry derived model activity, and workload-side code-review probe score consumers now fail closed if that score-report contract drifts at the nested block, aggregate, issue-row, or top-level provenance level instead of trusting ad hoc dict shape, but other review evidence and analysis consumers still remain around that durable execution truth.
9. review consistency-signature extraction
   Reason: this consistency-analysis surface now validates persisted review-bundle authority markers, required lane-payload `run_id`, required lane-payload `control_plane_*` refs when the manifest declares them, manifest or lane attempt or step refs that drift outside the declared `control_plane_run_id` lineage, orphaned lower-level manifest or lane control-plane refs, and manifest-to-lane run/control-plane identifier alignment through one shared review-bundle loader before trusting lane JSON, the same `run_1000_consistency.py` producer now also validates shared report contract framing plus required nested baseline/default/strict/replay signature digests, deterministic finding-row code/severity/message/path/span/details shape, deterministic-lane version, executed-check lists, truncation framing, and scenario-local `truncation_check` snapshot digests, byte counts, and boolean flags before write while still allowing truthful failed outcomes to persist as failed reports and still fails closed before serialization when default, strict, replay, or baseline `run_id` is empty, and the persisted `check_1000_consistency.py` validator now also fails closed when `contract_version` drifts, when those report `run_id` values are empty, or when those required nested signature fields, finding-row fields, or scenario-local `truncation_check` fields drift instead of trusting shallow `ok` or counter fields alone, but other review evidence and analysis consumers still remain around that durable execution truth.

## Remaining gaps and blockers

Workstream 1 is not complete.

Remaining gaps:
1. `Workload` still lacks one universal governed start-path authority across every runtime start path; cards, ODR, and extension workload execution now route through the shared resolver, touched catalog-resolved publishers now carry canonical `WorkloadRecord` objects instead of local workload string-pair aliases, `run_card(...)` is now the sole public runtime surface over one normalized dispatcher, the private catalog-local helper names are now de-exported and locked to their exact owner paths, private extension manifest metadata is now mechanically contained inside `orket/extensions/`, interaction-session extension workload validation now uses a boolean `has_manifest_entry(...)` probe instead of a metadata-returning lookup surface, the extension run-action adapter now treats `run_rock` only as explicit legacy alias normalization onto `run_card(...)`, internal rock routing is colder because it no longer survives as a rock-named helper seam, no longer returns a rock-shaped runtime payload, and its default build token no longer carries the older `rock-build-...` prefix, the named runtime recommendation surface now points to `python main.py --card <card_id>` while `--rock` survives only as a legacy alias, live benchmark tooling now also shells through `--card` instead of the legacy alias, no longer emits rock-named runtime identifiers or `run_mode="rock"` in benchmark run metadata, and now defaults benchmark execution-mode metadata to `live-card`, and active runtime callsites now prefer that canonical surface directly, but broader runtime entrypoints and remaining workload-local nouns still are not fully closed.
   The matrix is now a closure gate instead of passive inventory, so any new direct workload-authority consumer that is not classified there is blocker drift immediately.
2. `Run` still has legacy read surfaces under `run_start_artifacts.py`, `run_summary.py`, and observability trees that can still look authoritative.
3. `Attempt` still is not universal across broader retry and recovery behavior.
4. `Step` still is not universal across broader runtime execution paths.
5. `CE-01` and `CE-02` both remain open.

Current blocker on the next obvious `CE-02` cut:
1. `run_start_artifacts.py` is session-scoped and immutable, while top-level cards epic control-plane run ids are invocation-scoped. Forcing invocation-scoped identity into that surface would create stale or dishonest authority on same-session reentry.

## Authority-story updates landed with these slices

The following authority docs were updated in the same slices recorded here:
1. `docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/specs/WORKLOAD_CONTRACT_V1.md`
4. `docs/specs/REVIEW_RUN_V0.md`
5. `docs/guides/REVIEW_RUN_CLI.md`
6. `docs/specs/TRUTHFUL_RUNTIME_ARTIFACT_PROVENANCE_CONTRACT.md`
7. `docs/specs/TRUTHFUL_RUNTIME_SOURCE_ATTRIBUTION_CONTRACT.md`
8. `docs/specs/TRUTHFUL_RUNTIME_NARRATION_EFFECT_AUDIT_CONTRACT.md`
9. `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
10. `docs/architecture/CONTRACT_DELTA_REVIEW_RUN_CONTROL_PLANE_IDENTITY_2026-03-28.md`
11. `docs/architecture/CONTRACT_DELTA_REVIEW_RUN_BUNDLE_IDENTITY_2026-03-28.md`
12. `docs/architecture/CONTRACT_DELTA_RETRY_POLICY_REPORT_SNAPSHOT_VALIDATION_2026-03-29.md`
13. `docs/architecture/CONTRACT_DELTA_REVIEWRUN_ANSWER_KEY_SCORE_REPORT_2026-03-29.md`
14. `docs/architecture/CONTRACT_DELTA_REVIEWRUN_CONSISTENCY_REPORT_VALIDATION_2026-03-29.md`

## Verdict

Workstream 1 has materially narrowed `CE-01` and `CE-02`, but it is still open.

The next truthful Workstream 1 work should still prioritize workload convergence ahead of lane-celebration or new breadth: keep remaining workload-local surfaces adapter-only, extend the start-path matrix until every governed start path is catalog-resolved or projection-resolved through the one seam, and then demote the remaining legacy run and attempt read surfaces without pushing invocation-scoped control-plane identity into immutable session-scoped artifacts.

