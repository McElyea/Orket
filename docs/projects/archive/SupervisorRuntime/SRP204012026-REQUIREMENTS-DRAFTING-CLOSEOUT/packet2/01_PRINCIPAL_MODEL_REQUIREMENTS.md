# Principal Model Requirements
Last updated: 2026-04-01
Status: Completed archived draft packet requirements authority
Owner: Orket Core
Packet role: Stage 1

## Purpose

Define the first-class principal model Packet 2 will use across runtime, control-plane, operator, and client surfaces.

## Draft requirements

1. Packet 2 must define one explicit principal family covering `human_operator`, `model`, `scheduler`, `rule_engine`, `extension`, and `external_service`.
2. Principal identity must remain visible at admission, mutation, reconciliation, and closure surfaces where the acting authority matters.
3. Principal type must not, by itself, grant mutation or resume authority; capability and policy still govern privileged actions.
4. Extension and client repos may act as principals only through host-owned contracts, not as hidden runtime authority centers.
5. Principal framing must stay compatible with the active Packet 1 operator and session specs.

## Non-goals

1. human-account product design
2. full tenancy or identity-provider integration
3. broad authn or authz implementation planning
