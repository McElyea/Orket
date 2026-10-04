# Changelog

All notable changes to `orket-extension-sdk` will be documented in this file.

The format is based on Keep a Changelog and this package follows SemVer while in the `0.x` line.

## [0.7.1] - 2026-10-03

### Changed
- Publish the verified Windows pairing with core 0.7.1 and update compatibility
  documentation. SDK public contracts and implementation remain unchanged except
  version identity. This is a packaging/compatibility patch, not a new SDK feature.
- The admitted window is exact core 0.7.1 with SDK 0.7.1; the historical 0.7.0
  pair retains its separate release record. Other cross-pairings are not certified.
- SDK compatibility: preserved for extensions using its public surface;
  no extension source migration is required from SDK 0.7.0. Core-private fixture
  imports require the migration documented in `docs/releases/0.7.1/RELEASE_NOTES.md`.

## [0.7.0] - 2026-10-03

### Changed
- Release the architectural-truth SDK contracts with matched core 0.7.0.
  The admitted compatibility window is core 0.7.0 on Windows; future cores
  and published core 0.6.0/0.6.2 are not admitted by this release.
- Preserve the prerelease's `agent_model_use_receipt.v2` negotiation and
  `model_generate_response.v1` nullable latency/posture fields. Historical
  v1 receipts remain readable; no retained manifest is automatically migrated.
- Compatibility: breaking for SDK 0.6.0 consumers. Upgrade the matched core/SDK
  pair, review nullable latency handling, declare the required v2 host feature,
  and run strict extension validation before admitting new execution.
- No SDK implementation change from 0.7.0a1 beyond the version identity.
  Release proof and migration: `docs/releases/0.7.0/PROOF_REPORT.md` and
  `docs/architecture/CONTRACT_DELTA_CORE_SDK_0_7_0_2026-10-03.md` in the core repo.

## [0.7.0a1] - 2026-09-13

### Changed
- `GenerateResponse` adds `model_generate_response.v1`, nullable nonnegative
  integer latency and derived `reported`/`unavailable` posture. Dataclass
  serialization retains these fields. Null generation reports unavailable
  latency; generic host API consumers must handle null. Host observation adapters
  share `llm.nonnegative_int_or_none` without coercing malformed metadata.
- Development prerelease for `agent_model_use_receipt.v2`: nullable integer
  latency and explicit `reported`/`unavailable` posture. Reported latency is a
  host-provider observation, not independent clock or capacity proof. Token-usage
  posture and charging are unchanged. Canonical historical v1 receipts remain
  readable without new fields or rewritten payloads.
- New agent declarations require the `agent_model_use_receipt.v2` host feature.
  Older declarations must be reviewed and revalidated before new admission;
  there is no v1 dispatch fallback that invents a latency measurement.
- Ready frames advertise supported model-receipt versions. The matched host
  refuses an older child handshake before reservation or inference; historical
  ready-frame decoding remains available without the new field.
- This prerelease requires the paired architectural-truth host candidate. It is
  not compatible with the published core 0.6.0/0.6.2 artifacts, which pin SDK
  0.6.0. Exact candidate compatibility requires the matched-artifact proof in the
  canonical architectural-truth plan; no SDK or core release is claimed here.

## [0.6.0] - 2026-09-10

### Added
- Three fixed ticket-report acceptance cases (`mixed`, `all-open`, and
  `empty-first`) through the public fixture helper.
- SDK-local packaging authority via `orket_extension_sdk/pyproject.toml`.
- PEP 561 marker (`py.typed`) for downstream type-checking.
- Packaged canonical `governed_agent_loop_v1.json` wire schema and loader.
- Strict manifest-v0 declarations for governed agent workloads, including
  host-feature negotiation and the `agent.iteration.v1` protocol marker.
- Immutable public governed-agent submission, iteration, model-call, memory,
  effect, handoff, progress, cancellation, usage, receipt, and IPC frame models.
- Canonical semantic validation, bounded framed-stdio helpers, async workload
  protocol, host-owned model/memory capability protocols, read-only
  cancellation, and bounded progress reporting.

### Changed
- Release the public governed-agent contracts as SDK 0.6.0. The nominal core
  0.6 through 0.8 compatibility window is explicitly narrowed to core 0.6.0,
  the host verified with these artifacts. Future hosts require new proof.
- Core 0.5.9 and earlier bundling hosts are outside this release's admitted
  window. Upgrade core with both pinned wheels supplied, then force-reinstall
  SDK 0.6.0 last to restore sole namespace ownership. Run `pip check` and strict
  host validation. See `docs/releases/0.6.0/PROOF_REPORT.md` in the core repository.

### Security
- Memory-write proposals require the admitted `memory.write` capability, unique
  proposal ids, and admitted role ownership when a role is specified.
- Agent discriminators now fail closed across author validation, host install,
  catalog reload, and generic invocation. Child configuration cannot
  self-materialize the host-bound agent broker capability.
