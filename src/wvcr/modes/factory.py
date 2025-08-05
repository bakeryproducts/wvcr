from wvcr.config import OAIConfig
from wvcr.notification_manager import NotificationManager
from .base import BaseMode
from . import ProcessingMode, TranscribeMode, AnswerMode, ExplainMode, VoiceoverMode


class ModeFactory:
    
    @staticmethod
    def create_mode(mode: ProcessingMode, config: OAIConfig, notifier: NotificationManager) -> BaseMode:
        mode_classes = {
            ProcessingMode.TRANSCRIBE: TranscribeMode,
            ProcessingMode.ANSWER: AnswerMode,
            ProcessingMode.EXPLAIN: ExplainMode,
            ProcessingMode.VOICEOVER: VoiceoverMode,
        }
        
        mode_class = mode_classes.get(mode)
        if not mode_class:
            raise ValueError(f"Unknown mode: {mode}")
            
        return mode_class(config, notifier)
    
    @staticmethod
    def get_available_modes():
        return list(ProcessingMode)
