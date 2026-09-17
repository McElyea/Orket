# Card Completion Acceptance Contract

Last updated: 2026-09-13
Status: Active contract; builtin completion passes scoped BT-3 acceptance
Owner: Orket Core

## Epic approval pause and continuation

An admitted governed turn-tool approval pause is unfinished execution. It must
retain the original epic admission, running ledger and control-plane invocation;
it must not retain a terminal workload outcome or publish terminal success/failure.
The publication journal retains `epic_approval_pause.v1`: original request/export
binding, execution artifacts/transcript and exact approval requests. Later pauses
append to retained history without extending pre-effect continuation authority.
Each pause is consumed once under the journal write
transaction after all its decisions are resolved. Pending decisions cannot dispatch.

Continuation uses the original request and same governed child turn identities,
without card reset, new epic initialization or repeated setup effects. The
original turn checkpoint and its authorization checks remain the tool authority.
Post-effect continuation remains outside the admitted checkpoint contract and
must preserve its recovery refusal; retaining a later approval pause cannot authorize it.
Denial stops unfinished governed children and publishes parent failure without
executing their approved effects. Existing terminal publications are immutable;
old failed runs are not converted to pauses. A consumed pause with no later pause
or outcome is uncertain and cannot be automatically dispatched again. Restart
before consumption is supported. The explicit recovery below admits a new
continuation only after its guarded owner releases local ownership. Concurrent
decisions/continuations cannot consume a pause twice.

## Interrupted approval recovery

New standard approval claims retain an `epic_continuation_lock.v1` artifact.
`EpicApprovalPauseService` uses the exclusive native lock supplied by runtime
composition. This is a local continuation contract; the architectural-truth plan
records its current verification and remaining wider recovery obligations.

1. Continuation admission must hold an exclusive local execution lock for the
   selected journal/session before consuming a pause. Its stable lock-file
   identity is retained with new claims. The lock remains held through restored
   workload execution and durable outcome or next-pause retention, including
   cancellation cleanup. The continuing caller releases it before entering
   export and publication. Other callers may independently finalize an already
   retained outcome; export recovery keeps its own admitted ownership protocol.
   A lock is not an effect
   receipt or proof of remote/descendant termination.
2. Canonical Python `run_card(..., approval_recovery=...)` must bind the original
   epic/session/request, pause sequence/digest, expected recovery-history head,
   stable request ID, operator/reason references and explicit continuation
   resolution. It is mutually exclusive with admission and export recovery.
3. Recovery must acquire the same lock. A live holder refuses takeover; no expiry
   or age-based assumption can replace ownership. Missing or substituted retained
   lock identity rejects recovery. The lock path is operational local state and
   must be preserved with the journal, not recreated to clear a refusal.
4. Under the journal writer, recovery revalidates the original pause, decisions,
   parent/admission and checkpoint authority, then records one bound recovery
   request and canonical operator action. Exact reentry observes that grant and
   cannot dispatch again; conflicting reuse, stale history and superseded requests
   reject. Another interrupted grant requires a new explicit request.
5. Approved continuation keeps the original pre-effect checkpoint and tool
   authorization checks. Known steps/effects, orphan operation artifacts or
   insufficient checkpoint evidence cannot authorize a retry. Every referenced
   approved child must remain pre-effect; already completed children also refuse
   this grant. Denial follows the
   existing stop/failure path and does not dispatch the approved effects. Recovery
   does not invent workload return, reset cards, replace child identities, widen
   accepted completion, or admit general post-effect continuation.
6. Previously unmarked consumed pauses remain unresolved. An unconsumed waiting
   pause may receive a marker only when its actual guarded claim commits. Retained
   outcomes and publication records continue through their existing protocols.
   There is no backfill, old-store merge, independent-journal recovery or implicit
   ownership upgrade. The broader unknown-workload recovery obligation remains.
7. `epic_approval_recovery_request.v1` requires `session_id`, `sequence`,
   `request_id`, `expected_pause_digest`, `expected_recovery_digest`,
   `operator_ref`, `reason_ref`, and `resolution="continue_resolved_pause"`.
   `expected_recovery_digest` is explicitly null for the first grant and the
   retained latest recovery digest for a subsequent grant on that pause. Request
   IDs are unique within a session. Append-only `epic_approval_recovery.v1` rows
   share the publication SQLite transaction; each binds the original pause,
   predecessor and lock identity plus a canonical operator action. Outcome and
   publication artifacts reference the complete retained recovery history;
   missing or conflicting referenced history prevents success publication.
   Unresolved observations include retained recovery digest references. The
   original claimed pause is never reset or rewritten by recovery.

Delta: `docs/architecture/CONTRACT_DELTA_EPIC_APPROVAL_RECOVERY_BT3_2026-09-13.md`.

## Authority and implementation status

Engine, epic and turn-tool composition select the same control-plane file using
`control_plane_db_for_runtime`. For absolute runtime DB paths it is the sibling
`control_plane_records.sqlite3`; the default absolute durable layout is unchanged.
Relative paths retain a pre-existing inconsistency: SQLite opens the runtime DB
relative to the process directory, while control-plane selection resolves against
the explicit workspace. Absolute DB paths define the verified scope here; relative
path convergence remains BT-5 work. Previously split custom-runtime/global
control-plane histories are not merged or moved automatically; preserve both
stores and perform explicit reconciliation before relying on old kernel/projection
history. There is no fallback to another database when a selected target is missing.

This contract implements the acceptance boundary required by BT-3/SR-07 in
`docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`.
Core input vocabulary lives in `orket/core/contracts/card_completion.py`; the
pure comparison lives in `orket/core/policies/card_completion.py`.

