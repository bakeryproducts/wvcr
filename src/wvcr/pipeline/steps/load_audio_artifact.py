from pathlib import Path

from loguru import logger
from google.genai import types

from ..step import Step

class LoadAudioArtifact(Step):
    name = "load_audio_artifact"
    requires = {"audio_file"}
    provides = {"audio_part"}

    def execute(self, state, ctx):
        audio_file = state.get("audio_file")

        if not isinstance(audio_file, Path):
            audio_file = Path(audio_file)

        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        # Read raw audio bytes
        with open(audio_file, "rb") as f:
            audio_data = f.read()

        # Determine MIME type based on file extension
        # ADK supports various audio formats
        suffix = audio_file.suffix.lower()
        mime_type_map = {
            ".wav": "audio/wav",
            ".mp3": "audio/mp3",
            ".m4a": "audio/mp4",
            ".ogg": "audio/ogg",
            ".flac": "audio/flac",
            ".pcm": "audio/pcm",
        }

        mime_type = mime_type_map.get(suffix, "audio/wav")  # default to wav

        # Create ADK Part using from_bytes constructor
        audio_part = types.Part.from_bytes(data=audio_data, mime_type=mime_type)

        state.set("audio_part", audio_part)

        logger.info(
            f"Loaded audio artifact: {audio_file.name} "
            f"({len(audio_data)} bytes, {mime_type})"
        )
