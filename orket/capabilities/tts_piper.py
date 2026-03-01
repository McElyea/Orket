from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket_extension_sdk.audio import AudioClip, NullTTSProvider, TTSProvider, VoiceInfo


@dataclass(frozen=True)
class PiperConfig:
    model_path: Path
    executable: str = "piper"
    sample_rate: int = 22050


class PiperTTSProvider:
    """Piper-backed TTS provider using local CLI invocation."""

    def __init__(self, config: PiperConfig) -> None:
        self._config = config
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
        voice_id = self._config.model_path.stem
        return [VoiceInfo(voice_id=voice_id, display_name=voice_id, language="und", tags=["piper"])]

    def synthesize(
        self,
        text: str,
        voice_id: str,
        emotion_hint: str = "neutral",
        speed: float = 1.0,
    ) -> AudioClip:
        if not str(text or "").strip():
            return AudioClip(sample_rate=self._config.sample_rate, channels=1, samples=b"", format="pcm_s16le")
        if not self._config.model_path.exists():
            raise RuntimeError(f"Piper model file not found: {self._config.model_path}")
        exe = self._resolve_executable(self._config.executable)
        if not exe:
            raise RuntimeError(f"Piper executable not found: {self._config.executable}")

        emotion = str(emotion_hint or "neutral").strip().lower()
        emotion_factor = float(self._emotion_speed.get(emotion, 1.0))
        combined_speed = max(0.5, min(2.0, float(speed) * emotion_factor))
        # Piper uses inverse speed via length scale. Lower length_scale = faster speech.
        length_scale = max(0.5, min(2.0, 1.0 / combined_speed))
        cmd = [
            exe,
            "--model",
            str(self._config.model_path),
            "--output-raw",
            "--length_scale",
            f"{length_scale:.4f}",
        ]
        try:
            proc = subprocess.run(
                cmd,
                input=str(text).encode("utf-8"),
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            raise RuntimeError(f"Piper execution failed: {exc}") from exc
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"Piper synthesis failed (voice_id={voice_id}): {stderr.strip()}")
        return AudioClip(sample_rate=self._config.sample_rate, channels=1, samples=bytes(proc.stdout), format="pcm_s16le")

    @staticmethod
    def _resolve_executable(value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        return shutil.which(raw) or raw


def build_tts_provider(*, input_config: dict[str, Any]) -> TTSProvider:
    backend = str(input_config.get("tts_backend") or os.getenv("ORKET_TTS_BACKEND", "null")).strip().lower()
    if backend != "piper":
        return NullTTSProvider()
    model_path_raw = str(
        input_config.get("tts_model_path")
        or os.getenv("ORKET_TTS_PIPER_MODEL_PATH", "")
    ).strip()
    executable = str(input_config.get("tts_executable") or os.getenv("ORKET_TTS_PIPER_BIN", "piper")).strip() or "piper"
    sample_rate = int(input_config.get("tts_sample_rate") or os.getenv("ORKET_TTS_SAMPLE_RATE", "22050") or 22050)
    if not model_path_raw:
        return NullTTSProvider()
    model_path = Path(model_path_raw).expanduser()
    if not model_path.exists():
        return NullTTSProvider()
    if not shutil.which(executable) and not Path(executable).exists():
        return NullTTSProvider()
    return PiperTTSProvider(PiperConfig(model_path=model_path, executable=executable, sample_rate=sample_rate))

