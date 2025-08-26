from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Optional

from loguru import logger

try:
    import webrtcvad  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    webrtcvad = None  # type: ignore


@dataclass
class VADConfig:
    rate: int = 16000
    chunk_ms: int = 20


class BaseVAD:
    def is_speech(self, pcm_bytes: bytes, rate: int) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

class NoVad:
    def is_speech(self, pcm_bytes: bytes, rate: int) -> bool:
        return True

class WebRtcVAD(BaseVAD):
    """WebRTC VAD wrapper with hangover handling."""

    def __init__(self, aggressiveness: int = 2, hangover_ms: int = 0, chunk_ms: int = 20, rate: int = 16000):
        if webrtcvad is None:
            raise RuntimeError("webrtcvad is not available; install it or disable WebRTC VAD")
        if chunk_ms not in (10, 20, 30):
            raise ValueError("WebRTC VAD requires frame sizes of 10, 20, or 30 ms")
        if rate not in (8000, 16000, 32000, 48000):
            raise ValueError("WebRTC VAD supports 8/16/32/48 kHz sample rates")

        self._vad = webrtcvad.Vad(int(aggressiveness))
        self._chunk_ms = int(chunk_ms)
        self._hangover_frames = 0
        self._hangover_limit = max(0, int(hangover_ms) // self._chunk_ms)

    def is_speech(self, pcm_bytes: bytes, rate: int) -> bool:
        try:
            is_speech = self._vad.is_speech(pcm_bytes, rate)
        except Exception as e:  # fail-open for robustness
            logger.debug(f"WebRTC VAD error: {e}")
            is_speech = True

        if is_speech:
            if self._hangover_limit:
                self._hangover_frames = self._hangover_limit
            return True
        if self._hangover_frames > 0:
            self._hangover_frames -= 1
            return True
        return False


class SileroVAD(BaseVAD):
    """Silero VAD wrapper for streaming use.

    Accumulates a short rolling window of audio and runs Silero's get_speech_timestamps.
    Declares current frame as speech if detected timestamps intersect the latest chunk.
    """

    def __init__(
        self,
        window_ms: int = 500,
        hangover_ms: int = 300,
        threshold: Optional[float] = None,
        min_speech_ms: Optional[int] = None,
        min_silence_ms: Optional[int] = None,
    ):
        from silero_vad import load_silero_vad  # type: ignore

        self._model = load_silero_vad()
        self._window_ms = int(window_ms)
        self._hangover_frames = 0
        self._hangover_ms = max(0, int(hangover_ms))
        self._threshold = threshold
        self._min_speech_ms = min_speech_ms
        self._min_silence_ms = min_silence_ms

        # Rolling buffer of recent raw PCM16 bytes
        self._buf = bytearray()
        self._last_chunk_samples = 0

    def _bytes_to_tensor(self, pcm_bytes: bytes):
        # Avoid numpy to reduce extra deps; use array + torch
        import array
        import torch

        arr = array.array('h')
        arr.frombytes(pcm_bytes)
        t = torch.tensor(arr, dtype=torch.float32)
        t /= 32768.0
        return t

    def _analyze(self, rate: int):
        # Convert rolling buffer to torch tensor and run silero
        if not self._buf:
            return []
        wav = self._bytes_to_tensor(bytes(self._buf))
        try:
            from silero_vad import get_speech_timestamps  # type: ignore
        except Exception as e:  # pragma: no cover
            logger.debug(f"silero-vad not importable at runtime: {e}")
            return []

        kwargs = {}
        if self._threshold is not None:
            kwargs['threshold'] = float(self._threshold)
        if self._min_speech_ms is not None:
            kwargs['min_speech_duration_ms'] = int(self._min_speech_ms)
        if self._min_silence_ms is not None:
            kwargs['min_silence_duration_ms'] = int(self._min_silence_ms)

        ts = get_speech_timestamps(wav, self._model, sampling_rate=rate, return_seconds=False, **kwargs)
        return ts or []

    def is_speech(self, pcm_bytes: bytes, rate: int) -> bool:
        res = self._is_speech(pcm_bytes, rate)
        # if res:
        #     logger.debug(f"Silero VAD speech detected  buf_len={len(self._buf)}")
        # else:
        #     logger.debug("No speech detected")
        return res


    def _is_speech(self, pcm_bytes: bytes, rate: int) -> bool:
        if rate != 16000:
            # Silero models are trained for 16k; fail-open if mismatch
            logger.debug("Silero VAD expects 16kHz audio; passing through")
            return True

        # Update rolling buffer and maintain window size
        self._buf.extend(pcm_bytes)
        self._last_chunk_samples = len(pcm_bytes) // 2
        max_bytes = (rate * self._window_ms // 1000) * 2
        if len(self._buf) > max_bytes:
            del self._buf[: len(self._buf) - max_bytes]

        # Analyze the current window
        timestamps = self._analyze(rate)
        # Decide current-frame speech by intersection with last chunk region
        if timestamps:
            total_samples = len(self._buf) // 2
            last_region_start = max(0, total_samples - self._last_chunk_samples)
            for seg in timestamps:
                start = int(seg.get('start', 0))
                end = int(seg.get('end', 0))
                if end > last_region_start and start < total_samples:
                    # Speech overlaps the latest chunk
                    if self._hangover_ms > 0:
                        self._hangover_frames = max(
                            self._hangover_frames,
                            self._hangover_ms // max(1, (self._last_chunk_samples * 1000 // rate)),
                        )
                    return True

        # No direct speech found in current chunk; apply hangover if any
        if self._hangover_frames > 0:
            self._hangover_frames -= 1
            return True
        return False
