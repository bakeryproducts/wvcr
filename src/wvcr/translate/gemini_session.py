from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional
from loguru import logger
from google import genai
from google.genai import types


class GeminiConfig:
    def __init__(self, target_language: str, api_key: str, echo_target_language: bool = True):
        self.target_language = target_language
        self.api_key = api_key
        self.echo_target_language = echo_target_language


class GeminiSession:
    def __init__(
        self,
        config: GeminiConfig,
        on_output_audio: Callable[[bytes], Awaitable[None] | None],
        on_output_transcript: Callable[[str], Awaitable[None] | None] | None = None,
        on_input_transcript: Callable[[str], Awaitable[None] | None] | None = None,
    ):
        self.config = config
        self.on_output_audio = on_output_audio
        self.on_output_transcript = on_output_transcript
        self.on_input_transcript = on_input_transcript
        self._client: Optional[genai.Client] = None
        self._session_ctx = None
        self._session = None
        self._closing = False
        self._closed_event = asyncio.Event()

    async def __aenter__(self) -> GeminiSession:
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def connect(self) -> None:
        logger.info("connecting to Gemini Live Translate API")
        self._client = genai.Client(api_key=self.config.api_key)
        
        # Configure Live Translate
        model = "gemini-3.5-live-translate-preview"
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            translation_config=types.TranslationConfig(
                target_language_code=self.config.target_language,
                echo_target_language=self.config.echo_target_language,
            ),
        )
        # Connect
        self._session_ctx = self._client.aio.live.connect(model=model, config=config)
        self._session = await self._session_ctx.__aenter__()
        logger.info(f"Gemini translation session started (target_language={self.config.target_language})")

    async def send_audio(self, pcm16: bytes) -> None:
        if self._session is None or self._closing:
            return
        try:
            # Input audio format for translation is 16-bit PCM at 16kHz
            await self._session.send_realtime_input(
                audio=types.Blob(
                    data=pcm16,
                    mime_type="audio/pcm;rate=16000"
                )
            )
        except Exception as e:
            if not self._closing:
                logger.error(f"Error sending audio to Gemini: {e}")

    async def receive_loop(self) -> None:
        if self._session is None:
            return
        try:
            while not self._closing:
                response = await self._session._receive()
                if self._closing:
                    break
                if response.server_content:
                    # Handle input transcription
                    if response.server_content.input_transcription and self.on_input_transcript:
                        text = response.server_content.input_transcription.text
                        if text:
                            res = self.on_input_transcript(text)
                            if asyncio.iscoroutine(res):
                                await res
                    
                    # Handle output transcription
                    if response.server_content.output_transcription and self.on_output_transcript:
                        text = response.server_content.output_transcription.text
                        if text:
                            res = self.on_output_transcript(text)
                            if asyncio.iscoroutine(res):
                                await res

                    # Handle audio data
                    if response.server_content.model_turn:
                        for part in response.server_content.model_turn.parts:
                            if part.inline_data and part.inline_data.data:
                                res = self.on_output_audio(part.inline_data.data)
                                if asyncio.iscoroutine(res):
                                    await res
        except Exception as e:
            if not self._closing:
                logger.info(f"Gemini receive loop closed / error: {e}")
        finally:
            self._closed_event.set()

    async def close(self) -> None:
        if self._session is None:
            return
        if not self._closing:
            self._closing = True
            try:
                # Close the context manager of the session
                if self._session_ctx is not None:
                    await self._session_ctx.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error exiting Gemini session context: {e}")
            
            try:
                await asyncio.wait_for(self._closed_event.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Timed out waiting for Gemini session to close")
        self._session = None
        self._client = None
