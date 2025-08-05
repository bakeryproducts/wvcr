import os
import re
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse

import yt_dlp
import requests
from loguru import logger

from ..services.file_service import create_download_audio_file_path


class DownloadService:
    
    def __init__(self, temp_dir: Optional[Path] = None):
        self.temp_dir = temp_dir or Path(tempfile.gettempdir())
        
    def download_and_extract_audio( self, url: str, output_format: str = "wav") -> Path:
        logger.info(f"Processing URL: {url}")
        
        if self._is_youtube_url(url):
            return self._download_youtube_audio(url, output_format)
        else:
            return self._download_direct_url(url, output_format)
    

    def _is_youtube_url(self, url: str) -> bool:
        """Check if URL is a YouTube URL."""
        youtube_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=',
            r'(?:https?://)?(?:www\.)?youtu\.be/',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/',
            r'(?:https?://)?(?:www\.)?youtube\.com/shorts/'
        ]
        return any(re.match(pattern, url) for pattern in youtube_patterns)
    

    def _download_youtube_audio( self, url: str, output_format: str = "wav") -> Path:
        output_format = 'wav'
        output_file = self.temp_dir / f"youtube_audio.{output_format}"
        
        ydl_opts = {
            'format': 'worstaudio/worst',
            'outtmpl': str(self.temp_dir / 'youtube_audio.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': output_format,
                'preferredquality': '64',
            }],
            # 'quiet': True,
            # 'no_warnings': True,
            'force_ipv4': True
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            logger.info(f"YouTube audio downloaded to {output_file}")
            
        except Exception as e:
            logger.exception(e)
            logger.error(f"Error downloading YouTube audio: {e}")
            raise
    
        return self._process_audio(output_file)


    def _download_direct_url( self, url: str, output_format: str = "wav") -> Path:
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Get file extension from URL or content-type
            parsed_url = urlparse(url)
            file_extension = Path(parsed_url.path).suffix.lower()
            
            if not file_extension:
                content_type = response.headers.get('content-type', '')
                if 'audio' in content_type:
                    file_extension = '.mp3'  # default
                elif 'video' in content_type:
                    file_extension = '.mp4'  # default
                else:
                    file_extension = '.tmp'
            
            temp_file = self.temp_dir / f"downloaded_file{file_extension}"
            
            # Download file
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"File downloaded to {temp_file}")
            
            # If it's already an audio file and format matches, process and save to final location
            if file_extension[1:] == output_format and self._is_audio_file(temp_file):
                return self._process_audio(temp_file)
            
            # Extract audio if it's a video file or convert format
            return self._extract_audio_with_ffmpeg(temp_file, output_format)
            
        except Exception as e:
            logger.error(f"Error downloading file from URL: {e}")
            raise
    

    def _is_audio_file(self, file_path: Path) -> bool:
        audio_extensions = {'.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.wma'}
        return file_path.suffix.lower() in audio_extensions
    

    def _extract_audio_with_ffmpeg( self, input_file: Path, output_format: str = "mp3") -> Path:
        # Create final output file path
        final_audio_file = create_download_audio_file_path(output_format)
        
        cmd = [
            'ffmpeg', '-i', str(input_file),
            '-vn',  # no video
            '-acodec', 'pcm_s16le' if output_format == 'wav' else 'libmp3lame',
            '-ar', '44100',  # sample rate
            '-ac', '2',      # stereo
            '-af', 'atempo=2.0',  # Apply speed processing directly
            '-y',            # overwrite output
            str(final_audio_file)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Audio extracted and processed to {final_audio_file}")
            
            # Clean up original file
            if input_file != final_audio_file:
                input_file.unlink(missing_ok=True)
            
            return final_audio_file
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error extracting audio with ffmpeg: {e}")
            raise

    
    def _process_audio(self, audio_file: Path) -> Path:
        # Create final output file path
        final_audio_file = create_download_audio_file_path("mp3")
        
        cmd = [
            'ffmpeg', '-i', str(audio_file),
            '-af', 'atempo=2.0',
            '-y',
            str(final_audio_file)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Audio processed and saved to {final_audio_file}")
            
            # Clean up temporary file
            audio_file.unlink(missing_ok=True)
            
            return final_audio_file
            
        except subprocess.CalledProcessError as e:
            logger.warning(f"Audio processing failed, copying original to final location: {e}")
            # If processing fails, copy the original file to the final location
            import shutil
            shutil.copy2(audio_file, final_audio_file)
            audio_file.unlink(missing_ok=True)
            return final_audio_file
    

    def cleanup_temp_files(self):
        """Clean up temporary files created during download."""
        try:
            for file in self.temp_dir.glob("youtube_audio.*"):
                file.unlink(missing_ok=True)
            for file in self.temp_dir.glob("downloaded_file.*"):
                file.unlink(missing_ok=True)
            for file in self.temp_dir.glob("extracted_audio.*"):
                file.unlink(missing_ok=True)
            for file in self.temp_dir.glob("processed_*"):
                file.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Error cleaning up temp files: {e}")
