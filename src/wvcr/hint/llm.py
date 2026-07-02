from __future__ import annotations

from loguru import logger
from google import genai
from google.genai import types

MODEL = "gemini-3.5-flash"

HINT_PROMPT = (
    "You are a live assistant listening to a conversation. The audio contains "
    "both my voice and the other participants, mixed together. Based on the most "
    "recent part of the conversation, give me one immediately useful hint or answer "
    "I can act on right now. No preamble, no restating the question. "
    "Respond in Russian only. "
    "Plain text, no markdown formatting. "
    "Short sentences, each on its own line separated by \\n."
)


def get_hint(audio_bytes: bytes, api_key: str, mime_type: str = "audio/mp3") -> str:
    client = genai.Client(api_key=api_key)
    tools = [types.Tool(google_search=types.GoogleSearch())]
    response = client.models.generate_content(
        model=MODEL,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.LOW,
            ),
            tools=tools,
        ),
        contents=[
            HINT_PROMPT,
            types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
        ],
    )
    text = getattr(response, "text", None) or ""
    logger.debug(f"hint received {len(text)} chars")
    return text.strip()
