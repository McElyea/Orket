# Contract delta: adapter effect classification enforcement

Date: 2026-09-22
Change classification: breaking
Runtime modes: all
Migration requirement: required

## Contract

`docs/specs/ADAPTER_EFFECT_CLASSIFICATION.md` settles the declaration boundary for
all policy-classified adapter modules. Module-level literal booleans bound exported
behavior; existing class declarations cannot weaken that bound. Read-only `False`
does not mean deterministic or free of external observation.

The dependency checker must reject absent or invalid declarations and listed
decision-node adapter targets that lack a valid read-only declaration or reach an
effectful/unclassified adapter. Existing import exceptions do not waive this gate.
The decision adapter list remains empty. Explicit decision-context requirements and
all existing runtime acceptance conditions remain unchanged.

## Migration

- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`

Declare each adapter module's conservative effect bound in its source, including
initializers and reexports. Preserve class-specific declarations and review mixed
surfaces as effectful. Tooling fixtures must supply declarations when testing a
passing adapter dependency; negative controls deliberately omit or invalidate them.

## Verification and limits

Native checker counterexamples and the canonical plan bind acceptance. Declaration
validation is structural proof; preserved real runtime tests establish only their
existing scopes. Full async reachability, actual classification truth, explicit
decision inputs, Linux acceptance, E/CAP and lane acceptance remain separate work.
