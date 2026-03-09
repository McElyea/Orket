# External Extension Template

Copy this template into a new repository and update:
1. `extension_id`
2. package name in `pyproject.toml`
3. workload ids and entrypoints
4. script defaults and ports

Validation commands:
1. `python -m orket_extension_sdk.validate . --json`
2. `python -m orket_extension_sdk.import_scan src --json`
3. `orket ext validate . --json`
