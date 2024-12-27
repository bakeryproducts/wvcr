import pytest
import wave
from pathlib import Path
from unittest.mock import MagicMock
from wvcr.player import SpeechPlayer
from wvcr.config import AudioConfig

@pytest.fixture
def mock_notifier():
    return MagicMock()

@pytest.fixture
def player(mock_notifier):
    return SpeechPlayer(mock_notifier)

@pytest.fixture
def test_audio_file(tmp_path):
    # Create a simple test WAV file
    audio_file = Path('tests/data') / "noti_audio.mp3"
    return audio_file

def test_player_initialization(player):
    assert player is not None
    assert isinstance(player.config, AudioConfig)
    assert player.playing is False


def test_play_audio_file(player, test_audio_file):
    player.play(Path(test_audio_file), stop_on_key=False)
    assert player.playing is True
