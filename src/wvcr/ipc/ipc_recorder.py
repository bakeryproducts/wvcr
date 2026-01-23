from __future__ import annotations
import time
import wave
import subprocess
from pathlib import Path
from loguru import logger

from wvcr.common import create_key_monitor
from wvcr.config import RecorderAudioConfig
from wvcr.ipc.ipc_mic_handler import IPCMicHandler


class IPCVoiceRecorder:
    """
    IPC-based voice recorder that mimics the public API of the legacy VoiceRecorder.
    It spawns a separate mic capture process that streams VAD-filtered PCM frames
    via a Unix domain socket. Frames are accumulated locally until stopped.
    """
    def __init__(self, config: RecorderAudioConfig, use_evdev: bool = False):
        self.config = config
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
        if not self._frames:
            logger.warning("[IPC] No audio frames captured; creating empty file")
        
        raw = b"".join(self._frames)
        
        # Pipe raw PCM directly to ffmpeg - no temp file needed
        cmd = [
            "ffmpeg",
            "-f", "s16le",           # signed 16-bit little-endian PCM
            "-ar", str(self.config.RATE),     # sample rate
            "-ac", str(self.config.CHANNELS), # channels
            "-i", "pipe:0",          # read from stdin
            "-codec:a", "libmp3lame",
            # "-b:a", "16k",           # 16 kbps to match Gemini downsampling
            "-b:a", "128k",         # 128 kbps for better quality  
            "-y",                    # overwrite output
            str(output_file)
        ]
        
        try:
            result = subprocess.run(cmd, input=raw, check=True, capture_output=True)
            logger.info(f"[IPC] Audio saved as MP3 to {output_file}")
        except subprocess.CalledProcessError as e:
            logger.error(f"[IPC] Error converting to MP3: {e.stderr.decode()}")
            raise
        except FileNotFoundError:
            logger.error("ffmpeg not found. Install ffmpeg to enable MP3 saving.")
            raise
