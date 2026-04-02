# Extension And Client Boundary Requirements
Last updated: 2026-04-01
Status: Completed archived draft packet requirements authority
Owner: Orket Core
Packet role: Stage 4

## Purpose

Define how Packet 2 keeps extensions and clients thin over host-owned runtime authority.

## Draft requirements

1. Extensions and client-facing repos must remain consumers of host-owned runtime contracts, not alternate authority centers.
2. Validation, packaging, runtime invocation, and operator surfaces must keep the host as the source of truth for execution state.
3. Client-friendly transport may exist, but must project host-owned state rather than mint local truth.
4. Packet 2 must preserve compatibility with the Packet 1 extension validation posture.
5. Product-facing repos may specialize UX, but not runtime authority.

## Non-goals

1. marketplace or cloud distribution
2. client-specific product roadmaps
3. moving session or execution authority into a BFF or frontend repo
