from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _default_schema_path() -> Path:
    return Path(__file__).resolve().parents[2] / "docs" / "specs" / "companion-provider-runtime-matrix.schema.json"


def _default_input_path() -> Path:
    return Path(__file__).resolve().parents[2] / "benchmarks" / "results" / "companion" / "provider_runtime_matrix" / "companion_provider_runtime_matrix.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Companion provider/runtime matrix JSON against schema contract.",
    )
    parser.add_argument("--input", default=str(_default_input_path()), help="Path to matrix JSON artifact.")
    parser.add_argument("--schema", default=str(_default_schema_path()), help="Path to matrix schema JSON file.")
    return parser


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def validate_matrix_payload(*, payload: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    messages: list[str] = []
    for error in errors:
        path_tokens = [str(token) for token in list(error.path)]
        path = ".".join(path_tokens) if path_tokens else "<root>"
        messages.append(f"{path}: {error.message}")
    return messages


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    input_path = Path(str(args.input)).resolve()
    schema_path = Path(str(args.schema)).resolve()
    if not input_path.exists():
        raise SystemExit(f"E_COMPANION_MATRIX_VALIDATE_INPUT_MISSING: {input_path}")
    if not schema_path.exists():
        raise SystemExit(f"E_COMPANION_MATRIX_VALIDATE_SCHEMA_MISSING: {schema_path}")

    payload = _load_json_object(input_path)
    schema = _load_json_object(schema_path)
    errors = validate_matrix_payload(payload=payload, schema=schema)
    if errors:
        print("matrix-validation=invalid")
        for message in errors:
            print(f"- {message}")
        return 1
    print("matrix-validation=valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
