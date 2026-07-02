from __future__ import annotations

import io
import subprocess
import threading
import wave

from loguru import logger

from .audio import (
    CAPTURE_DEVICE,
    CHANNELS,
    FRAME_SAMPLES,
    SAMPLE_RATE,
    SAMPLE_WIDTH,
)

FRAME_BYTES = FRAME_SAMPLES * CHANNELS * SAMPLE_WIDTH
MP3_BITRATE = "16k"  # matches what Gemini downsamples to internally anyway,
# so sending higher bitrate is just wasted upload bytes.
SPEED_FACTOR = 2.0  # speed up audio before sending -- only text matters, not
# playback quality, so a faster/shorter clip means less upload + faster
# Gemini processing. atempo supports 0.5-2.0 per filter instance.


class RingBuffer:
    """In-memory rolling buffer of the last `window_seconds` of PCM16 audio.

    A background thread reads raw PCM from `pacat --record` on the hint bus
    monitor and appends it. Old bytes are trimmed off the front. Reading is
    I/O-bound (blocks on read), so idle CPU cost is ~0.
    """

    def __init__(self, window_seconds: float = 600.0):
        self._max_bytes = int(SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH * window_seconds)
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._proc = subprocess.Popen(
            [
                "pacat",
                "--record",
                f"--device={CAPTURE_DEVICE}",
                f"--rate={SAMPLE_RATE}",
                f"--channels={CHANNELS}",
                "--format=s16le",
                "--raw",
                "--latency-msec=40",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        logger.info(f"hint ring buffer capturing {CAPTURE_DEVICE}")

    def _read_loop(self) -> None:
        assert self._proc is not None
        stdout = self._proc.stdout
        assert stdout is not None
        while not self._stop.is_set():
            chunk = stdout.read(FRAME_BYTES)
            if not chunk:
                logger.warning("hint capture stdout closed")
                break
            with self._lock:
                self._buf.extend(chunk)
                excess = len(self._buf) - self._max_bytes
                if excess > 0:
                    del self._buf[:excess]

    def snapshot(self) -> bytes:
        with self._lock:
            return bytes(self._buf)

    def snapshot_wav(self) -> bytes:
        pcm = self.snapshot()
        out = io.BytesIO()
        with wave.open(out, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm)
        return out.getvalue()

    def snapshot_mp3(self) -> bytes:
        """Compress the current snapshot to MP3 in-memory (no temp files).

        Gemini downsamples all audio to 16 Kbps internally, so a low-bitrate
        MP3 costs no understanding quality while cutting payload size ~6x
        vs raw PCM/WAV -- important once the window is minutes long. Audio
        is also sped up by SPEED_FACTOR since only the transcribed text
        matters -- a shorter clip uploads faster and Gemini processes it
        faster too.
        """
        pcm = self.snapshot()
        cmd = [
            "ffmpeg",
            "-f", "s16le",
            "-ar", str(SAMPLE_RATE),
            "-ac", str(CHANNELS),
            "-i", "pipe:0",
            "-filter:a", f"atempo={SPEED_FACTOR}",
            "-codec:a", "libmp3lame",
            "-b:a", MP3_BITRATE,
            "-f", "mp3",
            "pipe:1",
        ]
        result = subprocess.run(cmd, input=pcm, capture_output=True, check=True)
        return result.stdout

    def stop(self) -> None:
        self._stop.set()
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            except Exception as e:
                logger.warning(f"error stopping hint capture: {e}")
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1)
