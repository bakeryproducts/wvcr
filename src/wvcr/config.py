import os
from pathlib import Path
from dataclasses import dataclass

from loguru import logger

import pyaudio
from pynput.keyboard import Key

import dotenv

PACKAGE_ROOT = Path(__file__).parent.parent.parent.absolute()
OUTPUT = PACKAGE_ROOT / "output"
OUTPUT.mkdir(exist_ok=True)


def find_dotenv():
    """Find .env file in various possible locations"""
    # Check in the package root
    package_env = PACKAGE_ROOT / '.env'
    # logger.debug(f"Checking for .env file in {package_env}")
    if package_env.exists():
        return str(package_env)
    return None


# Load .env file from the first location found
dotenv_path = find_dotenv()
if dotenv_path:
    dotenv.load_dotenv(dotenv_path)
else:
    logger.error("Warning: No .env file found. Make sure to set OPENAI_API_KEY environment variable.")


@dataclass
class OAIConfig:
    STT_MODEL: str = "whisper-1"
    # STT_MODEL: str = "gpt-4o-transcribe" # wont support 16 kHz for some reason
    # GPT_MODEL: str = "gpt-4o-2024-11-20"
    GPT_MODEL: str = "gpt-4.1-2025-04-14"
    temperature: float = 0.0
    client = None
    
    def __init__(self, model: str = None):
        if model:
            self.GPT_MODEL = model
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.client = client

# New separate configs
@dataclass
class RecorderAudioConfig:
    """Configuration for audio recording (microphone capture)."""
    CHUNK: int = 1024
    FORMAT: int = pyaudio.paInt16
    CHANNELS: int = 1
    # RATE: int = 44100
    RATE: int = 16000
    STOP_KEY: Key = Key.esc
    MAX_DURATION: int = 120  # seconds
    ENABLE_VAD: bool = True  

@dataclass
class PlayerAudioConfig:
    """Configuration for audio playback."""
    CHUNK: int = 1024        # playback buffer size
    FORMAT: int = pyaudio.paInt16
    CHANNELS: int = 1
    RATE: int = 44100
    STOP_KEY: Key = Key.esc