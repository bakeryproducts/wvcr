import pyperclip
from pathlib import Path
from typing import Optional, Tuple

from .base import BaseMode
from ..services.transcription_service import transcribe_audio
from ..services.file_service import save_text_to_file, create_output_file_path


class TranscribeMode(BaseMode):
    def process(self, audio_file: Path, **kwargs) -> Tuple[str, Optional[Path]]:
        transcription = transcribe_audio(audio_file, self.config)
        output_file = create_output_file_path("transcribe")
        save_text_to_file(transcription, output_file)
        
        pyperclip.copy(transcription)
        
        self._send_notification(transcription, cutoff=100)
        return transcription, output_file
