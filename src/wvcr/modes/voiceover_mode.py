from pathlib import Path
from typing import Optional, Tuple
from loguru import logger

from .base import BaseMode
from ..services.file_service import create_audio_file_path
from wvcr.voiceover import voiceover_clipboard


class VoiceoverMode(BaseMode):
    def process(self, audio_file: Path = None, use_evdev: bool = False, **kwargs) -> Tuple[str, Optional[Path]]:
        if audio_file is None:
            audio_file = create_audio_file_path("voiceover", "wav")
        
        self.notifier.send_notification(
            'Voiceover started', 
            'Voiceover started, press escape to stop'
        )
        
        success = voiceover_clipboard(
            audio_file, 
            self.config, 
            notifier=self.notifier, 
            play=True, 
            use_evdev=use_evdev
        )
        
        if success:
            logger.info(f"Voiceover saved to {audio_file}")
            return "Voiceover completed", audio_file
        else:
            return "Voiceover cancelled", None
