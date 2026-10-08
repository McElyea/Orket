# Apple Silicon Mac support implementation plan

Last updated: 2026-10-07
Status: Active implementation; blocked on native prerequisites
Owner: Orket Core

## Authority and objective

User accepted implementation on 2026-10-06. Durable requirements and the fixed
MA-01 through MA-09 acceptance cases live in
`docs/specs/MACOS_LOCAL_RUNTIME_ACCEPTANCE.md`. This lane does not reopen ATG-v1,
OrketUI or other completed/paused work. Full native Mac acceptance is mandatory;
an independently deliverable batch is not a reduced completion definition.

## Fixed execution queue

| Goal | Dependencies / start | Workset and exit evidence | Status |
| --- | --- | --- | --- |
| MAC-01 | Startup protocol | Audit install/runtime public paths and supervision feasibility; record source-supported blockers and affected consumers. | Complete: audit and feasibility blocker recorded; no native proof claimed |
| MAC-02 | MAC-01 | Implement equivalent native ownership only if feasible within scope; MA-06/07/09 on macOS plus existing Windows controls. | Blocked on equivalent ownership design and native proof |
| MAC-03 | MAC-01 | Built core/SDK isolated installation, upgrade/removal/state guide; Windows installed proof and native MA-01. | Producer/guide and live Windows installed proof complete; native MA-01 pending |
| MAC-04 | MAC-01 | Hardware capability and memory reporting; explicit unknowns/estimates, native observation and regression controls. | Reporting implemented; native Mac observation outstanding |
| MAC-05 | MAC-01; integrate MAC-03/04 | Existing-service guided setup, selected provider checks and prepared example; public CLI and native MA-02/03/04/08/09. | Implemented; isolated Windows candidate and actual llama.cpp workflow passed; native Mac cases remain pending |
| MAC-06 | MAC-01; integrate MAC-02 through MAC-05 | Repeatable acceptance commands, Gitea native-runner workflow, operator runbook and concrete remote access proposal. | Tooling/runbook, full Windows quality and refreshed installed/provider proof complete; native prerequisites blocked |
| MAC-07 | MAC-02 through MAC-06; authorized Mac access | All MA cases and actual Metal proof, identified packages and retained complete receipts. | Pending; user can arrange a Mac tester after main publication |
| MAC-08 | MAC-07 | Required governance/regression checks, authority consistency, completion audit and repository closeout. | Pending |

Continue independent eligible work when a dependency is externally blocked. Keep
goal IDs and the completion denominator fixed. Do not add unrelated findings as
new goals. The 2026-10-07 user direction authorizes quality/mypy closeout and finishing
in-flight unrelated work in preparation for main publication and a Mac tester.
The user subsequently authorized committing all 195 reviewed paths on main,
creating the matching annotated v0.7.8 tag and pushing both. This supersedes the
earlier no-commit/push restriction for this reviewed aggregate.
Cloud spending, external account creation and GitHub workflows are not authorized.

## Current audit

- `owned_command_worker._backend` accepts Windows Jobs and Linux subreapers only;
  `owned_command_process._decode` also restricts accepted backend identities.
  Public consumers include runtime verification/card acceptance, outward command
  execution, SDK children, provider CLI inventory/load, Git export, sandbox CLI,
  Piper and OpenClaw JSONL. Native macOS execution is not currently admitted.
- Hardware reporting now preserves Apple unified-memory observations and unknown
  GPU/Metal/model fit. Native Apple observation is still unverified.
- Built core/SDK installation has live Windows proof and an Apple Silicon
  candidate guide. Native Mac installation is still unverified.
- `.gitea/workflows/quality.yml` contains Ubuntu/Windows selections, not macOS.
- Setup saves the provider, GGUF root and runtime model default. Doctor separates
  catalog, arithmetic inference and command observations. The prepared local-agent
  example reuses governed submission and verification and has installed Windows
  actual-provider proof. Full native Mac acceptance remains outstanding.

### Supervision feasibility evidence

Apple's XNU `bsd/sys/event.h` states fork-tracking flags have been unsupported
since macOS 10.5; `bsd/kern/kern_event.c:filt_procattach` rejects those flags with
`ENOTSUP`. Thus a FreeBSD-style `kqueue NOTE_TRACK` backend is not a Mac solution.
The archived kqueue manual's `NOTE_FORK` observes a watched process; it does not
establish transitive retained descendant ownership. Process snapshots and group
termination leave reparenting/session-change races under the existing contract.

