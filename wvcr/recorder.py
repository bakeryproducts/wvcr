import time
from pathlib import Path
import wave
import pyaudio
from pynput import keyboard
from loguru import logger

from wvcr.config import AudioConfig
from wvcr.notification_manager import NotificationManager


class VoiceRecorder:
    def __init__(self, config: AudioConfig):
        self.config = config
        self.recording = False
        self.frames = []
        self.listener = None
        self.start_time = None
        self.notifier = NotificationManager()

    def _setup_audio(self):
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=self.config.LOW_QUALITY_FORMAT,
            channels=self.config.CHANNELS,
            rate=self.config.LOW_QUALITY_RATE,
            input=True,
            frames_per_buffer=self.config.LOW_QUALITY_CHUNK
        )

    def _send_notification(self, title: str, text: str):
        self.notifier.send_notification(title, text, timeout=1, color='#FF0000', font_size='14px')

    def _on_key_press(self, key):
        if key == self.config.STOP_KEY:  # Direct comparison with Key enum
            self.recording = False
            self.listener.stop()

    def _monitor_stop_key(self):
        self.listener = keyboard.Listener(on_press=self._on_key_press)
        self.listener.start()

    def _check_duration(self) -> bool:
        if self.start_time is None:
            return True
        elapsed = time.time() - self.start_time
        if elapsed >= self.config.MAX_DURATION:
            logger.info(f"Maximum recording duration ({self.config.MAX_DURATION}s) reached")
            self.recording = False
            return False
        return True

    def record(self, filename: Path) -> None:
        self._setup_audio()
        self.recording = True
        self.start_time = time.time()
        self._send_notification('Recording Started', 'recording')

        self._monitor_stop_key()  # Start key listener

        while self.recording and self._check_duration():
            self.frames.append(self.stream.read(self.config.CHUNK))

        self._cleanup()
        self._save_to_file(filename)

    def _cleanup(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

    def _save_to_file(self, filename: Path):
        with wave.open(str(filename), 'wb') as wf:
            wf.setnchannels(self.config.CHANNELS)
            wf.setsampwidth(self.p.get_sample_size(self.config.LOW_QUALITY_FORMAT))
            wf.setframerate(self.config.LOW_QUALITY_RATE)
            wf.writeframes(b''.join(self.frames))