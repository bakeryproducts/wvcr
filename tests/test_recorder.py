
import pytest
from wvcr.recorder import VoiceRecorder
from wvcr.config import AudioConfig

@pytest.fixture
def config():
    return AudioConfig()

@pytest.fixture
def recorder(config):
    return VoiceRecorder(config)

def test_recorder_initialization(recorder):
    assert recorder is not None
    assert recorder.config is not None

def test_recorder_config(recorder, config):
    assert recorder.config.CHANNELS == config.CHANNELS
    assert recorder.config.RATE == config.RATE
    assert recorder.config.OUTPUT_FORMAT == config.OUTPUT_FORMAT


# TODO fixme
from loguru import logger
logger.debug('start')

import pyaudio
from pynput import keyboard
import wave

class SimpleRecorder:
    def __init__(self):
        self.recording = False
        self.frames = []
        
        # Basic audio settings
        # self.format = pyaudio.paInt16
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000 # 16kHz
        _chunk_seconds = 0.1
        self.chunk = int(self.rate * _chunk_seconds)

    def _setup_audio(self):
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk
        )

    def _on_key_press(self, key):
        if key == keyboard.Key.esc:  # Use ESC to stop
            self.recording = False
            self.listener.stop()

    def record(self, filename: str):
        self._setup_audio()
        self.recording = True
        
        # Setup keyboard listener
        self.listener = keyboard.Listener(on_press=self._on_key_press)
        self.listener.start()
        
        logger.debug("Recording... Press ESC to stop")
        while self.recording:
            self.frames.append(self.stream.read(self.chunk))

        # Cleanup
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

        # Save
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.p.get_sample_size(self.format))
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(self.frames))

if __name__ == "__main__":
    recorder = SimpleRecorder()
    recorder.record("test_recording.wav")