Sources inspected 2026-10-06:
- [Apple XNU event declarations](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/event.h)
- [Apple XNU event implementation](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_event.c)
- [Apple kqueue manual](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/kqueue.2.html)
- [Apple Endpoint Security](https://developer.apple.com/documentation/endpointsecurity)

Further primary-source research on 2026-10-07 identifies a narrower candidate:
Apple documents `es_new_descendants_client` and `es_sync_client` for macOS 27.
The former covers the caller's descendant subtree and does not require root or
TCC approval, but still requires the Endpoint Security entitlement. Non-root
callers and descendants cannot execute setuid/setgid binaries through this client.
The sync callback follows prior queued messages, but also runs on client deletion;
the callback alone cannot establish healthy observation or cleanup.
[Descendant client](https://developer.apple.com/documentation/endpointsecurity/es_new_descendants_client(_:_:)),
[queue synchronization](https://developer.apple.com/documentation/endpointsecurity/es_sync_client(_:_:)).

A system extension is not the only documented packaging route. Apple describes a
standalone daemon in an app-like bundle with an embedded provisioning profile.
An internal headless helper is a candidate, not an adopted design or desktop-app
scope expansion. The Apple grant, matching profile/signing identity, package
delivery and actual launch must be established before claiming this route works.
[Entitlement](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.endpoint-security.client),
[restricted-entitlement signing](https://developer.apple.com/documentation/xcode/signing-a-daemon-with-a-restricted-entitlement).

`AUTH_SIGNAL` exposes the target process before signal authorization. A trusted
descendant helper might use this to guard public `kill` against process-identity
reuse; this is an inference requiring native proof. The owner itself receives
only notifications, so it cannot supply that authorization boundary. Apple's
macOS 27 fail-closed deadline mode also denies auth messages dropped by queue
overflow. Neither feature proves complete fork/exit observation, safe client-death
behavior, or cleanup within the existing three-second budget. The private XNU
audit-token signal interface is research evidence, not an approved shipping API.
[Signal authorization](https://developer.apple.com/documentation/endpointsecurity/es_event_type_auth_signal),
[deadline mode](https://developer.apple.com/documentation/endpointsecurity/es_set_deadline_miss_mode(_:_:)).

Retained primary documents and hashes are in `.tmp/macos-support/native-api-research.json`.
The Apple team/entitlement/signing-access question was asked once; no response or
authorization has been received. Native Mac/Metal proof remains absent. Do not
admit a nominal Darwin backend or weaken any MA case while ownership is unproven.

## Resumable checkpoint

- Current batch: Windows quality/mypy closeout and core 0.7.8 publication preparation
  complete. The existing 0.5-second timing assertions, skip rules and 89-percent
  coverage floor remain unchanged. Full native Mac acceptance is still required.
- Pre-publication base: `0342a855453a5a36c3096163d74e78e42989e861`, directly on main. Preserve the
  original dirty inventory in `.tmp/macos-support/initial-state.json` and its
  patch/status files. The approved publication identity is the main commit carrying
  annotated tag v0.7.8; inspect the remote refs for its publication state.
- Mypy now passes after a type-only task-registry annotation. FastAPI cold-request
  profiling identified included-route dependency compilation on the event loop;
  owned startup now prepares the public OpenAPI schema before readiness.
  All 64 scoped native controls, first-request replay assertions, server bootstrap/
  reload, typing and Ruff passed. Full coverage passed: 13,252 passed, 93 skipped,
  89.25% in 5,681.17s. Source remained frozen, with confirmed native capture/cleanup.
  The incomplete worker measurement remains retained and disclosed.
- Fresh 0.7.8 candidate, 27 installed process cases and actual llama.cpp workflow
  passed. Eight Windows MA controls passed; MA-05 remains blocked, overall
  CONTROL_PASS/primary/partial success, never Mac acceptance. Final scope, wheel
  identities, receipts, architecture review and exact changed paths are in
  `docs/releases/0.7.8/PROOF_REPORT.md`. No proof process or model server remains running.
- Historical Windows candidate/actual llama.cpp and failed full-suite evidence:
  `docs/projects/archive/macos-support/MACOS_WINDOWS_CHECKPOINT_2026-10-07.md`.
  Archived workflow recovery is already complete; all 38 retained recovery
  receipts are terminal. Wrong model outputs remain rejected, not reopened work.
- Process receipts: `.tmp/macos-support/coverage-check.json` and the package/process/
  native acceptance reports are terminal. `.tmp/macos-support/prepublish-coverage-audit.json`
  checked retained measurement/logs, source identity and process settlement; the
  installed audit plus full audit verified 106 command-log hashes. The original
  failed full run and invalid missing-provider observations remain archived.
- Publication handoff: main and its matching annotated v0.7.8 tag are authorized.
  Next lane action: use the Mac tester/access path to resolve MAC-02 before the
  mandatory native acceptance chain. Access does not itself prove ownership.
- Remaining blockers or drift: native macOS process ownership is unimplemented;
  native hardware/Metal and MA-01 through MA-09 are unverified. A Mac tester can
  supply access after publication, but equivalent ownership and entitlement/signing
  feasibility still require native evidence. No spending or account work is implied.