The core types and comparison now have an application-owned verifier and retained
evidence path in `card_acceptance_service.py`. It checks declared Python CLI
behavior or literal text/JSON artifact criteria against captured bytes and re-reads SQLite evidence before returning
its decision. `card_completion_service.py` now authorizes final writes through
an injected core protocol; `AsyncCardRepository` rejects new successful completion
without that authority and a typed evidence request. Explicit tools and synthesized
status requests use this boundary in composed integration proof. The standard
runtime factory now configures the service and default card repository, binds
each dispatched turn to its actual run/attempt and evaluates declared acceptance.
Its compact prompt preserves acceptance diagnostics, the actual declared criteria
and available tool names.
Turn success publication and completed-turn replay validate the current receipt
and retained evidence. Builtin writers share the completion writer guard. Builtin dependency, build,
publication and operator consumers now use retained acceptance. The final BT-3
audit records source, installed and provider acceptance plus failed-attempt
dispositions. Custom writers, separate stores and broader recovery remain
BT-5/capability obligations; they do not inherit builtin completion authority.

The 2026-09-13 approval repair retains unfinished epic execution through the
existing pre-effect checkpoint. Restart approval and denial now pass composed
source and installed acceptance; a real llama.cpp four-card flow pauses, restarts,
executes the approved write and completes the original parent and child. The proof
uses both default and custom runtime database layouts. A recorded decision alone
is still not proof that its tool ran. The final BT-3 audit assesses this alongside the completion gate; previously
published terminal failures remain immutable.

Application services must own acceptance admission, evidence collection and
completion authorization. Adapters execute the authorized persistence operation.
A deserialized completion decision, a model-supplied record, and the pure
comparison's `sufficient` property are not storage permissions.

## Declared acceptance

1. An admitted `card_acceptance_plan.v1` names an acceptance reference, policy
   reference and digest of resolved policy, workload identity, and a nonempty
   ordered tuple of unique acceptance criteria.
2. Each criterion declares its meaning, a versioned verifier reference, the
   digest of the admitted verifier definition, and the exact evidence class it
   requires. Admission must pin the verifier's actual coverage and inputs; a
   matching name or an arbitrary command returning zero does not establish it.
3. Evidence classes are `not_evaluated`, `syntax_only`, `command_execution`,
   `artifact_verification`, and `behavioral_verification`. They are distinct claims, not an automatic ranking.
   A requirement cannot request `not_evaluated`. A behavioral observation cannot
   substitute for another criterion merely because its class sounds stronger.
4. Plan digest is SHA-256 over UTF-8 of `json.dumps(plan.model_dump(mode="json"),
   sort_keys=True, separators=(",", ":"), allow_nan=False)`. Default JSON ASCII
   escaping applies. All declared fields, including schema version, criterion
   order, descriptions, policy digest and verifier digests, are bound.
5. No plan, empty coverage, duplicate criterion identities, unknown schema fields,
   or unsupported objectives can inherit acceptance from verifier success.
   The governed-agent ticket-report verifier retains its existing narrow scope.
   Verifier families require explicit declarations for their stated coverage;
   there is no universal default verifier.

## Definition admission boundary

1. The standard runtime reads `params.completion_acceptance` from the selected
   operator/application-configured card record. Programmatic repository and
   acceptance-service callers are trusted application inputs; these APIs do not
   establish the origin of arbitrary supplied definitions. A serialized trust
   flag, model proposal or accepted pure comparison cannot grant admission.
2. `card_acceptance_admission.validate_model_card_payload` rejects the reserved
   `completion_acceptance` member anywhere in a model structural asset's nested
   JSON objects/arrays. The driver applies this before `create_issue`,
   `create_epic` or `create_rock` can write assets, including legacy `cards`
   children. Builtin `create_issue` applies the same check to its arguments before
   storage. Both return `E_CARD_ACCEPTANCE_MODEL_DEFINITION_FORBIDDEN` on refusal;
   the driver records `driver_process_failed` with `failure_kind=acceptance_admission`
   in its configured operator workspace. Refusal does not write or link assets.
3. Ordinary model-created cards have no implicit acceptance. References in note
   strings, authored inputs or ODR result data are not promoted into the reserved
   top-level card parameter. Without an admitted definition, completion remains
   `not_evaluated` and cannot authorize a new successful terminal write.
4. Existing config files do not carry independently verified historical authorship.
   This boundary does not retroactively establish their provenance, contain a
   privileged host writer, or authorize custom tools to rewrite definitions.
   Custom writers remain BT-5/capability work; hostile-code containment remains CAP-2 work.

## Dependency and dispatch admission

1. Dependencies are local to the selected build. A prerequisite resolves only
   with `done`/`guard_approved` lifecycle, a current completion binding and readable
   retained acceptance. Archived, canceled, pending, reopened, missing,
   foreign-build and legacy receiptless prerequisites do not resolve.
2. `card_completion_outcome_service.require_accepted_card_receipt` supplies the
   same receipt check to build finalization and `card_dependency_service`.
   `read_card_dispatch_snapshot` reads the complete build and receipts under the
   existing repository writer guard. It derives eligible cards and per-dependent
   rejection reasons from that observation. The former adapter-owned
   `get_independent_ready_issues` selector is removed; repositories expose data
   and acceptance inspection through the existing card port.
3. Planner strategies receive copies of eligible cards. They select identities;
   returned payload changes do not replace the inspected dispatch data. Unknown
   or duplicate selections fail with `E_CARD_DISPATCH_UNADMITTED`. Targeted
   ready, in-progress and review turns obey the same dependency boundary.
4. Before review preflight or turn effects, the application re-reads the target's
   dependency list, build and lifecycle and its prerequisites under the writer
   guard. Missing targets, changed dependency inputs or changed lifecycle fail
   explicitly. Unresolved acceptance stops dispatch with
   `E_CARD_DEPENDENCY_UNSATISFIED`. Turn context includes dependency lifecycle,
   accepted receipt digests and rejection diagnostics. Stalled-loop diagnostics
   retain per-dependent rejection reasons.
