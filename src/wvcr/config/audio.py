"""Audio hardware configuration for recording and playback."""
from dataclasses import dataclass
from typing import Any
import pyaudio
from pynput.keyboard import Key


@dataclass
class RecorderAudioConfig:
    """Configuration for audio recording (microphone capture)."""
    CHUNK: int = 1024
    FORMAT: int = pyaudio.paInt16
    CHANNELS: int = 1
    RATE: int = 16000
    AUDIO_FORMAT: str = "mp3"  # File format: mp3, wav
    STOP_KEY: Any = Key.esc
    MAX_DURATION: int = 120  # seconds
    ENABLE_VAD: bool = False


@dataclass
class PlayerAudioConfig:
    """Configuration for audio playback."""
    CHUNK: int = 1024
    FORMAT: int = pyaudio.paInt16
    CHANNELS: int = 1
    RATE: int = 44100
    STOP_KEY: Any = Key.esc
