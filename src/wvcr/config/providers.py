"""API provider configurations with lazy client initialization."""
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class OAIConfig:
    """Configuration for OpenAI provider (lazy client creation)."""
    provider: str = "openai"
    STT_MODEL: str = "whisper-1"
    GPT_MODEL: str = "gpt-4.1-2025-04-14"
    EXPLAIN_MODEL: str = "gpt-5"
    temperature: float = 0.0
    api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    _client: Any = field(default=None, init=False, repr=False)

    def get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise RuntimeError(
                    "openai package not installed. Install openai to use OpenAI provider."
                ) from e
            self._client = OpenAI(api_key=self.api_key)
        return self._client


@dataclass
class GeminiConfig:
    """Configuration for Gemini provider."""
    provider: str = "gemini"
    STT_MODEL: str = "gemini-3-flash-preview"
    GPT_MODEL: str = "gemini-3-flash-preview"
    EXPLAIN_MODEL: str = "gemini-3-flash-preview"
    temperature: float = 1.0
    api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    _client: Any = field(default=None, init=False, repr=False)

    def get_client(self):
        if self._client is None:
            try:
                from google import genai
            except ImportError as e:
                raise RuntimeError(
                    "google-generativeai package not installed. "
                    "Install it to use Gemini provider."
                ) from e
            self._client = genai.Client(api_key=self.api_key)
        return self._client
