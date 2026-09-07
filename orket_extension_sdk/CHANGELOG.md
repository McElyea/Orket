# Changelog

All notable changes to `orket-extension-sdk` will be documented in this file.

The format is based on Keep a Changelog and this package follows SemVer while in the `0.x` line.

## [Unreleased]

### Added
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
- Development version moves to the SDK 0.5 prerelease line so its prospective
  core compatibility window includes core 0.5 through 0.7. No released
  compatibility claim is made until built host/SDK artifacts pass the recorded
  matrix.

### Security
- Agent discriminators now fail closed across author validation, host install,
  catalog reload, and generic invocation. Child configuration cannot
  self-materialize the host-bound agent broker capability.
