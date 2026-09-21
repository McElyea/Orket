# Agent configuration, journal and epic calendar inputs

Status: Active contract for the 0.6.53 candidate
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

Epic owner construction captures an immutable `EosSprintBaseline` and the
`ORKET_TIMEZONE` name from one environment snapshot. A supplied
`RuntimeConstructionInputs.environment` is authoritative, including an empty
mapping; direct pipeline construction without it observes the environment at owner
construction. Direct `EpicRunOrchestrator` construction can inject a baseline and
`calendar_timezone_name`; defaults are the built-in baseline and UTC. No
process-global EOS cache supplies this path.

Epic setup obtains UTC from its selected `RuntimeInputService` before its first
await. The existing `configured_timezone` resolver runs in an owned worker, then
application converts that captured observation and calculates one sprint before
asset reads. This preserves configured timezone semantics: absent/empty values
mean UTC, MST is fixed UTC-7, and unknown zones retain the resolver's UTC fallback.
Repeated cancellation and timeout retain worker ownership until it settles;
worker failure propagates before assets or card publication. No universal timezone
I/O deadline is asserted. `EpicRunSetup.calendar_sprint` carries the result into
each new card payload. Existing cards retain their stored sprint. A later
recovery/setup entry observes a new value for newly created cards; this is not a
historical calendar migration or a run-wide durable calendar snapshot.

Version 0.6.52 incorrectly used the host timezone. Its pure calendar parity checks
did not cover timezone selection. Version 0.6.53 corrects that regression and this
contract; historical .52 evidence is retained, and stored cards are not rewritten.

Published calendar parity also retains the existing `TypeError` for naive datetime
arguments. This checkpoint does not add naive-datetime support.

These contracts do not freeze every Agent context field or all pipeline routing
and child configuration. Governed authority, completion and lifetime requirements
remain unchanged. The architectural-truth plan owns measured proof and blockers.
