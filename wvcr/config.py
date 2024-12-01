import os
from dataclasses import dataclass
import pyaudio
from pynput.keyboard import Key
from pathlib import Path
import importlib.resources

import dotenv
dotenv.load_dotenv()


PACKAGE_ROOT = Path(importlib.resources.files("wvcr"))
OUTPUT = PACKAGE_ROOT.parent / "output"
OUTPUT.mkdir(exist_ok=True)


@dataclass
class OAIConfig:
    STT_MODEL: str = "whisper-1"
    GPT_MODEL: str = "gpt-4o-2024-11-20"
    temperature: float = 0.0
    
    def __init__(self, model: str = None):
        if model:
            self.GPT_MODEL = model


@dataclass
class AudioConfig:
    CHUNK: int = 1024
    FORMAT: int = pyaudio.paInt16
    CHANNELS: int = 1
    RATE: int = 44100
    OUTPUT_FORMAT: str = 'mp3'
    STOP_KEY: Key = Key.esc  # Changed from '\x1b' to Key.esc
    MAX_DURATION: int = 120  # maximum duration in seconds (2 minutes)
    # Lower quality settings for smaller files
    LOW_QUALITY_RATE: int = 16000  # CD quality is 44100, 16000 is good for voice
    LOW_QUALITY_FORMAT: int = pyaudio.paInt16  # Could use paInt8 for even smaller files
    LOW_QUALITY_CHUNK: int = 512  # Smaller chunk size
