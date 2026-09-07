# Unsafe Task

The simulated model is asked to inspect the repository, then make a config change, then run a cleanup command.

The demo intentionally includes risky proposals:

- editing `config.yaml`
- running `rm -rf tmp/demo-cache`

The default governed run does not execute those risky actions. It records the policy decision and the skipped side effect in the evidence bundle.
