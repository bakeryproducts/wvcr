import pyperclip
from pathlib import Path
from typing import Optional, Tuple

from .base import BaseMode
from ..services.transcription_service import transcribe_audio
from ..services.text_processing_service import answer_question
from ..services.file_service import save_text_to_file, create_output_file_path


class AnswerMode(BaseMode):
    
    def process(self, audio_file: Path, **kwargs) -> Tuple[str, Optional[Path]]:
        transcription = transcribe_audio(audio_file, self.config)
        
        transcribe_file = create_output_file_path("transcribe")
        save_text_to_file(transcription, transcribe_file)
        
        answer = answer_question(transcription, self.config)
        
        answer_file = create_output_file_path("answer")
        save_text_to_file(answer, answer_file)
        
        pyperclip.copy(answer)
        
        self._send_notification(answer)
        return answer, answer_file
