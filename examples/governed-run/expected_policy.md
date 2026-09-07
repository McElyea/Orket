# Expected Policy

This scenario uses the smallest governed-run policy:

- `read`, `list`, and `inspect` actions are allowed as read-only observations.
- `write`, `edit`, and `delete` actions require human approval and are not executed by the deterministic demo.
- shell commands are denied unless the exact command is in `shell_allowlist`.
- network actions are denied by default.
- unknown actions are denied by default.

For `scenario.yaml`, the expected decisions are:

- `inspect-files`: allowed
- `edit-config`: approval required, no side effect
- `run-shell-command`: denied, no side effect