5. These are retained-evidence observations, not locks held across model calls or
   permanent assertions about live workspace artifacts. They do not rerun prior
   verifier commands. Concurrent changes after the final observation, custom
   writers and multi-store coordination retain their separate BT-5 obligations.

## Failed-turn requeue

Application retry scheduling may return an `awaiting_guard_review` card to
`ready`, using the existing `system_set_status` action and either
`retry_scheduled` or `runtime_guard_retry_scheduled`. This extends the existing
in-progress retry exception; ordinary `set_status`, unrelated reasons and
terminal-card reopen requests do not inherit it. Both transition gate hooks
still apply. Builtin model status tools cannot select the system action by
embedding action/reason fields in their arguments.

Requeue retains the failed turn and retry count, invalidates its completion
context/reference, and publishes failed, unsatisfied dispatch truth. It does not
invent a guard decision or accepted completion. Exhausted retries retain the
existing blocked outcome. The next attempt requires a new completion binding and
fresh acceptance before a successful terminal write. `ready` denotes eligibility
for later dispatch, not an automatic resume guarantee or evidence that the failed
turn had no effects. Interruption and atomic publication across stores remain
separate obligations.

## Bounded Python CLI verifier

1. `card_python_cli_acceptance.v1` is an explicit application input, not a public
   admission endpoint. It declares acceptance/policy/workload references, one
   Python entrypoint, all artifact paths used by the checks, and 1-32 independent
   cases. Each case names its criterion, meaning, exact argument tuple and expected
   JSON text. The caller must supply the accepted workload requirements; model
   response content cannot create an admitted definition.
2. The definition admits only normalized relative paths under `agent_output`.
   Its entrypoint must be a declared `.py` artifact. Each case runs a fresh copy
   of the captured artifact bytes with `python -I -B <entrypoint> <arguments>`.
   All declared Python sources must compile. Arguments retain empty strings and
   leading/trailing whitespace. The environment comes from the shared sanitized
   child environment policy; arbitrary host environment variables are excluded.
3. `python_cli_exact_json.v1` requires exit zero, complete valid UTF-8 stdout,
   standard JSON with unique object members and finite numbers, and exact equality
   of normalized JSON with the declared expectation. Object key order is ignored;
   booleans, strings and numeric representations are not interchanged. Each case
   must leave the declared snapshot artifacts unchanged. Passing this verifier
   proves only those declared cases on the recorded interpreter/environment.
4. Limits: 64 declared artifacts, 1 MiB per artifact, 8 MiB per snapshot, 32
   arguments per case with 4,096 characters each, and 1-60 seconds per case.
   Normalized expected JSON and captured stdout are bounded at 2,000 characters.
   A clipped stdout capture cannot satisfy acceptance, even when its prefix parses.
5. The policy digest hashes the UTF-8 `PythonCliAcceptance.model_dump_json()`
   representation, including default fields and ordered cases/paths. The verifier
   digest hashes the sorted compact JSON definition built by
   `card_acceptance_evaluation._verifier_digest`, binding the verifier version,
   entrypoint, complete case, interpreter flags, capture limit and check semantics.
6. Artifact-manifest digest hashes UTF-8 compact sorted-key JSON of the path-sorted
   entries `{path, sha256, size_bytes}`. Raw bytes are preserved, including LF/CRLF.
   Input digest hashes the retained normalized JSON envelope
   `card_acceptance_inputs.v1`, containing workload inputs and the executable,
   Python version and sanitized environment used for the checks.
7. `card_acceptance_package.v1` retains the definition, plan, scope, input envelope,
   artifact bytes and manifests, command receipts and diagnostics. The adapter
   `card_acceptance_evidence_store.py` retains content-addressed JSON in the
   caller-selected SQLite database, with a 32 MiB body limit and immutable-row
   triggers. Standard runtime composition defaults to
   `<runtime-db-filename>.card_acceptance.sqlite3` beside the card database;
   direct service callers may select an explicit evidence store. No production
   migration has been executed.
   Read inspection uses SQLite read-only/query-only mode, checks content digests,
   and does not initialize, repair or execute the evidence store.
8. Inspection recomputes the admitted plan, verifies retained bytes and manifest,
   validates the executed argv/cwd and lossless output metadata, and compares all
   criteria with the caller's current scope. It never treats a saved success flag
   as authority. This establishes consistency of retained application evidence,
   not authenticity against a privileged coordinated rewrite of the host store.
9. Cancellation stops admission of further cases and drains the current verifier
   before removing its temporary snapshot and propagating cancellation. Repeated
   cancellation is covered for a normally exiting child. The shared verifier's
   descendant termination and raw-stream memory bounds remain BT-4 work; this
   service does not establish hostile-code OS containment.

## Bounded artifact verifier

1. `card_artifact_acceptance.v1` requires an explicit schema token and
   acceptance/policy/workload references, 1-64 declared artifact paths and 1-32
   unique criteria. Paths use the same normalized `agent_output` inventory and
   capture bounds as CLI acceptance. Every criterion must name a declared path.
2. `text_equals` requires strict UTF-8 decoding and exact equality with
   `expected_text`, bounded to 4,096 UTF-8 bytes. No whitespace, line-ending or
   Unicode normalization occurs. A missing file cannot satisfy an empty expected
   string. `artifact_text_equals.v1` produces `artifact_verification` evidence;
   it does not execute the file or prove program behavior.
3. `json_value_equals` parses standard JSON with unique object members and finite
   numbers, then follows `key_path` (up to 16 object member names). An empty path
   selects the entire value. Arrays are values, not traversable member containers.
   The selected value must equal the normalized `expected_json` text, bounded to
   2,000 characters. Missing members, malformed JSON, invalid UTF-8, trailing
   content and mismatched types or numeric representations fail. Additional
   members outside the selected value are not asserted. This verifier is
   `artifact_json_value_equals.v1`, also `artifact_verification`.
