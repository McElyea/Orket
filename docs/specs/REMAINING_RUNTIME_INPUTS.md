# Agent configuration, journal and epic calendar inputs

Status: Active contract for the 0.6.52 candidate
Last updated: 2026-09-20
Owner: Orket Core

`Agent` captures its provider model name and model-family match at construction.
Its optional `environment` mapping is authoritative, including an empty mapping;
otherwise application construction observes the process environment. Later role
reads, environment changes and provider-name changes cannot select a different
dialect for that Agent. A new Agent is required to adopt new configuration.

`ModelFamilyRegistry.from_config` consumes only its explicit structured value.
An absent value selects built-in defaults. Operator environment decoding uses
`from_environment(environment)` with an explicit mapping. Malformed JSON raises
`E_MODEL_FAMILY_PATTERNS_JSON`; it no longer silently selects defaults. Existing
structured pattern normalization, aliases, ordering and generic fallback remain.
The generic fallback remains observable through the existing Agent warning.

At `Agent.run` entry, application captures the selected turn clock and any supplied
journal publication timestamp. A supplied timestamp retains its existing meaning
as caller-provided publication data. Otherwise each completed or failed direct
tool invocation obtains a fresh publication observation from the selected clock.
Journal construction consumes that explicit string and has no ambient clock
fallback. Clock failure after an effect propagates; it does not fabricate a receipt
or roll back the effect. This does not expand legacy direct-tool admission or claim
canonical governed dispatch, durable journaling or hostile-code containment.

Epic owner construction captures an immutable `EosSprintBaseline`. A supplied
`RuntimeConstructionInputs.environment` is authoritative; direct pipeline
construction without that snapshot observes the environment at owner construction.
Direct `EpicRunOrchestrator` construction can inject a baseline and otherwise uses
the immutable built-in baseline. No process-global EOS cache supplies this path.

Epic setup obtains UTC from its selected `RuntimeInputService`, converts that
observation to host local time in application, and calculates one sprint before
asset-read awaits. `EpicRunSetup.calendar_sprint` carries the result into each new
card payload. Local calendar semantics and the existing pure baseline calculation
are preserved. Existing cards retain their stored sprint. A later recovery/setup
entry takes a new observation for newly created cards; this is not a historical
calendar migration or a run-wide durable calendar snapshot.

Published calendar parity also retains the existing `TypeError` for naive datetime
arguments. This checkpoint does not add naive-datetime support.

These contracts do not freeze every Agent context field or all pipeline routing
and child configuration. Governed authority, completion and lifetime requirements
remain unchanged. The architectural-truth plan owns measured proof and blockers.
