from pathlib import Path

from loguru import logger

from wvcr.config import OAIConfig


def transcribe_audio(audio_file: Path, config: OAIConfig) -> str:
    try:
        with open(audio_file, 'rb') as audio:
            transcription = config.client.audio.transcriptions.create(
                model=config.STT_MODEL,
                file=audio,
                language="ru",
                chunking_strategy=None
            )
            logger.debug(transcription)
            logger.info(f"Transcription usage {transcription.usage}")
        return transcription.text
    except Exception as e:
        raise Exception(f"Transcription failed: {str(e)}")
