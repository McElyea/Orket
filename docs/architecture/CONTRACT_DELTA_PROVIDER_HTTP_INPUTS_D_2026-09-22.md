# Provider HTTP catalog input and construction ownership

Owner: Codex for Orket Core
Date: 2026-09-22
Status: Scoped implementation contract; acceptance remains in the canonical plan

Six actual origin/proxy TCP controls fail on source and the byte-verified v0.6.90
wheel: supplied empty, proxy and bypass mappings lose to ambient proxy settings.
Two ambient-default controls pass. Preserve all opening observations.

For intended patch 0.6.91, propagate captured environment/cwd through HTTP catalog
entry, compile proxy mounts explicitly, and construct verified TLS/client resources
in an owned native worker. Retain acquired resources and close them through repeated
interruption. The existing shared worker/cleanup owner remains authoritative.
Declare certifi directly because native trust construction now imports its public
bundle API; its previously transitive HTTPX requirement remains unconstrained.

Durable contract: `docs/specs/PROVIDER_HTTP_CATALOG_INPUTS.md`. Migration: supplied
empty mappings no longer inherit ambient network settings; registry-only proxies
require explicit environment configuration; unsupported NO_PROXY CIDR and non-finite
HTTP budgets fail explicitly. Default captured environment, verified TLS, one-second
minimum, redirects, parsing and provider-selection behavior remain authoritative.

Pre-publication review found that manual SSLContext construction omits Python 3.13's
STRICT/PARTIAL_CHAIN defaults. Two controlled-policy real TLS probes fail the first
candidate; retain that candidate's1663-case source pass as intermediate evidence.
Preserve host-version verification flags and use compliant public positive fixtures;
the original legacy chain remains a negative control. Controlled 3.13-style flags
on actual Windows3.11/3.12 handshakes are not installed Python3.13 acceptance.

Validate actual proxy/origin and TLS requests, captured-input drift, native setup
responsiveness, interrupted construction/request/close, failure precedence and
installed artifacts. Synthetic parser checks are structural proof only. No fixture
catalog establishes actual model inference or CAP acceptance. Revert implementation
and authority together if acceptance fails; retain all observations. No lane
retirement, Linux clock repair, full D/E/CAP or release readiness follows.
