from __future__ import annotations

import asyncio
import base64
import json
import os
from dataclasses import dataclass
from typing import Awaitable, Callable

import websockets
from loguru import logger

WS_URL = "wss://api.openai.com/v1/realtime/translations?model=gpt-realtime-translate"


@dataclass
class TranslateConfig:
    target_language: str
    api_key: str


class TranslateSession:
    def __init__(
        self,
        config: TranslateConfig,
        on_output_audio: Callable[[bytes], Awaitable[None] | None],
        on_output_transcript: Callable[[str], Awaitable[None] | None] | None = None,
        on_input_transcript: Callable[[str], Awaitable[None] | None] | None = None,
    ):
        self.config = config
        self.on_output_audio = on_output_audio
        self.on_output_transcript = on_output_transcript
        self.on_input_transcript = on_input_transcript
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._closing = False
        self._closed_event = asyncio.Event()

    async def __aenter__(self) -> "TranslateSession":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def connect(self) -> None:
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
        }
        safety_id = os.getenv("OPENAI_SAFETY_IDENTIFIER")
        if safety_id:
            headers["OpenAI-Safety-Identifier"] = safety_id
        logger.info("connecting to translate WS")
        self._ws = await websockets.connect(
            WS_URL,
            additional_headers=headers,
            max_size=None,
        )
        await self._ws.send(
            json.dumps(
                {
                    "type": "session.update",
                    "session": {
                        "audio": {
                            "output": {
                                "language": self.config.target_language,
                            },
                        },
                    },
                }
            )
        )
        logger.info(f"session.update sent (lang={self.config.target_language})")

    async def send_audio(self, pcm16: bytes) -> None:
        if self._ws is None or self._closing:
            return
        b64 = base64.b64encode(pcm16).decode("ascii")
        await self._ws.send(
            json.dumps(
                {
                    "type": "session.input_audio_buffer.append",
                    "audio": b64,
                }
            )
        )

    async def receive_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                event = json.loads(raw)
                etype = event.get("type")
                if etype == "session.output_audio.delta":
                    audio_b64 = event.get("delta", "")
                    if audio_b64:
                        pcm = base64.b64decode(audio_b64)
                        result = self.on_output_audio(pcm)
                        if asyncio.iscoroutine(result):
                            await result
                elif etype == "session.output_transcript.delta":
                    if self.on_output_transcript:
                        delta = event.get("delta", "")
                        result = self.on_output_transcript(delta)
                        if asyncio.iscoroutine(result):
                            await result
                elif etype == "session.input_transcript.delta":
                    if self.on_input_transcript:
                        delta = event.get("delta", "")
                        result = self.on_input_transcript(delta)
                        if asyncio.iscoroutine(result):
                            await result
                elif etype == "session.closed":
                    logger.info("received session.closed")
                    self._closed_event.set()
                    break
                elif etype == "error":
                    logger.error(f"translate error: {event}")
        except websockets.ConnectionClosed as e:
            logger.info(f"WS closed: {e}")
            self._closed_event.set()

    async def close(self) -> None:
        if self._ws is None:
            return
        if not self._closing:
            self._closing = True
            try:
                await self._ws.send(json.dumps({"type": "session.close"}))
                logger.info("sent session.close, waiting for session.closed")
            except Exception as e:
                logger.warning(f"error sending session.close: {e}")
            try:
                await asyncio.wait_for(self._closed_event.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("timed out waiting for session.closed")
        try:
            await self._ws.close()
        except Exception:
            pass
        self._ws = None
