import re
import pyperclip
from pathlib import Path
from typing import Optional, Tuple
from loguru import logger

from .base import BaseMode
from ..services.transcription_service import transcribe_audio
from ..services.file_service import save_text_to_file, create_output_file_path
from ..services.download_service import DownloadService


class TranscribeUrlMode(BaseMode):
    def process(self, audio_file: Path = None, **kwargs) -> Tuple[str, Optional[Path]]:
        url = pyperclip.paste().strip()
        if not url:
            raise ValueError("No URL found in clipboard")
        
        logger.info(f"Processing URL from clipboard: {url}")
        
        if not self._is_valid_url(url):
            raise ValueError(f"Invalid URL: {url}")
        
        download_service = DownloadService()
        
        try:
            self._send_notification("Downloading audio from URL...")
            audio_file = download_service.download_and_extract_audio(url, output_format="mp3")
            
            logger.info(f"Audio file ready: {audio_file}")
            
            self._send_notification("Transcribing audio...")
            transcription = transcribe_audio(audio_file, self.config)

            # postprocess transcription, add \n on .
            transcription = re.sub(r'(?<=[.!?]) +', '\n', transcription) 
            
            output_file = create_output_file_path("transcribe")
            save_text_to_file(transcription, output_file)
            
            pyperclip.copy(transcription)
            
            self._send_notification(transcription, cutoff=100)
            return transcription, output_file
            
        except Exception as e:
            error_msg = f"Error processing URL: {str(e)}"
            logger.error(error_msg)
            self._send_notification(error_msg)
            raise
        finally:
            # Clean up temporary files
            download_service.cleanup_temp_files()
    
    def _is_valid_url(self, url: str) -> bool:
        """Basic URL validation."""
        return url.startswith(('http://', 'https://')) and len(url) > 10
