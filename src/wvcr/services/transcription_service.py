"""Сервис для транскрипции аудио файлов."""

from pathlib import Path
from wvcr.config import OAIConfig


def transcribe_audio(audio_file: Path, config: OAIConfig) -> str:
    """Транскрибировать аудио файл используя OpenAI Whisper API."""
    try:
        with open(audio_file, 'rb') as audio:
            transcription = config.client.audio.transcriptions.create(
                model=config.STT_MODEL,
                file=audio
            )
        return transcription.text
    except Exception as e:
        raise Exception(f"Transcription failed: {str(e)}")
