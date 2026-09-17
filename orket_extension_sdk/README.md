# Orket Extension SDK

`orket_extension_sdk` is the public contract package for external Orket extensions.

## Install

Base install:

```bash
pip install orket-extension-sdk
```

From this monorepo source checkout:

```bash
pip install -e ./orket_extension_sdk
```

Optional extras:

```bash
pip install -e "./orket_extension_sdk[tts,testing]"
```

## Public Surface

- Manifest loading and validation
- Workload protocol and runtime context
- Capability registry and provider protocols
- Standard workload result models
- Extension-focused test helpers
- Immutable governed-agent request/result and proposal models
- Bounded framed-stdio codec, cancellation view, progress reporter, and
  provider-neutral model/memory capability protocols

## Generic Model Generation

Generic `model.generate` responses in the development candidate expose
`schema_version: model_generate_response.v1`, nullable integer `latency_ms`, and
derived `latency_posture` (`reported` or `unavailable`). These are frozen dataclass
fields and survive `dataclasses.asdict`. Invalid explicit latency is rejected;
the null provider reports unavailable latency. Consumers must handle null and
retain the response version/posture. The host contract is
`docs/specs/MODEL_PROVIDER_TIMING.md`; the compatibility restriction below applies.

## Governed Agent Workloads

Agent workloads use `AsyncAgentWorkload` and receive exactly one
`AgentIterationRequest` per admitted invocation. Model calls and memory reads go
through the host-owned `AgentModelCapability` and `AgentMemoryCapability`;
effects, memory writes, handoffs, and completion values returned by the child
remain proposals. The child never receives provider credentials or authority to
continue the parent run.

All public wire models support `from_wire()` and `to_wire()`. Both validate the
packaged canonical schema and semantic limits. Async frame helpers offload
schema/resource validation from the event loop. The host may reject an otherwise
valid author manifest when required runtime features are unavailable.

## Versioning And Compatibility

The architectural-truth worktree now uses development SDK `0.7.0a1` and its
explicit nullable model-receipt feature. Use it only with the paired host
candidate; published core `0.6.0` and `0.6.2` require SDK `0.6.0`. This overrides
the nominal window below for the prerelease. Candidate proof and remaining gaps
belong to the canonical architectural-truth plan; this is not a release claim.

`orket_extension_sdk` has its own semantic version sourced from
`orket_extension_sdk.__version__`; it does not follow the Orket core engine
version.

SDK `0.Y.Z` is compatible with Orket core `0.Y.*` through `0.(Y+2).*` for the
public SDK surface unless release notes explicitly narrow that window. Internal
`orket.*` imports and host-private runtime models are outside the compatibility
guarantee.

Development prereleases follow the same minor-window calculation but do not
claim released host compatibility until the built-artifact matrix passes. The
standalone SDK distribution is the sole SDK namespace owner in the current
core `0.6.2` release. Tagged core `0.5.9` still bundles SDK
`0.1.0`; overlaying the standalone SDK on that host creates duplicate ownership
and is unsupported. Upgrade core first, then force-reinstall the exact standalone
SDK wheel: removing an old core can remove SDK files that it owned. Run
`python -m pip check` and strict host validation after the upgrade.

The SDK `0.6.0` compatibility window is explicitly narrowed to verified core
`0.6.0` and `0.6.2`. Exact matched artifacts are recorded in
`docs/releases/0.6.0/PROOF_REPORT.md` and `docs/releases/0.6.2/PROOF_REPORT.md`
in the core repository. It does not certify older
bundling hosts or untested future core versions. Tagged core `0.5.9` also has
an independent undeclared `packaging` dependency; diagnostic validation with
that dependency supplied is not proof of a working clean historical install.

## Lifecycle Interceptors

The extension SDK does not register `TurnLifecycleInterceptor` instances.
Host-side Orket runtime interceptors are classified at registration as either
`advisory` or `mandatory`. Advisory interceptor crashes are logged and isolated;
mandatory interceptor crashes fail the affected turn before the governed action
continues.

## Manifest Runtime Declarations

`ExtensionManifest.config_sections` declares additional host config sections an
extension expects the host to preserve and resolve. The host registers these
sections during extension install or catalog listing.

`ExtensionManifest.allowed_stdlib_modules` declares standard-library modules an
SDK extension is allowed to import. SDK workloads are statically scanned and
then run in a host-managed subprocess with a stdlib import hook; undeclared
static or dynamic stdlib imports fail. Safe examples for many extensions include
`json`, `pathlib`, and `dataclasses`. Dangerous or side-effecting modules such
as `os`, `subprocess`, and `socket` should not be declared unless the extension
has explicit host approval for that capability. If the list is empty, SDK
workloads may not import stdlib modules beyond the runtime base allowlist.
Legacy workloads keep compatibility behavior: internal Orket imports remain
blocked, and stdlib allowlist enforcement applies only when the legacy manifest
declares a non-empty allowlist.

Agent workloads remain inside `manifest_version: v0` but declare
`workload_kind: agent`, the exact `agent_iteration_request.v1` and
`agent_iteration_result.v1` contracts, an `agent` block, and the required
`agent.iteration.v1` capability marker. The typed `agent` block rejects unknown
fields and must request `governed_agent_loop.v1`, `agent_stdio_ipc.v1`, and
`agent_model_use_receipt.v2`. The canonical wire schema is available through
`load_governed_agent_schema()` and is included in built distributions.

Host admission checks the declared features before the dedicated governed-agent
broker/handshake path can start a child. Generic workload dispatch refuses agent
workloads. Manifest validation alone does not prove runtime or OS containment.

New model receipts use v2: `latency_ms` is a nonnegative integer or null, with
`latency_posture` set to `reported` or `unavailable`. Reported values come from
the host model-provider observation; they do not certify a clock measurement.
Historical v1 reads preserve their original integer and omit the new posture
field. New declarations must explicitly admit v2 after their consumers are
updated to handle unavailable latency.

## Data Handling Policy

SDK/runtime downloaded data is user-local and should not be committed as long-lived repo content.

Versioned in git:
- small deterministic test fixtures
- data manifests (source URL, expected digest, version)
- fetch scripts

Local-only (ignored):
- downloaded model weights
- voice packs
- large datasets and caches

Current ignored roots:
- `data/voices/`
- `data/models/`
- `data/datasets/`
- `sdk_data/`

Reproducibility contract:
1. Every downloadable asset should have `id`, `url`, `sha256`, and `target_path`.
2. Fetch scripts must verify checksums after download.
3. Artifacts and manifests may reference asset ids/digests, but never embed secrets.
