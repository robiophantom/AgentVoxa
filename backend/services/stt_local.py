"""Local speech-to-text fallback for raw PCM call audio."""
from __future__ import annotations

import logging
from functools import lru_cache

import numpy as np

from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LocalSTT:
    """Thin wrapper around faster-whisper with graceful degradation."""

    def __init__(self) -> None:
        self._model = None
        self._available = False
        self._load_error = ""
        self._init_model()

    def _init_model(self) -> None:
        if not settings.local_stt_enabled:
            self._load_error = "LOCAL_STT_ENABLED is false"
            return

        try:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                settings.local_stt_model_size,
                device="cpu",
                compute_type="int8",
            )
            self._available = True
            logger.info("Local STT model loaded: %s", settings.local_stt_model_size)
        except Exception as exc:  # pragma: no cover - depends on runtime environment
            self._load_error = str(exc)
            logger.warning("Local STT unavailable: %s", exc)

    @property
    def available(self) -> bool:
        return self._available and self._model is not None

    @property
    def load_error(self) -> str:
        return self._load_error

    def transcribe_pcm16le(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """Transcribe mono PCM16LE bytes and return text."""
        if not self.available or not audio_bytes:
            return ""

        try:
            # Convert int16 PCM bytes to float32 [-1, 1]
            waveform = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            if waveform.size == 0:
                return ""

            segments, _ = self._model.transcribe(
                waveform,
                language=settings.local_stt_language,
                vad_filter=True,
                beam_size=1,
            )
            text = " ".join(s.text.strip() for s in segments if s.text and s.text.strip()).strip()
            return text
        except Exception:
            logger.exception("Local STT transcription failed")
            return ""


@lru_cache
def get_local_stt() -> LocalSTT:
    return LocalSTT()
