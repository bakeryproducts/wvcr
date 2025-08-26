import pyperclip
from pathlib import Path
from typing import Optional, Tuple

from .base import BaseMode
from ..services.transcription_service import transcribe_audio
from ..services.text_processing_service import explain
from ..services.file_service import save_text_to_file, create_output_file_path


class ExplainMode(BaseMode):
    def process(self, audio_file: Path, **kwargs) -> Tuple[str, Optional[Path]]:
        transcription = transcribe_audio(audio_file, self.config)
        
        transcribe_file = create_output_file_path("transcribe")
        save_text_to_file(transcription, transcribe_file)
        
        explanation = explain(transcription, self.config)
        
        explain_file = create_output_file_path("explain")
        save_text_to_file(explanation, explain_file)
        
        pyperclip.copy(explanation)
        
        self._send_notification(explanation)
        
        return explanation, explain_file
