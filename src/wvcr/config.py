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

@dataclass
class AudioConfig:
    CHUNK: int = 1024
    FORMAT: int = pyaudio.paInt16
    CHANNELS: int = 1
    RATE: int = 44100
    STOP_KEY: Key = Key.esc  # Changed from '\x1b' to Key.esc
    MAX_DURATION: int = 120  # maximum duration in seconds (2 minutes)
    # Lower quality settings for smaller files
    LOW_QUALITY_RATE: int = 16000  # CD quality is 44100, 16000 is good for voice
    LOW_QUALITY_FORMAT: int = pyaudio.paInt16  # Could use paInt8 for even smaller files
    LOW_QUALITY_CHUNK: int = 1024  # Smaller chunk size
