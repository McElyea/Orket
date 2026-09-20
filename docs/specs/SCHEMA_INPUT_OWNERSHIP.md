# Schema input ownership

Last updated: 2026-09-20
Status: Active contract for the 0.6.45 implementation candidate
Owner: Orket Core

`orket.schema` validates supplied values. Card identities (including roles and
card-detail trees) and verification-scenario identities are required inputs. Core
validation does not observe an identity generator or emit warnings. Equal complete
inputs produce equal values. Existing identity strings are preserved, including
legacy short scenario identities; this transition does not strengthen uniqueness
or rewrite historical records.

Application-owned authored asset admission uses
`orket.application.services.schema_input_service.validate_config_asset` or its
JSON counterpart. It obtains absent identities through `RuntimeInputService`
before core validation. Cards retain the prior UUID4 hexadecimal format; scenarios
retain the prior four-character UUID prefix. An explicitly supplied value, including
an invalid value, is never replaced. Generation failure is an admission failure.

The host follows model field types and validation aliases through nested models,
lists, dictionaries and optional models. It handles epic issue aliases, nested
verification scenarios, typed root models, role maps and recursive card-detail children. Arbitrary
parameter dictionaries are not schema objects. Ambiguous model unions and custom
validation aliases do not acquire guessed identities; normal validation applies.
Cycles in the typed schema input are rejected with `E_SCHEMA_ASSET_CYCLE`; repeated
objects at separate non-cyclic positions remain distinct admissions. Input
mappings are not mutated. A caller retaining generated identities persists
the validated result. Loading the same identity-free authored asset twice remains
two admissions, with new identities as before; no stable identity or replay claim
is inferred from the filename.

`ConfigLoader` uses this admission boundary for authored assets. Prompt role
validation/resolution also uses it. Revalidation of stored, accepted core values
uses the core model directly and cannot silently invent a missing historical ID.
Callers migrating incomplete stored values must supply their authoritative IDs or
explicitly author a new value; automatic historical repair is unsupported.

Environment models reject unknown keys without warning effects. The authoritative
environment payload helper retains its `E_ENVIRONMENT_CONFIG_UNKNOWN_KEYS` error;
direct model construction uses Pydantic's extra-field validation error. The former
non-authoritative warn-and-drop behavior is retired. Remove obsolete keys or place
supported provider options in `params`; do not silently drop a failed input.

This is a schema/input contract. It does not make every model immutable, establish
global uniqueness for short IDs, authorize effects, or close remaining D decision
context, adapter classification and asynchronous ownership obligations.
