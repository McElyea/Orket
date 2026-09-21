# Kernel control-plane publication inputs

Status: Active contract for the 0.6.57 candidate
Last updated: 2026-09-20

Each asynchronous public kernel admission, commit and session-end invocation
captures its request before calling the kernel or awaiting publication. Session,
trace, proposal, result claims and operator/attestation values used after a wait
remain the values selected at invocation entry.

Each direct control-plane admission, commit and session-end publication captures
its request, response and ledger items before its first await. Collection uses
the existing SDK immutable JSON value and produces detached, operation-owned
views for application effects. Nested caller mutations cannot replace proposal
or policy snapshots, change a commit result, supply later execution evidence,
or rewrite selected receipt digests and timestamps.

These boundaries accept JSON payloads. Non-finite numbers and unsupported object
types are refused by the existing immutable JSON codec before publication;
they are not replaced with fabricated values. Existing stable JSON inputs,
kernel digest rules, namespace checks, retry guards and terminal classifications
retain their behavior. Capture does not validate that a caller-supplied receipt
is authentic or enlarge the authority of that caller.

This contract does not make kernel in-memory state durable, make multiple stores
transactional, roll back prior kernel events, or reclassify claimed output as an
independently observed effect. Failure and cancellation preserve the existing
authority and ownership semantics. Other kernel clocks and runtime inputs remain
separate D obligations.

Acceptance retains before-change real-SQLite counterexamples for changed
admission snapshots, false-success commit publication and changed closeout time,
then proves both direct publication and the public engine path against held
repository operations. Source and installed proof also retain stable-input,
namespace, retry, recovery and terminal-authority regressions.
