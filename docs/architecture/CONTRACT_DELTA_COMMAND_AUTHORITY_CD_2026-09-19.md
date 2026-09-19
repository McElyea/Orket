# Prompt, setup, vision and operator command authority

## Summary

Owner: Orket Core. Effective date: 2026-09-19. Version: 0.6.32.
Status: implementation candidate; full architectural-truth acceptance remains open.

## Delta

Prompt commands delegate to application `PromptAssetService`. It captures nested
options and one supplied date before awaiting, then retains the complete guarded
file operation through interruption. Without an explicit `as_of`, application
`RuntimeInputService` supplies the UTC calendar date. SLA selection, metadata and
changelog use that same date. Invalid explicit dates fail instead of falling back.
Core owns metadata transition rules and status vocabulary over supplied values;
application owns asset selection, lint and prompt resolution.

Prompt names must match `[A-Za-z0-9][A-Za-z0-9_.-]{0,127}`. Role and dialect paths
stay inside their selected model directories; final symlink/reparse assets are
refused. Metadata writes require an ID matching the requested asset. SLA refuses
filename/metadata identity drift before updating any selected candidate. A supplied
promotion report must be an object, and canary/stable promotion requires its `pass`
field to be exactly `true`. The report remains optional; this change does not
introduce mandatory external evaluation evidence for promotion.

Queries and writes share the existing model-root native ownership with driver
resource commands: `<project>/model.driver-locks/`. A query can create an ownership
identity or refuse a busy owner. Preserve these files during active operations.
Applied updates use same-directory replacement, flush/sync and closed-file byte
readback before returning success. Preview remains advisory. SLA writes are separate
effects; a later failure does not roll back earlier writes. Diff resolves each side
separately and does not claim an atomic two-selection snapshot.

Interactive project setup runs as `python -m orket.interfaces.setup_cli`. The old
`orket/cli/setup_wizard.py` file is retired; `orket.cli` is a module, so the old
`python -m orket.cli.setup_wizard` spelling was not a working module entrypoint.
Application `SetupService` captures choices, validates the explicitly selected
module profile before effects, constructs organization policy and retains the
worker through interruption. The interface only collects inputs and presents the
result. Existing first-run runtime onboarding remains a separate startup operation.

Setup creates the chosen workspace/model directories, publishes and verifies
`<invocation>/config/organization.json`, and updates `module_profile` through the
shared settings authority without replacing unrelated settings. The CLI captures
`ORKET_DURABLE_ROOT` against its invocation root before collecting input. Chosen
workspace/model paths initialize directories; they do not change runtime path
selection defaults. Explicit absolute directory choices remain supported. Setup
serializes cooperating organization writers with
`<invocation>/config/organization.json.setup-locks/`; settings retain their existing
native guards. Initialization success follows both verified publications. Directory,
organization and settings effects are separate; failure can leave partial setup.
Inspect those locations before retrying. No rollback or restart journal is added.

ToolBox constructs application `VisionService` with the selected `sd_model` once.
Its existing default remains `runwayml/stable-diffusion-v1-5`. Image arguments are
copied before ToolBox dispatch and before service worker admission. A nonempty prompt
is required. The adapter receives an explicit model and performs no settings lookup.
Inference, encoding, publication and temporary cleanup stay owned through cancellation.
Native ownership at `<workspace>.vision-locks/` serializes cooperating image workers
and their cached pipeline use. A busy owner returns a failed tool result.

Encoding uses a temporary file with the requested filename/format. Missing or empty
encoder output is failure. Only observed nonempty bytes are published, flushed and
read back before `ok: true`. That acknowledgement proves local byte publication,
not image quality or semantic correctness. Optional inference dependencies remain
optional; their absence returns the existing explicit dependency error. Analysis
remains unimplemented and returns a refusal. Controlled encoder tests are not live
Stable Diffusion inference proof.

Application `operator_runtime_service` now interprets supplied run evidence and
card runtime intent. Interface view models retain display text and response shaping.
Existing completion vocabulary is preserved: lifecycle completion without accepted
evidence remains unverified, and ODR failure before primary output remains prebuild
blocked. This move adds no acceptance authority to UI fields.

All native locks cover cooperating local writers, not hostile editors or remote
filesystems. Interruption waits for an admitted worker; it cannot forcibly stop
inference or a stuck filesystem call. A timeout can therefore settle after its
requested deadline. Failed acknowledgement does not prove that no effect occurred.
Current local responsiveness and released-worker settlement proof bounds remain
0.5 seconds and 3 seconds. Wider async reachability and input ownership remain D work.

## Migration Plan

1. Embedded prompt callers use `await PromptAssetService(absolute_root).execute(...)`.
   Operations are `list`, `show`, `lint`, `resolve`, `update`, `stale`, and `enforce_sla`.
   Old synchronous helpers in `orket.interfaces.prompts_cli` have no aliases.
   The prompt CLI command tree and result shapes remain, with the stricter refusals
   and supplied-date behavior above. Tests and scripts must select their own temporary
   assets when a read should not create lock identities in the source checkout.
2. Invoke interactive setup through `python -m orket.interfaces.setup_cli`.
   Embedded callers supply `SetupService(absolute_root, SettingsLocation(...))` and
   await `initialize(choices)`. Setup does not initialize model providers or prove
   that the selected profile's external integrations are available.
3. Use `VisionService` for asynchronous image commands, or the ToolBox binding.
   Direct blocking `VisionTools` callers must supply `model_id` and retain a worker;
   its adapter export is not an asynchronous application entrypoint.
4. Existing operator HTTP response fields remain unchanged. Runtime interpretation
   is application-owned; no compatibility forwarding module is introduced.

## Verification and acceptance

The canonical plan records exact source/package/native proof and retained failures.
Initial command tests reproduced a prompt path escape, incorrect supplied-date
publication, unknown-profile setup success and image success without encoder output.
The first two command runs also exposed test fixtures creating root lock identities;
those files and failed input-stability observations are retained separately.
Tests now copy canonical assets into selected temporary roots.

Full dependency, async, quality and capability acceptance remains open. This contract
does not claim hosted CI, full-suite green, provider inference, hostile-code
containment, generic transactions or whole-lane acceptance.
