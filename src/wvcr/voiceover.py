import pyperclip
from pathlib import Path
from loguru import logger
import wave
import pyaudio
import threading
import io

from wvcr.config import AudioConfig, OAIConfig
from wvcr.common import create_key_monitor
from wvcr.notification_manager import NotificationManager

# from wvcr.player import SpeechPlayer



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


def generate_gpt_speech(text: str, output_file: Path, config):
    """Generate speech from text using OpenAI GPT TTS API."""
    try:
        response = config.client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="coral",
            input=text,
            instructions="Speak in a natural and engaging tone.",
            response_format="wav",
        )
        response.stream_to_file(str(output_file))
        return True
    except Exception as e:
        logger.exception(f"Could not generate GPT speech: {str(e)}")
        return False


def save_pcm_to_wav(pcm_data, output_file, sample_rate=24000, channels=1, sample_width=2):
    """Convert PCM data to a WAV file and save it."""
    try:
        with wave.open(str(output_file), 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)  # 2 bytes for 16-bit audio
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
        return True
    except Exception as e:
        logger.exception(f"Error saving WAV file: {e}")
        return False

def _stream_audio_with_buffer(response, stream, pcm_data, stop_event, buffer_size=5):
    """Helper function to handle streaming audio with buffer to prevent stuttering."""
    initial_buffer = []
    buffering = True
    
    for chunk in response.iter_bytes(1024):
        if stop_event and stop_event.is_set():
            logger.info("Stopping audio playback as requested")
            break
        
        if buffering:
            initial_buffer.append(chunk)
            if len(initial_buffer) >= buffer_size:
                # Play buffered audio all at once
                for buffered_chunk in initial_buffer:
                    stream.write(buffered_chunk)
                    if pcm_data is not None:
                        pcm_data.extend(buffered_chunk)
                buffering = False
        else:
            stream.write(chunk)
            if pcm_data is not None:
                pcm_data.extend(chunk)
    
    return True

def write_audio(stream, text, config, output_file=None, stop_event=None, use_gpt_tts=True, buffer_size=5):
    """Write audio to stream and optionally save to file."""
    try:
        pcm_data = bytearray() if output_file else None

        # Create the response with appropriate parameters
        create_params = {
            "input": text,
            "response_format": "pcm"
        }
        
        if use_gpt_tts:
            model = "gpt-4o-mini-tts"
            voice = "alloy"
            instructions = """
Voice Affect: Low, smoove, fast
Pacing: Fast and deliberate
Pronunciation: Smooth, flowing articulation
"""
            create_params["instructions"] = instructions
        else:
            model = "tts-1"
            voice = "alloy"

        create_params["voice"] = voice
        create_params["model"] = model
            
        with config.client.audio.speech.with_streaming_response.create(**create_params) as response:
            _stream_audio_with_buffer(response, stream, pcm_data, stop_event, buffer_size)

        # If we need to save to a file, convert the collected PCM data to WAV
        if output_file and pcm_data:
            return save_pcm_to_wav(pcm_data, output_file)
            
        return True
    except Exception as e:
        logger.exception(f"Error writing to stream: {e}")
        return False


def play_audio(text, config, output, stop_event=None, use_gpt_tts=True):
    """Play audio file using PyAudio."""
    try:
        p = pyaudio.PyAudio()
        stream = p.open(format=8,
                        channels=1,
                        rate=24_000,
                        output=True)

        # Write audio to stream
        result = write_audio(stream, text, config, output, stop_event, use_gpt_tts)
        
        stream.stop_stream()
        stream.close()
        p.terminate()
        return result
    except Exception as e:
        logger.exception(f"Error playing audio: {e}")
        return False


def voiceover_clipboard(output_file: Path, config: OAIConfig, notifier=None, play=False, use_evdev=False, use_gpt_tts=True):
    """Get text from clipboard, convert to speech, and save to file."""
    if notifier is None:
        notifier = NotificationManager()
    
    # Get clipboard content
    text = pyperclip.paste()
    if not text:
        notifier.send_notification("Error", "Clipboard is empty")
        return False
    
    
    try:
        notifier.send_notification("Processing", "Converting text to speech...")

        if play:
            # Create stop flag for playback
            stop_playback = threading.Event()
            
            # Function to stop playback
            def stop_callback():
                logger.error('Stop key pressed, stopping playback')
                stop_playback.set()
                notifier.send_notification("Playback", "Playback stopped")
            
            # Start key monitor
            audio_config = AudioConfig()
            key_monitor = create_key_monitor(audio_config.STOP_KEY, stop_callback, prefer_evdev=use_evdev)
            key_monitor.start()
            
            # Play in separate thread so we can monitor for stop key
            play_thread = threading.Thread(target=play_audio, args=(text, config, output_file, stop_playback, use_gpt_tts))
            play_thread.start()
            
            # Wait for playback to finish or stop key
            play_thread.join()
            
            # Clean up
            key_monitor.stop()
        else:
            # Just save to file without playing
            p = pyaudio.PyAudio()
            stream = p.open(format=8, channels=1, rate=24_000, output=True)
            write_audio(stream, text, config, output_file, use_gpt_tts=use_gpt_tts)
            stream.stop_stream()
            stream.close()
            p.terminate()
        
        notifier.send_notification("Success", "Voiceover saved to file")
        return True
    
    except Exception as e:
        logger.exception(f"Voiceover error: {e}")
        notifier.send_notification("Error", f"Failed: {str(e)}")
        return False


