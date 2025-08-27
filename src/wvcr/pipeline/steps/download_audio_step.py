from ..step import Step
from wvcr.services.download_service import DownloadService

class DownloadAudioStep(Step):
    name = "download_audio"
    requires = {"url"}
    provides = {"audio_file"}

    def execute(self, state, ctx):
        url = state.get("url")
        if not url:
            raise ValueError("No URL found")
        
        if not self._is_valid_url(url):
            raise ValueError(f"Invalid URL: {url}")
        
        download_service = DownloadService()
        
        try:
            audio_file = download_service.download_and_extract_audio(url, output_format="mp3")
            state.set("audio_file", audio_file)
        finally:
            # Clean up temporary files
            download_service.cleanup_temp_files()
    
    def _is_valid_url(self, url: str) -> bool:
        """Basic URL validation."""
        return url.startswith(('http://', 'https://')) and len(url) > 10
