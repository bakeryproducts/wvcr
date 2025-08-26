from __future__ import annotations
import time
import wave
import subprocess
from pathlib import Path
from loguru import logger

from wvcr.notification_manager import NotificationManager
from wvcr.common import create_key_monitor
from wvcr.config import RecorderAudioConfig
from wvcr.ipc.ipc_mic_handler import IPCMicHandler


class IPCVoiceRecorder:
    """
    IPC-based voice recorder that mimics the public API of the legacy VoiceRecorder.
    It spawns a separate mic capture process that streams VAD-filtered PCM frames
    via a Unix domain socket. Frames are accumulated locally until stopped.
    """
    def __init__(self, notifier: NotificationManager | None = None, use_evdev: bool = False):
        self.config = RecorderAudioConfig()
        self.notifier = notifier or NotificationManager()
        self.use_evdev = use_evdev
        self._ipc = IPCMicHandler(rate=self.config.RATE, channels=self.config.CHANNELS, enable_vad=self.config.ENABLE_VAD)
        self._frames: list[bytes] = []
        self._recording = False

    def record(self, output_file: Path, format: str = "wav") -> Path:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        self._ipc.start()
        self._frames = []
        self._recording = True
        start_time = time.time()

        self.notifier.send_notification("Recording", "Recording started (IPC). Press ESC to stop.")
        logger.info("[IPC] Recording started")

        stop_key = self.config.STOP_KEY

        def _stop():
            self._recording = False

        key_monitor = create_key_monitor(stop_key, _stop, prefer_evdev=self.use_evdev)
        key_monitor.start()

        try:
            while self._recording and (time.time() - start_time) < self.config.MAX_DURATION:
                try:
                    frame = self._ipc.get_frame(timeout=0.25)
                    if frame:
                        self._frames.append(frame)
                except Exception:
                    # Timeout or queue empty; just loop
                    pass
        finally:
            key_monitor.stop()
            self._ipc.stop()
            self._recording = False

        logger.info("[IPC] Recording stopped")
        self.notifier.send_notification("Recording", "Recording finished (IPC)")

        if format.lower() == "mp3":
            self._save_mp3(output_file)
        else:
            self._save_wav(output_file)
        logger.info("Files saved")
        return output_file


    def _save_wav(self, output_file: Path):
        if not self._frames:
            logger.warning("[IPC] No audio frames captured; creating empty file")
        raw = b"".join(self._frames)
        import pyaudio

        with wave.open(str(output_file), 'wb') as wf:
            wf.setnchannels(self.config.CHANNELS)
            wf.setsampwidth(pyaudio.PyAudio().get_sample_size(pyaudio.paInt16))
            wf.setframerate(self.config.RATE)
            wf.writeframes(raw)
        logger.info(f"[IPC] Audio saved to {output_file}")

    def _save_mp3(self, output_file: Path):
        temp_wav = output_file.with_suffix('.tmp.wav')
        self._save_wav(temp_wav)
        cmd = ["ffmpeg", "-i", str(temp_wav), "-codec:a", "libmp3lame", "-b:a", "128k", "-y", str(output_file)]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"[IPC] Audio saved as MP3 to {output_file}")
            temp_wav.unlink(missing_ok=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"[IPC] Error converting to MP3: {e}")
            temp_wav.rename(output_file.with_suffix('.wav'))
            raise
        except FileNotFoundError:
            logger.error("ffmpeg not found. Install ffmpeg to enable MP3 saving.")
            # Keep wav
            pass
