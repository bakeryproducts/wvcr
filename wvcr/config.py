import os
from dataclasses import dataclass
import pyaudio
from pynput.keyboard import Key

import dotenv
dotenv.load_dotenv()


@dataclass
class OAIConfig:
    API_KEY: str = os.getenv("OPENAI_API_KEY")
    STT_MODEL: str = "whisper-1"
    GPT_MODEL: str = "gpt-4o"


@dataclass
class AudioConfig:
    CHUNK: int = 1024
    FORMAT: int = pyaudio.paInt16
    CHANNELS: int = 1
    RATE: int = 44100
    OUTPUT_FORMAT: str = 'mp3'
    STOP_KEY: Key = Key.esc  # Changed from '\x1b' to Key.esc
    MAX_DURATION: int = 60  # maximum duration in seconds (2 minutes)
