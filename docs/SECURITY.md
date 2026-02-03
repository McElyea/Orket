# Orket Security Model

This document describes Orket’s operational and code security expectations.

## FilesystemPolicy

The filesystem model defines:

- reference spaces  
- workspace  
- domain  
- allowed read paths  
- allowed write paths  
- forbidden paths  

Policies are explicit and declarative.

## Write Policy

Write operations must:

- validate paths  
- respect allowed write locations  
- produce write receipts  
- log timestamp, path, and byte count  

## Tool Dispatcher Safety

The dispatcher enforces:

- Band‑level tool permissions  
- FilesystemPolicy rules  
- path normalization  
- path traversal protection  
- structured error reporting  

All tool calls must go through the dispatcher.

## Path Validation

Paths must be:

- absolute  
- normalized  
- inside allowed spaces  

No relative traversal is permitted.

## Agent Sandboxing Expectations

Agents:

- cannot bypass dispatcher  
- cannot write outside allowed spaces  
- cannot invoke tools not listed in tools_allowed  
- cannot escalate privileges  

## Logging and Auditability

All Sessions include:

- ordered messages  
- tool calls  
- timestamps  
- write receipts  

This ensures full traceability.
