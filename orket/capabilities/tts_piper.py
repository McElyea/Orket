from __future__ import annotations

import importlib.util
import math
import os
import shlex
import shutil
import sys
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_command_limits import MAX_OUTPUT_LIMIT
from orket.adapters.execution.owned_io import require_sync_context, run_owned_thread
from orket.capabilities.piper_voice_assets import (
    PiperVoiceAsset,
    piper_config_snapshot,
    resolve_voice,
    sample_rate_expectation,
    voice_models,
)
from orket.capabilities.sync_bridge import run_coro_sync
from orket.core.contracts.owned_command import CommandExecutionUncertain, CommandRunner, OwnedCommandResult
from orket_extension_sdk.audio import AudioClip, NullTTSProvider, TTSProvider, VoiceInfo


@dataclass(frozen=True)
class PiperConfig:
    model_path: Path
    voices_dir: Path | None = None
    executable: str = "piper"
    sample_rate: int | None = None
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "sample_rate", sample_rate_expectation(self.sample_rate))
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("E_PIPER_TIMEOUT_INVALID")


class PiperSynthesisError(RuntimeError):
    def __init__(self, result: OwnedCommandResult):
        super().__init__(f"E_PIPER_SYNTHESIS_FAILED: {result.reason}; exit={result.returncode}")
        self.lifetime = result


@dataclass(frozen=True)
class PiperSynthesisResult:
    clip: AudioClip
    voice: PiperVoiceAsset
    command: OwnedCommandResult | None


class PiperTTSProvider:
    """Piper-backed TTS provider using local CLI invocation."""

    def __init__(self, config: PiperConfig, *, command_runner: CommandRunner, workspace: Path) -> None:
        self._workspace = workspace.absolute()
        self._config = replace(config, model_path=self._workspace / config.model_path.expanduser(),
            voices_dir=self._workspace / config.voices_dir.expanduser() if config.voices_dir is not None else None)
        self._command_runner = command_runner
        self._emotion_speed = {
            "neutral": 1.0,
            "defensive": 1.15,
            "evasive": 0.9,
            "uncertain": 0.95,
        }

    @property
    def config(self) -> PiperConfig:
        return self._config

    def list_voices(self) -> list[VoiceInfo]:
        require_sync_context(code="E_PIPER_DISCOVERY_REQUIRES_ASYNC_OWNER")
        if not self._resolve_executable(self._config.executable):
            return []
        voices: list[VoiceInfo] = []
        for voice_id in voice_models(self._config.model_path, self._config.voices_dir):
            voices.append(VoiceInfo(voice_id=voice_id, display_name=voice_id, language="und", tags=["piper"]))
        return voices

    def synthesize(
        self,
        text: str,
        voice_id: str,
        emotion_hint: str = "neutral",
        speed: float = 1.0,
    ) -> AudioClip:
        require_sync_context(code="E_SYNC_COROUTINE_REQUIRES_ASYNC_OWNER")
        return run_coro_sync(self.synthesize_async(text, voice_id, emotion_hint, speed)).clip

    async def synthesize_async(
        self, text: str, voice_id: str, emotion_hint: str = "neutral", speed: float = 1.0,
    ) -> PiperSynthesisResult:
        voice, exe_cmd = await run_owned_thread(
            lambda: (resolve_voice(self._config.model_path, self._config.voices_dir, voice_id, self._config.sample_rate),
                     self._resolve_executable(self._config.executable)),
            label="Piper model and executable discovery",
        )
        if not str(text or "").strip():
            return PiperSynthesisResult(AudioClip(sample_rate=voice.sample_rate, channels=1, samples=b""), voice, None)
        if not exe_cmd:
            raise RuntimeError(f"Piper executable not found: {self._config.executable}")

        emotion = str(emotion_hint or "neutral").strip().lower()
        emotion_factor = float(self._emotion_speed.get(emotion, 1.0))
        combined_speed = max(0.5, min(2.0, float(speed) * emotion_factor))
        # Piper uses inverse speed via length scale. Lower length_scale = faster speech.
        length_scale = max(0.5, min(2.0, 1.0 / combined_speed))
        cmd = [
            *exe_cmd,
            "--model",
            str(voice.model_path),
            "--output-raw",
            "--length_scale",
            f"{length_scale:.4f}",
        ]
        async with piper_config_snapshot(self._workspace, voice.metadata_bytes) as config:
            proc = await self._command_runner.run(
                [*cmd, "--config", str(config)], cwd=self._workspace, timeout_seconds=self._config.timeout_seconds,
                input_data=str(text).encode("utf-8"),
                # PCM needs more than the verifier's 4 MiB text-stream default; retain a finite audio bound.
                output_limit_bytes=MAX_OUTPUT_LIMIT,
            )
        if not proc.cleanup_confirmed:
            raise CommandExecutionUncertain(proc)
        if proc.reason != "completed" or proc.returncode != 0 or not proc.capture_complete:
            raise PiperSynthesisError(proc)
        return PiperSynthesisResult(
            AudioClip(sample_rate=voice.sample_rate, channels=1, samples=bytes(proc.stdout), format="pcm_s16le"), voice, proc,
        )

    @staticmethod
    def _resolve_executable(value: str) -> list[str]:
        raw = str(value or "").strip()
        if not raw:
            return []
        tokens = [token[1:-1] if token.startswith('"') and token.endswith('"') else token
                  for token in shlex.split(raw, posix=False)]
        if not tokens:
            return []

        first_token = str(tokens[0]).strip()
        resolved = shutil.which(first_token)
        if resolved:
            return [resolved, *tokens[1:]]

        first_path = Path(first_token).expanduser()
        if first_path.is_file():
            return [str(first_path), *tokens[1:]]

        # Windows environments can have piper-tts installed without a `piper` shim on PATH.
        if first_token.lower() == "piper" and len(tokens) == 1 and importlib.util.find_spec("piper") is not None:
            return [sys.executable, "-m", "piper"]
        return []


