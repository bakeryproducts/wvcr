from __future__ import annotations

import asyncio
import signal
import subprocess
from pathlib import Path
from typing import Optional

from loguru import logger

from .audio import (
    CHANNELS,
    FRAME_MS,
    SAMPLE_RATE,
    SAMPLE_WIDTH,
    SINK_NAME,
    start_loopback,
    stop_loopback,
)
from .presets import Preset
from .recorder import PCMRecorder, TranscriptRecorder, make_session_dir
from .session import TranslateConfig, TranslateSession


def _spawn_capture(rate: int) -> subprocess.Popen:
    return subprocess.Popen(
        [
            "pacat",
            "--record",
            "--device=@DEFAULT_SOURCE@",
            f"--rate={rate}",
            f"--channels={CHANNELS}",
            "--format=s16le",
            "--raw",
            "--latency-msec=20",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )


def _spawn_playback() -> subprocess.Popen:
    return subprocess.Popen(
        [
            "pacat",
            "--playback",
            f"--device={SINK_NAME}",
            f"--rate={SAMPLE_RATE}",
            f"--channels={CHANNELS}",
            "--format=s16le",
            "--raw",
            "--latency-msec=20",
        ],
        stdin=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )


class Runner:
    def __init__(self, preset: Preset, api_key: str, record: bool = False):
        self.preset = preset
        self.api_key = api_key
        self.record = record
        self.capture_proc: Optional[subprocess.Popen] = None
        self.playback_proc: Optional[subprocess.Popen] = None
        self.session: Optional[object] = None
        self._stop = asyncio.Event()
        self._audio_in_bytes = 0
        self._audio_out_bytes = 0
        self._source_rec: Optional[PCMRecorder] = None
        self._translated_rec: Optional[PCMRecorder] = None
        self._source_text: Optional[TranscriptRecorder] = None
        self._translated_text: Optional[TranscriptRecorder] = None
        self._session_dir: Optional[Path] = None
        self.input_rate = 16000 if self.preset.backend == "gemini" else 24000
        self.frame_samples = self.input_rate * FRAME_MS // 1000
        self.frame_bytes = self.frame_samples * CHANNELS * SAMPLE_WIDTH

    def _on_output_audio(self, pcm: bytes) -> None:
        self._audio_out_bytes += len(pcm)
        if self._translated_rec is not None:
            self._translated_rec.write(pcm)
        if self.playback_proc is None or self.playback_proc.stdin is None:
            return
        try:
            self.playback_proc.stdin.write(pcm)
            self.playback_proc.stdin.flush()
        except (BrokenPipeError, ValueError):
            pass

    def _on_output_transcript(self, delta: str) -> None:
        if self._translated_text is not None:
            self._translated_text.append(delta)
        print(delta, end="", flush=True)

    def _on_input_transcript(self, delta: str) -> None:
        if self._source_text is not None:
            self._source_text.append(delta)

    async def _capture_loop(self) -> None:
        assert self.capture_proc is not None
        assert self.session is not None
        loop = asyncio.get_running_loop()
        stdout = self.capture_proc.stdout
        assert stdout is not None
        try:
            while not self._stop.is_set():
                chunk = await loop.run_in_executor(None, stdout.read, self.frame_bytes)
                if not chunk:
                    logger.warning("capture stdout closed")
                    break
                self._audio_in_bytes += len(chunk)
                if self._source_rec is not None:
                    self._source_rec.write(chunk)
                await self.session.send_audio(chunk)
        except asyncio.CancelledError:
            pass

    async def run(self) -> None:
        stop_loopback()
        self.capture_proc = _spawn_capture(self.input_rate)
        self.playback_proc = _spawn_playback()
        logger.info(
            f"capture pid={self.capture_proc.pid} playback pid={self.playback_proc.pid}"
        )

        if self.record:
            self._session_dir = make_session_dir()
            self._source_rec = PCMRecorder(self._session_dir / "source.wav", sample_rate=self.input_rate)
            self._translated_rec = PCMRecorder(self._session_dir / "translated.wav")
            self._source_text = TranscriptRecorder(self._session_dir / "source.txt")
            self._translated_text = TranscriptRecorder(
                self._session_dir / "translated.txt"
            )
            logger.info(f"recording -> {self._session_dir}")

        if self.preset.backend == "gemini":
            from .gemini_session import GeminiConfig, GeminiSession
            cfg = GeminiConfig(
                target_language=self.preset.language,
                api_key=self.api_key,
                echo_target_language=self.preset.echo_target_language,
            )
            session_cls = GeminiSession
        else:
            cfg = TranslateConfig(
                target_language=self.preset.language,
                api_key=self.api_key,
            )
            session_cls = TranslateSession

        try:
            async with session_cls(
                cfg,
                on_output_audio=self._on_output_audio,
                on_output_transcript=self._on_output_transcript,
                on_input_transcript=self._on_input_transcript,
            ) as session:
                self.session = session
                self._install_signal_handlers()

                cap_task = asyncio.create_task(self._capture_loop())
                recv_task = asyncio.create_task(session.receive_loop())
                stop_task = asyncio.create_task(self._stop.wait())

                done, pending = await asyncio.wait(
                    {cap_task, recv_task, stop_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for t in pending:
                    t.cancel()
                    try:
                        await t
                    except asyncio.CancelledError:
                        pass
        finally:
            self._cleanup_audio_procs()
            start_loopback()
            self._save_recordings()
            logger.info(
                f"audio in={self._audio_in_bytes} bytes "
                f"out={self._audio_out_bytes} bytes"
            )

    def _cleanup_audio_procs(self) -> None:
        for proc in (self.capture_proc, self.playback_proc):
            if proc is None:
                continue
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
            except Exception as e:
                logger.warning(f"error stopping audio proc: {e}")

    def _save_recordings(self) -> None:
        for rec in (
            self._source_rec,
            self._translated_rec,
            self._source_text,
            self._translated_text,
        ):
            if rec is None:
                continue
            try:
                rec.save()
            except Exception as e:
                logger.warning(f"failed to save {rec.path}: {e}")

    def _install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._request_stop)
            except NotImplementedError:
                pass

    def _request_stop(self) -> None:
        logger.info("stop requested")
        self._stop.set()


def run_translation(preset: Preset, api_key: str, record: bool = False) -> None:
    runner = Runner(preset, api_key, record=record)
    asyncio.run(runner.run())
