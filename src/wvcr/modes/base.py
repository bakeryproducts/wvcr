from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple

from wvcr.config import OAIConfig
from wvcr.notification_manager import NotificationManager


class BaseMode(ABC):
    
    def __init__(self, config: OAIConfig, notifier: NotificationManager):
        self.config = config
        self.notifier = notifier
    
    @abstractmethod
    def process(self, audio_file: Path, **kwargs) -> Tuple[str, Optional[Path]]:
        pass
    
    def _send_notification(self, text: str, cutoff: Optional[int] = None):
        self.notifier.send_notification(
            'Voice Transcription', 
            text, 
            font_size='28px', 
            cutoff=cutoff
        )
