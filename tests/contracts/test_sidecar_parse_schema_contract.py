from __future__ import annotations

from pathlib import Path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_sidecar_parse_schema_contract_tokens() -> None:
    path = Path("docs/specs/SIDECAR_PARSE_SCHEMA.md")
    assert path.exists(), f"Missing schema doc: {path}"
    text = _read(path)

    required_tokens = [
        "sidecar.parse.v1",
        "vram_total_mb",
        "vram_used_mb",
        "ttft_ms",
        "prefill_tps",
        "decode_tps",
        "thermal_start_c",
        "thermal_end_c",
        "kernel_launch_ms",
        "model_load_ms",
        "sidecar_parse_status",
        "sidecar_parse_errors",
        "OPTIONAL_FIELD_MISSING",
        "NOT_APPLICABLE",
        "REQUIRED_FIELD_MISSING",
        "PARSE_ERROR",
    ]
    missing = [token for token in required_tokens if token not in text]
    assert not missing, f"Missing sidecar parse schema tokens: {missing}"

