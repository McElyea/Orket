# Public enum representation contract

Status: Active
Owner: Orket Core
Date: 2026-09-27

## Existing public behavior

The retained string-backed enum declarations have two observable representations.
Diagnostic conversion through `str(member)`, an ordinary f-string and string-format
alignment uses `ClassName.MEMBER_NAME`. `repr(member)` uses
`<ClassName.MEMBER_NAME: value_repr>`. String equality and hashing, native JSON,
and Pydantic JSON use the declared string value. Parsing that value recovers the
same canonical enum member. Existing reexports retain the defining enum type's
identity; they do not create replacement enum types.

This contract preserves these behaviors. It does not redefine member names,
values or lifecycle semantics: those remain owned by the declaring modules and
the [control-plane enum authority](00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md).

## Bounded compatibility scope

The scope is the 52 existing enum declarations across these modules:

| Declaring module | Declarations |
| --- | ---: |
| `orket.core.domain.control_plane_enums` | 37 |
| `orket.core.domain.orket_manifest` | 1 |
| `orket.core.domain.sandbox` | 2 |
| `orket.core.domain.sandbox_cleanup` | 1 |
| `orket.core.domain.sandbox_lifecycle` | 6 |
| `orket.core.domain.workitem_transition` | 1 |
| `orket.core.types` | 3 |
| `orket.streaming.model_provider` | 1 |

`tests/contracts/test_public_enum_representation.py` names every scoped declaration,
checks every actual member without copying value definitions, and checks identity
through existing `orket.core.domain`, `orket.schema` and `orket.streaming` reexports.
It also checks card, transition-result and provider-event JSON boundaries.

## Lint disposition and change control

Each scoped declaration may carry a declaration-local `noqa: UP042` with a public
representation rationale. `UP042` stays enabled everywhere else. There is no file
or global rule exemption, replacement base class, or compatibility shim. Adding
an exception requires reviewing the public contract and explicit test inventory;
new enum declarations do not inherit permission from this document.

A naive `StrEnum` conversion changes diagnostic conversion to the underlying
string value, even while JSON values remain equal. That is a contract change
requiring an explicit migration decision. [Ruff documents this unsafe-fix
behavior](https://docs.astral.sh/ruff/rules/replace-str-enum/), and [Python's
StrEnum reference](https://docs.python.org/3.11/library/enum.html#enum.StrEnum)
defines its string conversion. Preserving JSON alone is insufficient acceptance.

## Verification and limits

Run the marked contract tests on supported Windows Python 3.11 and 3.12, canonical
Ruff, and a control showing that replacing a scoped enum with `StrEnum` is detected
by the representation assertion. Report intentional exceptions separately from
corrected Ruff defects. The tests establish Python representation and local model
serialization; they do not prove runtime lifecycle execution, providers, Docker,
or hosted Quality acceptance. This document does not close those gates.
