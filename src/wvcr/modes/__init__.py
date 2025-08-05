from enum import Enum

class ProcessingMode(Enum):
    TRANSCRIBE = "transcribe"
    ANSWER = "answer"
    EXPLAIN = "explain"
    VOICEOVER = "voiceover"

from .base import BaseMode
from .transcribe_mode import TranscribeMode
from .answer_mode import AnswerMode
from .explain_mode import ExplainMode
from .voiceover_mode import VoiceoverMode
from .factory import ModeFactory

__all__ = [
    'ProcessingMode',
    'BaseMode',
    'TranscribeMode',
    'AnswerMode', 
    'ExplainMode',
    'VoiceoverMode',
    'ModeFactory'
]
