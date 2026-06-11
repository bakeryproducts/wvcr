from __future__ import annotations

import wave
from datetime import datetime
from pathlib import Path

from loguru import logger

from wvcr.config import OUTPUT

from .audio import CHANNELS, SAMPLE_RATE, SAMPLE_WIDTH


def make_session_dir() -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = OUTPUT / "translate" / timestamp
    path.mkdir(exist_ok=True, parents=True)
    return path


class PCMRecorder:
    def __init__(self, path: Path):
        self.path = path
        self._chunks: list[bytes] = []

    def write(self, pcm: bytes) -> None:
        if pcm:
            self._chunks.append(pcm)

    def total_bytes(self) -> int:
        return sum(len(c) for c in self._chunks)

    def save(self) -> bool:
        if not self._chunks:
            return False
        with wave.open(str(self.path), "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"".join(self._chunks))
        logger.info(f"saved {self.total_bytes()} bytes -> {self.path}")
        return True


class TranscriptRecorder:
    def __init__(self, path: Path):
        self.path = path
        self._buf: list[str] = []

    def append(self, delta: str) -> None:
        if delta:
            self._buf.append(delta)

    def save(self) -> bool:
        if not self._buf:
            return False
        text = "".join(self._buf)
        self.path.write_text(text, encoding="utf-8")
        logger.info(f"saved transcript ({len(text)} chars) -> {self.path}")
        return True
