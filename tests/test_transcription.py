from pathlib import Path
from loguru import logger

import pytest
from wvcr.main import TranscriptionHandler

@pytest.fixture
def handler():
    return TranscriptionHandler()

def test_transcription_handler_initialization(handler):
    assert handler is not None
    assert handler.notifier is not None

def test_handle_transcription(handler, tmp_path):
    # Create a dummy audio file
    audio_file = Path('tests/data') / "capital_gb.mp3"
    
    # Test with test mode
    transcription, transcript_file = handler.handle_transcription(audio_file)
    logger.info(f"Transcription: {transcription}")
    
    assert transcription is not None
    assert isinstance(transcription, str)
    assert transcript_file.exists()