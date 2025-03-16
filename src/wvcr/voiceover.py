import pyperclip
from pathlib import Path
from loguru import logger

from wvcr.player import SpeechPlayer

def generate_speech(text: str, output_file: Path, config):
    """Generate speech from text using OpenAI TTS API."""
    try:
        response = config.client.audio.speech.create(
            model="tts-1",
            voice="onyx", 
            input=text,
            response_format="wav",
        )
        response.stream_to_file(str(output_file))
        return True
    except Exception as e:
        logger.exception(f"Could not generate speech: {str(e)}")
        return False

def voiceover_clipboard(output_file: Path, config, notifier, play=True):
    """Convert clipboard content to speech."""
    text = pyperclip.paste()
    if not text:
        logger.warning("Clipboard is empty")
        return False
    
    logger.info(f"Generating speech for text: {text[:100]}...")
    generated = generate_speech(text, output_file, config)
    if generated and play:
        play_speech(output_file, notifier)
    return generated


def play_speech(input_file: Path, notifier, stop_on_key=True):
    """Play generated speech file."""
    player = SpeechPlayer(notifier)
    player.play(input_file, stop_on_key)


