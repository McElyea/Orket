# Protocol Determinism Control Surface (v1)

Last updated: 2026-03-04  
Status: Draft  
Owner: Orket Core

This document defines the runtime control knobs used to constrain nondeterminism in protocol-governed execution.

## Objectives

1. Keep deterministic replay stable across hosts and reruns.
2. Ensure runtime, not prompt text, controls deterministic boundaries.
3. Make effective control values observable in turn context and receipts.

## Control Fields

The active control bundle is resolved per turn context:

1. `timezone`
2. `locale`
3. `network_mode`
4. `env_allowlist_values`
5. `env_allowlist` (resolved environment snapshot)
6. `env_allowlist_hash`

## Resolution Order

Each setting resolves in this order:

1. Environment variable override.
2. Organization process rules.
3. User settings.
4. Hard default.

### Environment Variables

1. `ORKET_PROTOCOL_TIMEZONE`
2. `ORKET_PROTOCOL_LOCALE`
3. `ORKET_PROTOCOL_NETWORK_MODE`
4. `ORKET_PROTOCOL_ENV_ALLOWLIST`

### Process Rules Keys

1. `protocol_timezone`
2. `protocol_locale`
3. `protocol_network_mode`
4. `protocol_env_allowlist`

### User Settings Keys

1. `protocol_timezone`
2. `protocol_locale`
3. `protocol_network_mode`
4. `protocol_env_allowlist`

## Defaults

1. `timezone = UTC`
2. `locale = C.UTF-8`
3. `network_mode = off`
4. `protocol_env_allowlist = ""`

## Network Mode Contract

Allowed values:

1. `off`
2. `allowlist`

Invalid values fail fast with:

1. `E_NETWORK_MODE_INVALID:<detail>`

## Environment Allowlist Semantics

`protocol_env_allowlist` accepts comma-separated variable names.

Normalization behavior:

1. trim whitespace around tokens
2. remove empty tokens
3. deduplicate
4. sort lexicographically

Runtime snapshot behavior:

1. only variables present in process environment are captured
2. resulting `env_allowlist` map is key-sorted
3. `env_allowlist_hash` is derived from captured key/value pairs

## Runtime Surfaces

Controls are emitted into:

1. turn execution context
2. tool execution capsule fields
3. protocol receipt payloads
4. replay comparator state digest

## Settings API Surfaces

Settings metadata endpoints expose these keys:

1. `run_ledger_mode`
2. `protocol_timezone`
3. `protocol_locale`
4. `protocol_network_mode`
5. `protocol_env_allowlist`

Endpoints:

1. `GET /v1/system/runtime-policy/options`
2. `GET /v1/system/runtime-policy`
3. `POST /v1/system/runtime-policy`
4. `GET /v1/settings`
5. `PATCH /v1/settings`

## Compatibility Notes

1. `protocol_timezone` and `protocol_locale` are freeform strings.
2. `protocol_network_mode` is constrained to registry values.
3. `protocol_env_allowlist` remains a normalized CSV string in settings surfaces.
4. Turn context carries normalized structured values (`env_allowlist` map + hash).

## Validation Checklist

Before rollout:

1. verify default context emits `UTC`, `C.UTF-8`, `off`
2. verify env/process/user precedence is deterministic
3. verify invalid network mode fails with `E_NETWORK_MODE_INVALID`
4. verify `env_allowlist_hash` changes when captured env values change
5. verify receipts preserve control values in execution capsule

## Open Items

1. CI parity campaign gating remains pending operator baseline thresholds.
2. Network allowlist destination policy metadata is not yet surfaced in settings.
3. Deterministic clock-source artifact replay wiring remains pending.

## Operator Checklist

Before enabling strict protocol enforcement:
1. Run at least one replay campaign with `--strict` and capture output artifact JSON.
2. Confirm `run_ledger_mode` is intentionally set (`sqlite`, `protocol`, or `dual_write`).
3. Verify `protocol_network_mode` policy matches deployment expectations.
4. Verify `protocol_env_allowlist` does not contain secrets that should not be captured.
