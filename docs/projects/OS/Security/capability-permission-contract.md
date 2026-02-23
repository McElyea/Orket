# Capability Permission Contract (v1)

Last updated: 2026-02-22
Status: Normative

## Enforcement Model
1. Deny-by-default for all undeclared permissions.
2. Capability resolution occurs before tool execution.
3. Permission checks occur before stage promotion.

## Audit Requirements
1. Every deny decision must include deterministic code and location.
2. Every allow decision must include capability source/version metadata.

## Failure Codes
1. `E_CAPABILITY_NOT_RESOLVED`
2. `E_PERMISSION_DENIED`
3. `E_SIDE_EFFECT_UNDECLARED`
