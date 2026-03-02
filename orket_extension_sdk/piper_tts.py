from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .audio import AudioClip, VoiceInfo

try:
    from piper import PiperVoice, SynthesisConfig
except ImportError:
    PiperVoice = None  # type: ignore[assignment,misc]
    SynthesisConfig = None  # type: ignore[assignment,misc]


_DEFAULT_VOICES_DIR = Path(__file__).resolve().parents[1] / "data" / "voices"


@dataclass
class PiperTTSProvider:
    """SDK TTSProvider backed by Piper (local neural TTS).

    Implements the TTSProvider protocol from orket_extension_sdk.audio.
    Each voice_id maps to a Piper ONNX model file in voices_dir.
    """

    voices_dir: Path = _DEFAULT_VOICES_DIR
    _loaded: dict[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if PiperVoice is None:
            raise RuntimeError(
                "piper-tts is not installed. Install with: pip install piper-tts"
            )
        self.voices_dir = Path(self.voices_dir)

    def _voice_for(self, voice_id: str) -> Any:
        """Load and cache a PiperVoice by voice_id."""
        if voice_id in self._loaded:
            return self._loaded[voice_id]

        model_path = self._resolve_model(voice_id)
        if model_path is None:
            raise FileNotFoundError(
                f"No Piper model found for voice_id '{voice_id}' in {self.voices_dir}"
            )
        voice = PiperVoice.load(str(model_path))
        self._loaded[voice_id] = voice
        return voice

    def _resolve_model(self, voice_id: str) -> Path | None:
        """Find the ONNX model file for a voice_id.

        Tries exact match first, then scans for partial match.
        """
        # Exact: voices_dir/{voice_id}.onnx
        exact = self.voices_dir / f"{voice_id}.onnx"
        if exact.exists():
            return exact

        # Scan for files containing the voice_id
        for candidate in sorted(self.voices_dir.glob("*.onnx")):
            if candidate.suffix == ".json":
                continue
            if voice_id in candidate.stem:
                return candidate

        # If only one model exists, use it as fallback
        models = [p for p in self.voices_dir.glob("*.onnx") if not p.name.endswith(".json")]
        if len(models) == 1:
            return models[0]

        return None

    def synthesize(
        self,
        text: str,
        voice_id: str,
        emotion_hint: str = "neutral",
        speed: float = 1.0,
    ) -> AudioClip:
        """Synthesize speech using Piper neural TTS.

        Speed is mapped to Piper's length_scale (inverted: higher speed = lower scale).
        emotion_hint is acknowledged but Piper doesn't natively support emotion control.
        """
        voice = self._voice_for(voice_id)

        # length_scale: 1.0 = normal, <1.0 = faster, >1.0 = slower
        length_scale = 1.0 / max(speed, 0.1)
        cfg = SynthesisConfig(length_scale=length_scale)

        raw_samples = b""
        sample_rate = voice.config.sample_rate
        for chunk in voice.synthesize(text, cfg):
            raw_samples += chunk.audio_int16_bytes
            sample_rate = chunk.sample_rate

        return AudioClip(
            sample_rate=sample_rate,
            channels=1,
            samples=raw_samples,
            format="pcm_s16le",
        )

    def list_voices(self) -> list[VoiceInfo]:
        """List available voice models in the voices directory."""
        voices: list[VoiceInfo] = []
        for model_path in sorted(self.voices_dir.glob("*.onnx")):
            if model_path.name.endswith(".json"):
                continue
            voice_id = model_path.stem
            display = voice_id.replace("-", " ").replace("_", " ").title()
            lang = "en"
            parts = voice_id.split("-")
            if len(parts) >= 2:
                lang = parts[0]  # e.g. "en_US"
            voices.append(
                VoiceInfo(
                    voice_id=voice_id,
                    display_name=display,
                    language=lang,
                    tags=["piper", "neural", "local"],
                )
            )
        return voices
