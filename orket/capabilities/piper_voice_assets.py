"""Host Piper asset selection and the owned metadata input supplied to its CLI."""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread

side_effecting = True


@dataclass(frozen=True)
class PiperVoiceAsset:
    voice_id: str
    model_path: Path
    metadata_bytes: bytes
    sample_rate: int

    def metadata(self) -> dict[str, Any]:
        return {"schema_version": "piper_voice.v1", "voice_id": self.voice_id, "sample_rate": self.sample_rate,
                "source": "model_config.audio.sample_rate",
                "model_config_sha256": hashlib.sha256(self.metadata_bytes).hexdigest()}


def _paired_paths(model: Path) -> tuple[Path, Path]:
    return model.resolve(), model.with_suffix(model.suffix + ".json").resolve()


def voice_models(default_model: Path, voices_dir: Path | None) -> dict[str, Path]:
    # Keep the declared model/config pairing, including a caller's asset symlink.
    default = default_model.expanduser().absolute()
    if not default.is_file() or default.suffix.lower() != ".onnx":
        raise ValueError("E_PIPER_DEFAULT_MODEL_UNAVAILABLE")
    models = {default.stem: default}
    folded = {default.stem.casefold(): _paired_paths(default)}
    directories = [voices_dir.expanduser().absolute()] if voices_dir is not None else []
    if default.parent not in directories:
        directories.append(default.parent)
    for directory in directories:
        if not directory.is_dir():
            continue
        for candidate in sorted(directory.glob("*.onnx")):
            if not candidate.is_file():
                continue
            resolved = candidate.absolute()
            key = candidate.stem.casefold()
            if key in folded:
                if folded[key] != _paired_paths(resolved):
                    raise ValueError("E_PIPER_VOICE_AMBIGUOUS")
                continue
            folded[key] = _paired_paths(resolved)
            models[candidate.stem] = resolved
    return models


def resolve_voice(default_model: Path, voices_dir: Path | None, voice_id: str, expected_rate: int | None) -> PiperVoiceAsset:
    models = voice_models(default_model, voices_dir)
    requested = str(voice_id or "").strip().casefold()
    selected = next(((name, path) for name, path in models.items() if name.casefold() == requested), None)
    if requested and selected is None:
        raise ValueError("E_PIPER_VOICE_UNKNOWN")
    name, model = selected or next(iter(models.items()))
    try:
        metadata = model.with_suffix(model.suffix + ".json").read_bytes()
    except OSError as exc:
        raise ValueError("E_PIPER_MODEL_METADATA_UNAVAILABLE") from exc
    try:
        payload = json.loads(metadata.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("E_PIPER_MODEL_METADATA_INVALID") from exc
    audio = payload.get("audio") if isinstance(payload, dict) else None
    sample_rate = audio.get("sample_rate") if isinstance(audio, dict) else None
    if type(sample_rate) is not int or sample_rate <= 0:
        raise ValueError("E_PIPER_MODEL_METADATA_INVALID")
    if expected_rate is not None and expected_rate != sample_rate:
        raise ValueError("E_PIPER_SAMPLE_RATE_MISMATCH")
    return PiperVoiceAsset(name, model, metadata, sample_rate)


def sample_rate_expectation(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError as exc:
            raise ValueError("E_PIPER_SAMPLE_RATE_INVALID") from exc
    if type(value) is not int or value <= 0:
        raise ValueError("E_PIPER_SAMPLE_RATE_INVALID")
    return value


@asynccontextmanager
async def piper_config_snapshot(workspace: Path, metadata: bytes):
    root, folder = None, None

    def create():
        nonlocal root, folder
        root = workspace.resolve()
        # Retain acquisition before cancellation can discard the worker's return value.
        folder = Path(tempfile.mkdtemp(prefix=".orket-piper-", dir=root))
        config = folder / "model.onnx.json"
        config.write_bytes(metadata)
        return config

    def cleanup():
        if folder is not None:
            if root is None or not folder.resolve().is_relative_to(root):
                raise RuntimeError("E_PIPER_CONFIG_CLEANUP_OUTSIDE_WORKSPACE")
            shutil.rmtree(folder)

    try:
        yield await run_owned_thread(create, label="Piper config snapshot creation")
    finally:
        await run_owned_thread(cleanup, label="Piper config snapshot cleanup")
