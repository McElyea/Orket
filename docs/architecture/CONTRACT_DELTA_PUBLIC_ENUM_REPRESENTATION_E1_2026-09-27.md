# Public enum representation preservation

## Summary

- Owner: Orket Core
- Date: 2026-09-27
- Status: Applied compatibility preservation; broader acceptance pending
- Contract: [Public enum representation](../specs/PUBLIC_ENUM_REPRESENTATION_CONTRACT.md)

## Delta

Current public string-backed enums render diagnostic text as `ClassName.MEMBER`
and serialize declared string values. Ruff reports 52 `UP042` declarations.
Automatically converting them to `StrEnum` changes diagnostic text and formatting.

The change makes the existing representation an explicit durable contract,
adds meaningful member/reexport/model controls, and records exactly 52 declaration-
local exceptions. Runtime behavior, enum definitions, values, import identity,
and all other Ruff rule admission remain unchanged. This is an intentional lint
disposition preserving compatibility, not a claim that 52 runtime defects were fixed.

## Migration and validation

1. Review the exact source-hash inventory and contract before applying exceptions.
2. Apply only declaration comments, the contract controls and this authority.
3. Run contract controls on Windows 3.11 and 3.12 and canonical Ruff. Retain a
   negative control proving naive `StrEnum` replacement fails diagnostic assertions.
4. Add this active spec to shared authority only after acceptance; retain original
   Ruff debt receipts and distinguish intentional exemptions in the E1 closeout.

No compatibility window is needed because runtime representations do not change.
Future representation changes require a separate explicit migration contract.

## Rollback and versioning

Remove the exceptions and preserve the controls if this disposition is rejected;
Ruff will again report the known declarations. There is no persisted-state change.
A patch release may record the accepted compatibility clarification and controls.
The root candidate owns the effective version and shared authority update.

## Proof posture

The source Windows Python 3.11 contract cohort passed all 63 cases. All 52 temporary
`StrEnum` replacements were rejected by the diagnostic-text assertion. Exact source
AST comparison confirms the declaration comments change no runtime body and add no
lines to existing modules. The test file was Ruff-formatted and passed scoped Ruff.
Windows Python 3.12, installed v108, final canonical Ruff and full Quality acceptance
remain pending. Local serialization controls do not establish runtime lifecycle,
external-provider or hosted CI truth. Proof receipts remain under
`.tmp/goal-20260927-quality/v108/enum-proposal/`.
