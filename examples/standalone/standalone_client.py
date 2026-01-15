import signal
import threading

import fire
from loguru import logger
from dotenv import load_dotenv

from config import AppConfig
from audio_player import AudioPlayer
from events_reader import EventsReader
from ipc.audio_ipc import UnixAudioInput, start_mic_capture_process


load_dotenv()

APP_NAME = "ADK Streaming example"


class App:
    def __init__(self, app_config: AppConfig):
        self._stop = threading.Event()
        self.config = app_config

        self.audio_input = UnixAudioInput(
            socket_path=app_config.streaming.socket_path,
            rcvbuf_bytes=app_config.streaming.ipc_rcvbuf_bytes,
            max_frames=app_config.streaming.ipc_max_frames)

        self.audio_player = AudioPlayer(rate=24000, debug=False)
        self.reader = EventsReader(self.audio_input, self.audio_player, app_config, app_name=APP_NAME)
        self._capture = None
        logger.debug(f"App initialized with mode: {app_config.streaming.mode}")

    def start(self):
        self.audio_input.start()
        self._capture = start_mic_capture_process(socket_path=self.config.streaming.socket_path,
                                                  rate=self.config.streaming.rate,
                                                  channels=1,
                                                  chunk_ms=self.config.streaming.chunk_ms,
                                                  batch_ms=self.config.streaming.batch_ms,
                                                  sndbuf_bytes=self.config.streaming.ipc_sndbuf_bytes,
                                                  enable_vad=self.config.streaming.enable_vad)
        self.audio_player.start()
        self.reader.start()

    def stop(self):
        if self.reader:
            self.reader.stop()
        if self._capture:
            try:
                self._capture.stop()
            except Exception:
                pass
        if self.audio_input:
            self.audio_input.stop()
        self.audio_player.stop()


class StreamingClient:
    def translation(self, language_code: str = "ru-RU", voice_name: str = "Orus"):
        config = AppConfig.create_translation(language_code, voice_name)
        self._run_app(App(config))
    
    def search(self, language_code: str = "ru-RU", voice_name: str = "Algenib"):
        config = AppConfig.create_search(language_code, voice_name)
        self._run_app(App(config))
        
    def _run_app(self, app: App):
        def handle_signal(sig, frame):
            app.stop()

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        app.start()

        try:
            signal.pause()
        except KeyboardInterrupt:
            pass
        finally:
            app.stop()


if __name__ == "__main__":
    fire.Fire(StreamingClient)
