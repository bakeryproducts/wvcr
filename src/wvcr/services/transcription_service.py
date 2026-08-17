import re
from pathlib import Path
from typing import Any

from loguru import logger

from wvcr.config import GeminiConfig, OAIConfig


TRANSCRIBE_PROMPT = (
    "Convert this audio into clean, structured text. "
    "Capture the core message accurately but remove filler words, false starts, and verbal noise. "
    "Reorganize sentences for clarity if needed while preserving the original meaning and intent. "
    "Output ONLY the processed transcript - no meta-commentary, no greetings, no sign-offs, no explanations. "
    "Never emit timestamps, timecodes, or time markers of any kind - not '[00:05]', not '0:05', not '(5s)', "
    "not bare 'M:SS' pairs, nothing periodic tied to elapsed seconds. This rule applies even mid-sentence "
    "and mid-word: never break a word apart to insert a time marker in the middle of it "
    "(e.g. do not write 'Кар 0:18ты' or 'несло 0:42жно' - the correct output is the unbroken word "
    "'Карты' / 'несложно' with no digits inside it). "
    "Output plain running text only, with no time annotations whatsoever, and with every word left intact. "
    "Start immediately with the content."
)

# Fallback safety net: some models (notably certain Gemini versions) ignore the
# prompt above and still emit periodic "M:SS" markers, sometimes splitting a
# word in half to insert one (e.g. "Кар 0:18ты" -> "Карты"). Strip a leading
# space + timestamp and rejoin, since the model never adds a space after the
# marker when it lands mid-word.
_TIMESTAMP_RE = re.compile(r"\s?(?<!\d)\d{1,2}:\d{2}(?!\d)")


def strip_timestamps(text: str) -> str:
    return _TIMESTAMP_RE.sub("", text)

def transcribe_audio(audio_file: Path, config: OAIConfig | GeminiConfig | Any, language: str = "ru") -> str:
    provider = getattr(config, "provider", None)
    logger.info(f"Transcribing with provider={provider}")

    try:
        if provider == "openai":
            text = transcribe_oai(audio_file, config, language)
        elif provider == "gemini":
            text = transcribe_gemini(audio_file, config, language)
        else:
            raise TypeError( f"Unsupported provider: {provider} (config type={type(config)})")
    except Exception as e:
        raise Exception(f"Transcription failed: {e}") from e

    return strip_timestamps(text)


def transcribe_oai(audio_file: Path, config: OAIConfig, language: str = "ru") -> str:
    from openai import OpenAI

    client: OpenAI = config.get_client()

    logger.debug("sending audio to OpenAI for transcription")

    with open(audio_file, "rb") as audio:
        transcription = client.audio.transcriptions.create(
            model=config.STT_MODEL,
            file=audio,
            language=language,
            prompt=TRANSCRIBE_PROMPT,
            chunking_strategy=None,
        )
    # logger.debug(transcription)
    # usage may not always exist depending on SDK version
    usage = getattr(transcription, "usage", None)
    if usage:
        logger.info(f"Transcription usage {usage}")
    return transcription.text


def transcribe_gemini(
    audio_file: Path, config: GeminiConfig, language: str = "ru"
) -> str:
    from google.genai import types, Client

    client: Client = config.get_client()
    # Determine MIME type from extension (Gemini needs correct mime_type)
    ext = audio_file.suffix.lower()
    mime_map = {
        ".mp3": "audio/mp3",
        ".mpeg": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
        ".mp4": "audio/mp4",
        ".webm": "audio/webm",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")

    with open(audio_file, "rb") as f:
        audio_bytes = f.read()


    logger.debug("sending audio to Gemini for transcription")
    response = client.models.generate_content(
        model=config.STT_MODEL,
        config=types.GenerateContentConfig(
            temperature=config.temperature,
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.LOW,
            ),
        ),
        contents=[
            TRANSCRIBE_PROMPT,
            types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
        ],
    )
    logger.debug(response)

    text = getattr(response, "text", None)
    logger.debug(f"Gemini transcription received {len(text)} chars")
    return text.strip()
