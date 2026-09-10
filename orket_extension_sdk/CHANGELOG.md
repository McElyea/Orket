# Changelog

All notable changes to `orket-extension-sdk` will be documented in this file.

The format is based on Keep a Changelog and this package follows SemVer while in the `0.x` line.

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
