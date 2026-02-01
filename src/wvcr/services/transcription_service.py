from pathlib import Path
from typing import Any

from loguru import logger

from wvcr.config import GeminiConfig, OAIConfig


TRANSCRIBE_PROMPT = (
    "Convert this audio into clean, structured text. "
    "Capture the core message accurately but remove filler words, false starts, and verbal noise. "
    "Reorganize sentences for clarity if needed while preserving the original meaning and intent. "
    "Output ONLY the processed transcript - no meta-commentary, no greetings, no sign-offs, no explanations. "
    "Start immediately with the content."
)

def transcribe_audio(audio_file: Path, config: OAIConfig | GeminiConfig | Any, language: str = "ru") -> str:
    provider = getattr(config, "provider", None)
    logger.info(f"Transcribing with provider={provider}")

    try:
        if provider == "openai":
            return transcribe_oai(audio_file, config, language)
        elif provider == "gemini":
            return transcribe_gemini(audio_file, config, language)
        else:
            raise TypeError( f"Unsupported provider: {provider} (config type={type(config)})")
    except Exception as e:
        raise Exception(f"Transcription failed: {e}") from e


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
