from __future__ import annotations

from loguru import logger
from google import genai
from google.genai import types

MODEL = "gemini-3.5-flash"

HINT_PROMPT = """You are a live assistant listening to a conversation.
The audio mixes my voice with other participants.

FOCUS: I pressed the hint button right now, this instant, because I need
help with what is being said RIGHT NOW. Anchor entirely on the last
sentence or phrase at the very end of the clip. If the topic changed
partway through the audio, ignore the earlier topic completely - only the
final moment matters, no matter how brief it was.

TASK: Give me one immediately useful hint about that exact topic - a fact,
number, name, definition, risk, counterargument, or next step I can act on.
Always surface something useful, even with no explicit question asked.
Never just ask a question back, and never say there is nothing to add - if
the topic is unclear, give the most useful info about the closest thing you
can identify from the last moment of audio.

FORMAT:
- No preamble, no restating what was said, no meta-commentary about the audio.
- Russian only.
- Plain text, no markdown.
- Short sentences, one per line, separated by \\n.
"""


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