def build_tts_provider(
    *, input_config: dict[str, Any], command_runner: CommandRunner | None = None, workspace: Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> TTSProvider:
    observed = os.environ if environment is None else environment
    backend = str(input_config.get("tts_backend") or observed.get("ORKET_TTS_BACKEND", "null")).strip().lower()
    if backend == "null":
        return NullTTSProvider()
    if backend != "piper":
        raise ValueError("E_TTS_BACKEND_UNSUPPORTED")
    model_path_raw = str(input_config.get("tts_model_path") or observed.get("ORKET_TTS_PIPER_MODEL_PATH", "")).strip()
    voices_dir_raw = str(input_config.get("tts_voices_dir") or observed.get("ORKET_TTS_PIPER_VOICES_DIR", "")).strip()
    executable = str(input_config.get("tts_executable") or observed.get("ORKET_TTS_PIPER_BIN", "piper")).strip() or "piper"
    sample_rate = sample_rate_expectation(input_config.get("tts_sample_rate", observed.get("ORKET_TTS_SAMPLE_RATE")))
    if not model_path_raw:
        raise ValueError("E_PIPER_MODEL_REQUIRED")
    if command_runner is None or workspace is None:
        raise ValueError("E_PIPER_COMMAND_OWNER_REQUIRED")
    model_path = Path(model_path_raw).expanduser()
    voices_dir = Path(voices_dir_raw).expanduser() if voices_dir_raw else model_path.parent
    return PiperTTSProvider(
        PiperConfig(
            model_path=model_path,
            voices_dir=voices_dir,
            executable=executable,
            sample_rate=sample_rate,
            timeout_seconds=float(input_config.get("tts_timeout_seconds", observed.get("ORKET_TTS_TIMEOUT_SECONDS", "120"))),
        ),
        command_runner=command_runner,
        workspace=workspace,
    )
