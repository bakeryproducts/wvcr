
import pytest
from wvcr.recorder import VoiceRecorder
from wvcr.config import AudioConfig

@pytest.fixture
def config():
    return AudioConfig()

@pytest.fixture
def recorder(config):
    return VoiceRecorder(config)

def test_recorder_initialization(recorder):
    assert recorder is not None
    assert recorder.config is not None

def test_recorder_config(recorder, config):
    assert recorder.config.CHANNELS == config.CHANNELS
    assert recorder.config.RATE == config.RATE
    assert recorder.config.OUTPUT_FORMAT == config.OUTPUT_FORMAT