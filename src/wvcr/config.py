import os
from pathlib import Path
from dataclasses import dataclass, field

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
    """Configuration for OpenAI provider (lazy client creation)."""
    provider: str = "openai"
    STT_MODEL: str = "whisper-1"
    GPT_MODEL: str = "gpt-4.1-2025-04-14"
    # EXPLAIN_MODEL: str = "gpt-4.1-2025-04-14"
    EXPLAIN_MODEL: str = "gpt-5"
    temperature: float = 0.0
    api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    _client: object = field(default=None, init=False, repr=False)

    def get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI  # lazy import
            except ImportError as e:
                raise RuntimeError("openai package not installed. Install openai to use OpenAI provider.") from e
            self._client = OpenAI(api_key=self.api_key)
        return self._client


@dataclass
class GeminiConfig:
    """Configuration for Gemini provider (transcription placeholder)."""
    provider: str = "gemini"
    STT_MODEL: str = "gemini-2.5-flash"
    GPT_MODEL: str = "gemini-2.5-pro"
    EXPLAIN_MODEL: str = "gemini-2.5-flash"
    temperature: float = 0.0
    api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    _client: object = field(default=None, init=False, repr=False)

    def get_client(self):
        if self._client is None:
            try:
                from google import genai
            except ImportError as e:
                raise RuntimeError("google-generativeai package not installed. Install it to use Gemini provider.") from e
            # genai.configure(api_key=self.api_key)
            self._client = genai.Client(api_key=self.api_key)
        return self._client


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