4. `card_artifact_acceptance_evaluation.py` binds each full criterion to a
   versioned verifier digest and reconstructs its observations from retained
   bytes. The shared core comparison still requires exact class, scope, plan,
   policy and verifier matches. Artifact evidence cannot substitute for a CLI
   behavioral criterion or establish broader semantic correctness.
5. Artifact evidence uses `card_acceptance_package.v2`: definition, plan, scope,
   inputs, raw artifacts/manifests and diagnostics, with no command receipts.
   Its input envelope records `runtime.verifier = card_artifact_verifier.v1`;
   interpreter/environment inputs are not invented for a non-executing check.
   The reader rejects artifact definitions in v1 packages, CLI definitions in v2
   packages and command receipts in artifact packages. Existing CLI v1 bodies,
   defaults and digest serialization remain unchanged. Both families share the
   existing immutable evidence store and final current-artifact recapture gate;
   this is not a database schema migration.
6. The canonical tiny summation asset builder declares stage-specific acceptance
   in `runtime/execution/live_acceptance_contracts.py`: the literal requirement,
   selected design fields, three actual two-integer CLI cases for implementation
   and review, and the exact source-attribution JSON when that task is enabled.
   These checks do not establish general requirements quality, architectural
   correctness, or universal program behavior. Broader workload coverage remains
   CAP-1 work.
7. Turn prompts expose `criteria_definition` from the validated persisted attempt
   inputs alongside the decision and missing criteria. Model narration cannot
   replace that definition or grant acceptance. Legacy empirical verification
   remains support evidence: its result and scenario observations survive later
   preparation saves, while a passing fixture with no declared acceptance still
   cannot authorize completion.
8. Compact prompt section extraction retains declared acceptance once, without
   copying it into preceding project-context or patch sections. The application
   passes its resolved legacy `runtime_verifier_enabled` setting into prompt
   composition; a disabled verifier must not be advertised as a future check.
   Explicit verifier commands replace the inferred no-argument command in the
   prompt. This setting does not disable declared acceptance or change its
   persisted criteria, evidence, parser or publication gates.
   Disabled legacy verification also removes its inferred support-artifact read
   from review context; an explicit turn-contract read is still honored. Canonical
   tiny-summation stages declare their actual artifact outputs and review paths:
   requirements and design are artifact stages, implementation/review use the app
   contract, and optional attribution uses its receipt artifact. A requirements
   fixture must not create placeholder Python merely to satisfy a later app review.

## Shared verifier capture

Runtime command receipts now include exact `argv`, plus `stdout_*` and `stderr_*`
fields for `truncated`, `encoding_valid`, `bytes`, and `sha256`. Digests and lengths
describe the original captured byte streams; diagnostic text may be clipped or
decoded with replacement. Existing receipt consumers may ignore these additive
fields, but a stdout acceptance contract must refuse unverified or lossy capture.

`stdout_capture_incomplete`, `stdout_encoding_invalid`, and
`stdout_capture_unverified` distinguish these failures. A successful process exit
is still reported as exit zero when stdout verification fails. Existing runtime
support-artifact paths and event names remain unchanged. Direct `RuntimeVerifier`
callers retain their existing environment behavior unless an explicit command
environment is supplied; this service supplies the sanitized environment.

## Evidence and scope

1. `CompletionScope` binds card, run, attempt and workload identities, input
   digest, and artifact-manifest digest. All identities are required; digests
   are lowercase SHA-256 values. Equality is exact across every field.
2. `card_acceptance_evidence.v1` additionally binds plan digest, criterion,
   verifier reference and digest, observed class and result, source, and retained
   evidence reference and body digest. Results distinguish passed, failed and
   not evaluated. Model self-report is inadmissible under this contract; a future
   attestation policy requires separate admission.
3. The application must retain and verify the referenced evidence bodies,
   manifests, artifacts, workload inputs, resolved policy and verifier definition.
   Unresolvable references, stale bindings, digest mismatch, missing inventory,
   substituted artifacts and uncertain source provenance deny completion.
   Matching digest strings alone do not prove that these checks occurred.
4. `CompletionEvidenceSnapshot.inventory_complete` defaults to false. Only the
   application reader that validates the retained evidence and expected inventory
   may set it true. Any snapshot diagnostic denies completion. This is an input
   contract, not an authenticity mechanism or a user-facing admission interface.
5. Exactly one admissible observation must cover every criterion. Duplicates,
   contradictory observations, reused evidence references, and undeclared
   criteria deny completion. Comparing only a passing subset is insufficient.
6. Evidence freshness must hold at final persistence, including after a tool
   writes between preflight and completion. The application/storage integration
   must bind completion to the exact verified artifact snapshot and active
   run/attempt, without a check/write race or cached-result bypass. Card-input
   writes now serialize with final review. ToolBox `write_file` and
   `create_directory` use the same writer guard. Normal per-tool completion cache
   entries are not reused as authority. Builtin writer coordination, standard
   composition and completed-turn receipt inspection are described below;
   custom writers require separate BT-5 admission and verification.

## Final card persistence

1. `params.completion_acceptance` supplies the explicit `PythonCliAcceptance`
   definition from application-owned card inputs. It is not accepted from model
   tool arguments. Invalid definitions fail admission; missing definitions remain
   not evaluated. No default objective or verifier is inferred.
2. `card_completion_context.v1` binds card/run/attempt, a monotonically increasing
   per-card generation, configured resolved workspace, definition digest and
   canonical card inputs. The repository admits it by compare-and-swap against
   current generation and inputs. Status, notes, support verification/metrics,
   timestamps and completion bookkeeping are excluded from the workload input
   snapshot. Input or status changes invalidate the active context. Supported
   artifact writes preserve attempt identity but require fresh artifact matching.
