import re
from pathlib import Path
from typing import Any

from loguru import logger

from wvcr.config import GeminiConfig, OAIConfig


TRANSCRIBE_PROMPT = (
    "Transcribe the spoken audio accurately into clean, well-punctuated text. "
    "Remove filler words, false starts, and verbal noise while preserving the original meaning. "
    "Do not include timestamps, timecodes, speaker labels, or meta-commentary."
)

BCP47 = {"ru": "ru-RU", "en": "en-US", "uk": "uk-UA", "de": "de-DE", "es": "es-419", "fr": "fr-FR"}

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
    usage = getattr(transcription, "usage", None)
    if usage:
        logger.info(f"Transcription usage {usage}")
    return transcription.text


def transcribe_gemini(
    audio_file: Path, config: GeminiConfig, language: str = "ru"
) -> str:
    client = config.get_client()

    transcription_config: dict[str, Any] = {"mode": "smart"}
    if language:
        transcription_config["language_codes"] = [BCP47.get(language, language)]

    logger.debug("uploading audio to Gemini for transcription")
    uploaded = client.files.upload(file=str(audio_file))
    try:
        interaction = client.interactions.create(
            model=config.STT_MODEL,
            input=[{"type": "audio", "uri": uploaded.uri, "mime_type": uploaded.mime_type}],
            generation_config={"transcription_config": transcription_config},
        )
    finally:
        try:
            client.files.delete(name=uploaded.name)
        except Exception as e:
            logger.warning(f"failed to delete uploaded file: {e}")

    text = (interaction.output_text or "").strip()
    logger.debug(f"Gemini transcription received {len(text)} chars")
    return text
