from enum import Enum

class ProcessingMode(Enum):
    TRANSCRIBE = "transcribe"
    TRANSCRIBE_URL = "transcribe_url"
    ANSWER = "answer"
    EXPLAIN = "explain"
    VOICEOVER = "voiceover"

from .base import BaseMode
from .transcribe_mode import TranscribeMode
from .transcribe_url_mode import TranscribeUrlMode
from .answer_mode import AnswerMode
from .explain_mode import ExplainMode
from .voiceover_mode import VoiceoverMode
from .factory import ModeFactory

__all__ = [
    'ProcessingMode',
    'BaseMode',
    'TranscribeMode',
    'TranscribeUrlMode',
    'AnswerMode', 
    'ExplainMode',
    'VoiceoverMode',
    'ModeFactory'
]