3. `CardCompletionRequest` contains context/evidence digests; it is not a token
   granting permission. Final `done` and `guard_approved` writes require a
   configured `CardCompletionAuthority`. Under `BEGIN IMMEDIATE`, the repository
   reloads the row, checks context/generation/inputs, and calls the application
   authority. That service recaptures current artifacts and interpreter/environment
   scope and re-inspects retained evidence using the same capture/comparison as
   verification. The evidence reader must use a separate store to avoid nested
   writes or initialization against the card transaction.
4. An accepted write atomically retains `card_completion_receipt.v1`, updates the
   card reference/status, and records history. The receipt binds context, request,
   target status and sufficient decision. Identical admitted retries retain one
   receipt and one history row. Failed final writes roll back both. Saving a new
   successful terminal row or changing terminal inputs through `save` is rejected;
   reopen first. Support annotations preserve an existing terminal record and its
   acceptance reference without creating new acceptance.
5. Card storage migration v2 adds `completion_generation`,
   `completion_context_json`, `completion_ref`, and `card_completion_commits`.
   Immutable-receipt and direct-SQL backstops reject unsupported terminal inserts,
   receiptless transitions, terminal input/generation changes, identity changes
   and deletion of a card whose generation has advanced. Archive is supported.
   Bulk nonterminal status/input changes invalidate the current context.
   Migration preserves historical terminal rows with generation zero and no
   acceptance receipt. Reading those rows does not promote them to verified
   objective success. This additive migration has only run on isolated proof data.
6. `CardWorkspaceMutationService` owns supported file writes while holding the
   same database writer guard. Cancellation, including repeated cancellation,
   drains the operation and releases the transaction before propagating. ToolBox
   file writing/directory creation and the other builtin writers listed below are
   wired; direct standalone file adapters, custom strategies and out-of-band host
   mutation are not covered by that integration. Retained receipts describe exact
   accepted snapshots; they do not promise the workspace remains unchanged forever.
