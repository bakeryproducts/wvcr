
import wave
import pyaudio
from pathlib import Path
from loguru import logger

from wvcr.common import KeyMonitor
from wvcr.config import AudioConfig


class SpeechPlayer:
    def __init__(self, notifier):
        self.config = AudioConfig()
        self.playing = False
        self.notifier = notifier

    def _send_notification(self, title: str, text: str):
        self.notifier.send_notification(title, text, timeout=1, color='#00FF00', font_size='14px')

    def play(self, filename: Path, stop_on_key=True):
        if not filename.exists():
            logger.error(f"File {filename} does not exist")
            return

        wf = wave.open(str(filename), 'rb')
        p = pyaudio.PyAudio()

        stream = p.open(
            format=p.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True
        )

        self.playing = True
        # self._send_notification('Playback Started', 'playing')

        if stop_on_key:
            key_monitor = KeyMonitor(self.config.STOP_KEY, lambda: setattr(self, 'playing', False))
            key_monitor.start()

        chunk_size = self.config.CHUNK
        data = wf.readframes(chunk_size)

        while data and self.playing:
            stream.write(data)
            data = wf.readframes(chunk_size)

        stream.stop_stream()
        stream.close()
        p.terminate()
        if stop_on_key:
            key_monitor.stop()