from __future__ import annotations

import os
from typing import Any

from orket_extension_sdk.audio import AudioClip, AudioPlayer, NullAudioPlayer


class SounddevicePlayer:
    """Optional sounddevice-backed audio player."""

    def __init__(self) -> None:
        try:
            import sounddevice as sd  # type: ignore
            import numpy as np  # type: ignore
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("sounddevice backend requires sounddevice and numpy") from exc
        self._sd = sd
        self._np = np

    def play(self, clip: AudioClip, blocking: bool = False) -> None:
        if clip.format != "pcm_s16le":
            raise ValueError(f"Unsupported audio clip format: {clip.format}")
        if not clip.samples:
            return
        arr = self._np.frombuffer(clip.samples, dtype=self._np.int16)
        if clip.channels > 1:
            arr = arr.reshape((-1, clip.channels))
        self._sd.play(arr, samplerate=int(clip.sample_rate), blocking=bool(blocking))

    def stop(self) -> None:
        self._sd.stop()


def build_audio_player(*, input_config: dict[str, Any]) -> AudioPlayer:
    backend = str(input_config.get("audio_backend") or os.getenv("ORKET_AUDIO_BACKEND", "null")).strip().lower()
    if backend != "sounddevice":
        return NullAudioPlayer()
    try:
        return SounddevicePlayer()
    except RuntimeError:
        return NullAudioPlayer()