7. Explicit `update_issue_status` receives `card_completion_request` only from
   its application context and exposes structured rejection diagnostics when
   available. Synthesized successful statuses require the typed
   `card_completion_decision` to be sufficient; storage still independently checks
   the evidence request. A legacy boolean or model-supplied request dictionary
   cannot authorize completion. Normal tool cache entries do not replace this
   final review. Successful tool responses carry `completion_ref`, the committed
   receipt digest. A completion claim must match the current card receipt and
   application-bound context (or the typed request's context digest). Reopened
   cards, different attempts, substituted receipt references and missing retained
   evidence cannot authorize normal or replayed turn success.

## Standard runtime composition and retained outcome inspection

1. `OrketRuntimeContext.from_env` builds the application service and binds it to
   the default `AsyncCardRepository`. A caller-injected repository is not silently
   rebound; it must carry its own completion authority. Standalone unconfigured
   repositories continue to reject successful writes.
2. Orchestrator turn preparation uses its actual dispatch run/attempt identity,
   persists the generation and evaluates acceptance. Explicit completion refreshes
   the evidence request immediately before invoking the card tool. The legacy
   verifier-disable setting does not disable declared acceptance.
3. `read_completion_receipt` uses a read-only card-store connection, checks row,
   generation, context, inputs and digest, then asks the configured application
   authority to inspect retained evidence. It never initializes a missing store.
   Inspection establishes consistency of the retained snapshot; it does not rerun
   commands or claim that workspace files remain unchanged after completion.
4. Final turn publication validates completion claims before success closeout.
   Status-only successful writes also publish control-plane results. Completed
   turn reentry checks current receipt/evidence without model or tool redispatch
   and without changing card, acceptance or control-plane records. Historical
   final truth is retained when a later reentry is rejected.
5. Filesystem writes and directory creation, `image_generate`, `archive_eval`,
   `promote_prompt`, `reforger_inspect` and `reforger_run` share the card writer
   guard. Selection follows the actual builtin callable, including aliases.
   Cancellation or timeout drains owned writes, including synchronous work in a
   thread, before releasing the guard. This is ownership proof, not a hard timeout
   bound or containment of arbitrary custom strategies.

## Build outcome inspection

1. `card_completion_outcome_service.inspect_build_completion` owns the build
   acceptance snapshot. It receives the admitted epic's expected card IDs through
   the canonical `CardRepository` port. Inventory and receipt inspection share one
   completion writer guard, excluding supported card writers across the entire
   read. Each receipt must also match its captured card row.
2. A successful build requires a nonempty inventory, every expected card present,
   and every observed card in `done` or `guard_approved` with current bindings and
   readable retained acceptance. Canceled, archived, blocked, legacy receiptless,
   missing and evidence-unreadable cards cannot authorize successful completion.
   An additional unaccepted card also prevents success.
3. Epic finalization retains `card_completion_outcome.v1` in the run ledger's
   artifacts: `build_id`, `expected_card_ids`, `card_count`,
   `acceptance_satisfied`, `accepted_receipts` (card ID to receipt digest),
   `unverified_cards` (card ID to diagnostic), and `diagnostics`. An empty inventory
   includes `empty_backlog`; a missing expected row reports
   `E_CARD_COMPLETION_CARD_MISSING`. This artifact projects the validated snapshot;
   it is not independently trusted acceptance evidence.
4. Only a sufficient snapshot may produce session `done`, and existing source
   attribution gates can still reject it. A nonempty workflow-terminal inventory
   without sufficient acceptance produces `terminal_failure` and a
   `card_completion_unverified:<card IDs>` reason unless another failure reason
   already applies. A nonterminal or empty inventory remains `incomplete`.
5. Loop policy `is_done` means workflow termination only. The application emits
   `orchestrator_epic_stopped` when that rule stops the no-candidate loop, including
   empty, canceled and archived backlogs. It does not use a strategy's event name
   as completion authority. `orchestrator_epic_complete` is emitted only after
   accepted finalization through the control plane and run ledger.
6. This is a consistent retained acceptance snapshot, not a cross-database commit
   or a permanent claim about current workspace files. The writer guard is released
   before downstream session, summary, success-store and control-plane publication.
   Historical receipts are not recaptured or re-executed during inspection.
   Scheduler dependency and builtin card/run/graph operator inspection reuse
   this receipt check. Other execution families retain their BT-5 conformance
   requirements and cannot infer completion from this card contract.

## Operator execution graph

1. Application-owned graph inspection reads the session inventory and referenced
   prerequisites through the card repository under one completion writer guard.
   Dependency checks reuse runtime dispatch context acceptance and build scope.
2. Node `status` is lifecycle. `completion_accepted` requires the current retained
   receipt and readable evidence; `completion_ref` is its validated digest, or
   null when rejected. `completion_rejection` explains rejection.
3. `blocked` and `blocked_by` report rejected prerequisites even for terminal
   nodes. `accepted_dependency_receipts` and `dependency_rejections` expose the
   same acceptance decision as dispatch. A valid same-build prerequisite can be
   outside the displayed session. `unresolved_dependencies` continues to identify
   references missing from the displayed node set, not failed acceptance checks.
4. Ordering and handoff edges are observational, not dispatch or completion
   authority. Canonical stored cards have no parent field; no spawn edges are
   inferred. Inspection never executes acceptance commands or rewrites receipts.
5. The stable execution graph snapshot is a support artifact written through the
   application workspace mutation guard after inspection releases its guard.
   It is not an atomic publication with the inspected stores. Write failures are
   logged and do not turn valid reads into successful persistence claims.

## Card and run operator views

1. Card list/detail views use application-owned receipt inspection under the card
   writer guard. They expose the same `completion_accepted`, `completion_ref` and
   `completion_rejection` fields as the execution graph. Both accepted successful
   statuses qualify for the completed filter. Unaccepted done/guard-approved rows
   require review. Lifecycle stays in `raw_status`; typed cards serialize enum
   values as JSON tokens before projection.
2. Card summaries describe the inspected card. A previous run's summary and
   lifecycle are retained separately in `last_run`; they cannot confer completion
   on another card or override a card's independent acceptance.
3. Run verification requires successful retained lifecycle plus a published
   `card_completion_outcome.v1` that exactly matches a fresh sufficient build
   inspection, including the published expected IDs and receipt digests. Missing,
   unreadable, inconsistent or stale outcomes are unverified. These projections
   are not independently trusted acceptance evidence; current card receipts and
   their retained evidence must pass inspection again.
4. Source attribution stays separately visible. Attribution, support-verifier
   paths, raw lifecycle and model narration cannot establish verified completion.
   Run views report acceptance diagnostics and rejected/missing cards. Historical
   runs without retained outcomes remain visible and unverified.
5. These are guarded card/evidence observations, not a transaction across run
   ledger, session and card stores. They do not rerun checks, rewrite historical
   evidence, establish historical storage authenticity or claim current workspace
   currency. Other execution families need separately admitted completion proof.

## Epic completion publication ordering

1. Control-plane epic closeout uses explicit transaction-scoped execution and
   append-only record repositories. Attempt state, closeout step/effect, final
   truth and run state commit together. Failure or cancellation before commit
   rolls back the closeout; independent publishers serialize through the store.
2. Repeated matching closeout requests reuse retained run/attempt, step, effect
   and final truth after validating the retained effect journal's digest chain.
   Conflicting terminal requests, missing evidence and damaged journal history
   are rejected without rewriting successful history.
3. Session completion and success-ledger publication follow successful control-plane
   and run-ledger finalization. An earlier failure cannot publish session done,
   success_recorded or orchestrator_epic_complete.
4. This is not a transaction across runtime, control-plane and filesystem stores.
   A later session/snapshot/success-store failure may still leave partial
   publication. The retained publication protocol below recovers its admitted
   boundaries; accepted card receipts are not revoked to disguise a publication error.
   Publication exceptions propagate as publication failures; they do not invoke
   failed-workload finalization or downgrade an already accepted control-plane
   outcome. The original error remains diagnosable.

## Retained workload termination

1. Before asynchronous completion inspection or initial preparation persistence,
   application authority retains `epic_workload_outcome.v1`. It captures the
   observed workload return or failure, original request and policy, non-secret
   export binding, run artifacts, transcript, effective configuration snapshot
   and observation time. A normal return is not an accepted-completion receipt.
2. Immutable outcomes live in `epic_workload_outcomes` in the existing publication
   journal. Session binding, schema and digest are checked on read. Conflicting
   replacement is rejected. Digest checking detects damage, not independent
   historical authenticity.
3. Matching standard reentry resumes completion inspection and preparation from
   that record before card reset or workload dispatch. Current card acceptance
   and source-attribution gates still apply. The retained effective snapshot and
   transcript are published rather than reconstructed from a fresh runtime.
   Retained failures preserve their reason/class in the typed published failure result.
4. With no later preparation/publication record, missing or conflicting run-ledger
   invocation evidence rejects outcome recovery. Damaged schema/digest, missing
   outcome or changed request/export binding cannot authorize another dispatch.
   Concurrent reentry checks journal progress before repeating finalization.
5. A started run with no retained outcome, preparation or publication plan raises
   `E_EPIC_WORKLOAD_OUTCOME_UNCERTAIN` before resetting cards or dispatching work.
   This includes process loss or cancellation before the outcome commit, even if
   some or all cards have acceptance receipts. The runtime cannot infer a normal
   workload return from those receipts. No automatic takeover or effect retry is
   admitted at that uncertain boundary; owner recovery remains required work.

## Epic run admission

1. Standard epic entry retains `epic_run_admission.v2` in the publication journal
   before session creation, card reconciliation/reset, control-plane initialization
   or workload dispatch. It binds session, original request, export settings,
   opaque owner identity, observed admission time and reserved resources.
2. Within the selected journal, an active admission reserves the canonical workspace,
   build and declared card IDs. A competing same-session caller or another run
   sharing any reserved resource rejects before those writes. The immutable claim
   and conflict check commit in one SQLite transaction. Disjoint workspaces/builds/
   cards remain independently admissible.
3. Admission has no expiry or automatic takeover. An interrupted owner retains its
   reservation even when no run ledger was created. An admission is not proof of
   workload dispatch, return, acceptance or failure. Existing outcome/preparation/
   publication recovery still runs before any new admission attempt.
4. Only verified complete publication releases the reservation, in the same journal
   transaction that observes its completed progress and validates published effects.
   The admission history remains retained and cannot be reused for another run.
   Lost publication progress or conflicting retained admission evidence cannot
   authorize release. Failure publication may release after the same verification.
   New run artifacts retain the original admission digest/owner reference; missing,
   changed or prematurely released admission evidence rejects preparation and
   publication before any further completion effect.
5. The journal reader validates retained admission digests and release state before
   admitting competing resources. This is local integrity checking, not an external
   authenticity anchor. Existing publication records without an admission retain
   their prior recovery semantics; they are not backfilled as fresh admissions.
6. Explicit recovery before initialization is defined below; retained export
   recovery has its separate bound operation. Unknown workload owner recovery
   and wider fencing remain required. These reservations
   coordinate standard entries using the same selected publication journal; they
   do not fence unrelated processes or separately configured journals sharing a
   workspace, nor provide hostile-writer or descendant-process containment.

## Recovery before epic initialization

1. After claiming admission and before the first session/card/control-plane write,
   the runtime commits `initialization_started=true` under the journal transaction.
   It compares the complete retained claim with the claiming caller's record.
   A changed owner/generation or an already consumed initialization claim rejects
   before those writes. Once initialization is marked, ownership cannot transfer
   through this recovery operation, even if no run ledger exists yet.
2. The canonical Python `run_card` surface accepts an explicit `admission_recovery`
   object for an epic target with an explicit matching session ID. Its
   `epic_admission_recovery_request.v1` contract binds session, stable request ID,
   expected owner, fencing generation and claim digest, operator reference and
   reason reference. Issue/collection targets cannot silently consume this request.
3. Matching original request/export settings, an active uninitialized admission,
   and absence of retained outcome/preparation/publication evidence are required.
   Recovery changes owner, increments generation and appends the bound request,
   decision time and canonical `OperatorActionRecord` to admission history in one
   transaction. It does not fabricate an execution attempt or a failed workload.
   The replacement then competes for the same atomic initialization marker.
4. The old owner fails its comparison before initialization. Repeating an identical
   recovery request observes its existing replacement; it cannot obtain a second
   initialization. Reusing the request ID with different fields, supplying stale
   owner evidence or retrying a superseded recovery rejects. Later retained outcome/
   preparation/publication recovery continues without another workload dispatch.
5. Every history entry validates its predecessor claim digest and operator record.
   The claim reference binds owner/generation/history and immutable inputs while
   excluding initialization/release progress. This is retained local integrity,
   not independent historical authenticity or proof that a process has stopped.
6. Admission v1 cannot prove whether initialization began; the v2 reader rejects it.
   Preserve old records/digests without inventing a false initialization marker or
   recovery permission. No production migration is performed by this change.
7. This is a trusted local Python operator surface. It does not add a CLI command,
   authenticated remote recovery endpoint, workload takeover after initialization,
   or admission across independent journals. Those wider obligations remain open.

## Retained epic publication and reentry

1. Application authority retains an `epic_preparation.v2` record before control-plane
   closeout, receipt materialization, summary materialization and export. It contains
   original publication inputs, policy and export binding. Preparation completion
   and the ready `epic_publication.v1` plan commit in one journal transaction.
   The ready plan contains final ledger arguments, configuration snapshot and
   transcript. Ledger time is captured after preparation, preserving protocol order.
2. The SQLite publication repository stores both records and monotonic progress in
   `<runtime_db>.epic-publications.sqlite3`. The plan, progress and schema are
   checked against a retained digest on every read. This detects damaged history;
   it is not independent historical authenticity. The sidecar is durable state.
3. Each publication step serializes through a journal transaction, performs the
   effect through its original repository and confirms its readback before
   advancing progress: run ledger, session, snapshot, then success ledger. A
   process killed after the effect commits can resume by reading that same effect.
   Matching rows retain their original values and timestamps. No-op writes cannot
   advance progress. Missing/conflicting effects after completion are rejected,
   not silently reconstructed. Snapshots may replace the provisional checkpoint
   during their pending publication step.
4. Standard `run_epic` and `run_card` reentry checks for this retained plan before
   resetting cards or starting another invocation. Matching session/request
   reentry finishes publication or returns the verified retained transcript.
   A fresh execution uses a new session ID after conflicting reservations are
   released. Changed request/configuration/storage
   scope, changed retained acceptance, damaged journal history or lost completed
   effects fail closed. A retained failed workload returns a published failed
   runtime result after failure publication; recovery does not convert it to success.
5. Recovery uses retained inputs and revalidates card acceptance and control-plane
   closeout. Pending local preparation may repeat; a ready publication plan does
   not repeat preparation callbacks. Neither path reruns the workload. The request
   binds full epic, team and environment definitions, build, department, target and
   storage scope. Older records with insufficient bindings reject reentry rather
   than borrowing current definitions. Same-session recovery replaces automatic
   creation of another invocation from a previously published session.
6. Existing finalized invocations without preparation or a publication plan reject with
   `E_EPIC_PUBLICATION_RECOVERY_EVIDENCE_MISSING` before card reset. Do not backfill
   plans from current workspace output or reseal old history. Completed preparation
   missing its ready publication plan also rejects. Retained workload outcomes
   cover interruption before preparation retention. Unknown workload termination,
   cross-installation relocation and arbitrary custom writer bindings remain
   acceptance obligations.
7. Publication events follow confirmed effects. Recovery may repeat an event when
   a process dies after event emission but before journal progress commits. Events
   are observations, not an exactly-once delivery mechanism or a second authority.

## Preparation and export uncertainty

1. Preparation advances through closeout, receipts, summary, export-ready,
   export-started and complete. Each completed local stage retains its outputs.
   A local effect committed before progress retention may repeat through the
   standard callback on reentry; it must not redispatch accepted cards.
2. Protocol receipt failures, summary artifact write failures and export callback
   failures propagate with diagnostic context. Existing explicitly degraded summary
   generation remains distinct from a successful summary artifact write.
3. Enabled Gitea exports first prepare a local immutable Git commit. Its
   `gitea_export_intent.v1` and the export-started marker commit together before
   repository creation or push. Exact bindings, paths and payload semantics live
   in `docs/specs/GITEA_ARTIFACT_EXPORT_CONTRACT.md`.
4. Only a currently admitted claiming call may dispatch the push. Automatic reentry instead confirms
   the retained commit/subtree/manifest against the selected remote branch. A
   confirmed result finishes publication without another push or workload dispatch.
   Missing evidence remains `E_EPIC_EXPORT_OUTCOME_UNCERTAIN`; transport/integrity
   errors propagate. Empty dispatch results fail with `E_EPIC_EXPORT_RECEIPT_MISSING`.
   Disabled export has no external effect and may repeat before atomic promotion.
5. Explicit `run_card(..., export_recovery=...)` can fence an interrupted export
   owner and grant one retry of the exact retained Git commit after read-only
   remote confirmation. It requires a bound epic/session, original request and
   acceptance, current owner/generation/claim and intent digests, stable request
   ID, operator/reason references and `retry_exact_commit` resolution. It is
   mutually exclusive with `admission_recovery`; identical reentry grants no new
   dispatch. The initial `epic_export_dispatch.v1` reference is retained atomically
   in preparation artifacts, and successful publication validates the settled
   reference against owner history and the exact commit/tree receipt. Admission,
   workload outcome, accepted cards and Git intent do not change. Full semantics
   and the local fencing boundary are in the Gitea export contract.
6. Preparation v1 and insufficient old bindings reject reentry rather than inventing
   a Git intent. Existing unmarked v2 preparations allow confirmation only, with
   no inferred retry owner. Unknown workload outcomes, old-store reconciliation
   and custom writer bindings remain required work. A marker alone does not establish an
   effect. This protocol does not provide one transaction across stores or
   exactly-once external effects.

## Decision and enforcement

1. `card_completion_decision.v1` reports `not_evaluated`, `insufficient_evidence`,
   `acceptance_failed`, or `acceptance_satisfied`, with scope, acceptance and policy
   references, plan digest, missing criteria, diagnostics and evidence references.
2. Missing plan or current scope reports not evaluated. Missing, invalid or
   mismatched evidence reports insufficient evidence. A correctly bound failed
   accepted check reports acceptance failed. Only complete, correctly bound,
   admitted passing observations with no diagnostics report acceptance satisfied.
3. Satisfaction is limited to the admitted criteria. Successful syntax checks,
   process termination, parseable JSON, model narration and turn execution do not
   independently establish behavioral or objective satisfaction.
4. The application must enforce this same decision at explicit model status calls,
   synthesized completion, application transitions and final persistence. It must
   provide the operator with the missing criteria and diagnostics. Termination
   remains distinct from successful completion.
5. `runtime_verifier_ok`, verifier support artifacts, and packet-1 projections must
   not be used as completion authority. Existing support-artifact names and replay
   semantics remain governed by their existing contracts.
6. Both prompt formats project the current typed acceptance decision, including
   scope, policy and evidence references, declared criteria and diagnostics.
   Support verification with no reported errors must not instruct a guard to
   choose `done`. Absent application decision authority projects an unevaluated
   decision; the prompt does not manufacture a storage permission.
7. A governed guard rejection uses the existing single JSON envelope with empty
   `content`. The blocked `update_issue_status` call carries `args.guard_review`:
   an object containing nonempty `rationale`, a nonempty string list `violations`,
   and a nonempty string list `remediation_actions`. Initial and corrective
   prompts describe this same location. A second JSON object is not a governed
   response format. The proposal hash binds these tool arguments.
8. Pre-dispatch validation and post-dispatch guard events consume the same typed
   rejection payload. Missing, malformed or empty diagnostics, or multiple
   blocked status calls, fail guard validation before dispatch. Malformed present
   structured metadata cannot fall back to unrelated prose. Existing non-governed
   text responses retain their legacy extraction path through the shared reader.
   Guard diagnostics describe a rejection; they cannot establish accepted
   completion or replace an acceptance receipt.

Delta: `docs/architecture/CONTRACT_DELTA_COMPLETION_GUARD_BT3_2026-09-13.md`.

## Required runtime acceptance

Composed runs must exercise real verification, tools, filesystem and final storage
for absent plan, empty workspace, syntax-only evidence, incorrect but syntactically
valid behavior, failed accepted checks, stale and cross-run evidence, and behavior
satisfying declared acceptance. Both explicit and synthesized completion must be
covered, together with direct application transitions and persistence bypasses.
Only the admitted sufficient case may persist successful completion. Provider-backed
proof must identify its actual provider; deterministic model fixtures remain
integration proof of the exercised runtime components.
