import wave
import threading
from pathlib import Path

import pyaudio
from loguru import logger
from wvcr.config import OAIConfig, GeminiConfig


def _save_pcm_to_wav(pcm_data, output_file, sample_rate=24000, channels=1, sample_width=2):
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


def _generate_and_play_oai(
    text: str,
    config: OAIConfig,
    output_file: Path,
    stop_event: threading.Event | None = None,
    use_gpt_tts: bool = True
) -> bool:
    try:
        p = pyaudio.PyAudio()
        stream = p.open(format=8, channels=1, rate=24_000, output=True)
        
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
            
            logger.debug(f"Generating OpenAI TTS with model={model}, voice={voice}")
            
            with config.client.audio.speech.with_streaming_response.create(**create_params) as response:
                _stream_audio_with_buffer(response, stream, pcm_data, stop_event, buffer_size=5)

            # If we need to save to a file, convert the collected PCM data to WAV
            if output_file and pcm_data:
                return _save_pcm_to_wav(pcm_data, output_file)
                
            return True
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
            
    except Exception as e:
        logger.exception(f"OpenAI TTS generation failed: {e}")
        return False


def _generate_and_play_gemini_non_streaming(
    text: str,
    config: GeminiConfig,
    output_file: Path,
    stop_event: threading.Event | None = None
) -> bool:
    """Generate and play TTS using Gemini API (non-streaming)."""
    try:
        from google.genai import types
        
        p = pyaudio.PyAudio()
        stream = p.open(format=8, channels=1, rate=24_000, output=True)
        
        try:
            logger.debug("Generating Gemini TTS with model=gemini-2.5-flash-preview-tts, voice=Kore")
            
            # Generate TTS using Gemini API
            client = config.get_client()
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name='Kore',
                            )
                        )
                    ),
                )
            )
            logger.debug("Gemini TTS response received")
            
            # Extract audio data from response
            audio_data = response.candidates[0].content.parts[0].inline_data.data
            logger.debug(f"Gemini TTS audio data: {len(audio_data)} bytes")
            
            # Play audio with buffering to prevent stuttering/clicking
            chunk_size = 4096  # Larger chunks to reduce stuttering
            buffer_size = 5
            initial_buffer = []
            buffering = True
            
            for i in range(0, len(audio_data), chunk_size):
                if stop_event and stop_event.is_set():
                    logger.info("Stopping Gemini TTS playback as requested")
                    break
                
                chunk = audio_data[i:i + chunk_size]
                
                if buffering:
                    initial_buffer.append(chunk)
                    if len(initial_buffer) >= buffer_size:
                        # Play buffered audio all at once
                        for buffered_chunk in initial_buffer:
                            stream.write(buffered_chunk)
                        buffering = False
                else:
                    stream.write(chunk)
            
            # Save to file if requested
            if output_file:
                return _save_pcm_to_wav(audio_data, output_file)
            
            return True
            
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
            
    except Exception as e:
        logger.exception(f"Gemini TTS generation failed: {e}")
        return False


def _generate_and_play_gemini(
    text: str,
    config: GeminiConfig,
    output_file: Path,
    stop_event: threading.Event | None = None
) -> bool:
    """Generate and play TTS using Gemini API with streaming."""
    try:
        from google.genai import types, Client
        
        p = pyaudio.PyAudio()
        stream = p.open(format=8, channels=1, rate=24_000, output=True)
        
        try:
            logger.debug("Generating streaming Gemini TTS with model=gemini-2.5-flash-tts, voice=Kore")
            
            client: Client = config.get_client()
            
            generate_content_config = types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    language_code="en-us",
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name="Kore",
                        )
                    )
                ),
            )
            
            final_audio_data = bytearray() if output_file else None
            chunk_count = 0
            buffer_size = 5
            initial_buffer = []
            buffering = True
            

            # this shit wont stream properly, i think its genai-gemini problem
            # comes out in one chunk
            for chunk in client.models.generate_content_stream(
                # model="gemini-2.5-flash-preview-tts",
                # model="gemini-2.5-flash-preview-native-audio-dialog",
                # model="gemini-2.5-flash-tts",
                model="gemini-2.5-flash-native-audio-preview-12-2025",
                contents=text,
                config=generate_content_config,
            ):
                if stop_event and stop_event.is_set():
                    logger.info("Stopping streaming Gemini TTS playback as requested")
                    break
                
                chunk_count += 1
                
                # Check if chunk has audio data
                if (
                    chunk.candidates is None
                    or not chunk.candidates
                    or chunk.candidates[0].content is None
                    or not chunk.candidates[0].content.parts
                ):
                    continue
                
                part = chunk.candidates[0].content.parts[0]
                if part.inline_data and part.inline_data.data:
                    audio_chunk = part.inline_data.data
                    
                    # Accumulate for file saving
                    if final_audio_data is not None:
                        final_audio_data.extend(audio_chunk)
                    
                    # Play with buffering to prevent stuttering
                    if buffering:
                        initial_buffer.append(audio_chunk)
                        logger.debug(f"Buffering chunk {len(initial_buffer)}/{buffer_size}, size: {len(audio_chunk)} bytes")
                        if len(initial_buffer) >= buffer_size:
                            # Play buffered audio all at once
                            total_buffered = sum(len(bc) for bc in initial_buffer)
                            logger.debug(f"Playing {len(initial_buffer)} buffered chunks, total: {total_buffered} bytes")
                            for buffered_chunk in initial_buffer:
                                stream.write(buffered_chunk)
                            initial_buffer.clear()
                            buffering = False
                            logger.debug("Buffering complete, switching to direct playback")
                    else:
                        logger.debug(f"Direct playback: {len(audio_chunk)} bytes")
                        stream.write(audio_chunk)
            
            # Play any remaining buffered chunks that didn't reach buffer_size
            if buffering and initial_buffer:
                total_buffered = sum(len(bc) for bc in initial_buffer)
                logger.debug(f"Playing {len(initial_buffer)} remaining buffered chunks, total: {total_buffered} bytes")
                for buffered_chunk in initial_buffer:
                    stream.write(buffered_chunk)
            
            logger.debug(f"Gemini TTS streaming completed: {chunk_count} chunks received")
            
            # Save to file if requested
            if output_file and final_audio_data:
                return _save_pcm_to_wav(bytes(final_audio_data), output_file)
            
            return True
            
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
            
    except Exception as e:
        logger.exception(f"Gemini TTS streaming generation failed: {e}")
        return False


class TTSService:
    def __init__(self, oai_config: OAIConfig, gemini_config: GeminiConfig):
        self.oai_config = oai_config
        self.gemini_config = gemini_config
    
    def generate_and_play(
        self, 
        text: str, 
        output_file: Path, 
        provider: str = "openai",
        stop_event: threading.Event | None = None) -> bool:

        logger.info(f"Generating TTS with provider={provider}")
        
        try:
            if provider == "openai" or not self.gemini_config:
                return _generate_and_play_oai(
                    text=text,
                    config=self.oai_config,
                    output_file=output_file,
                    stop_event=stop_event,
                    use_gpt_tts=True
                )
            elif provider == "gemini":
                return _generate_and_play_gemini_non_streaming(
                    text=text,
                    config=self.gemini_config,
                    output_file=output_file,
                    stop_event=stop_event
                )
            else:
                raise ValueError(f"Unsupported provider: {provider}")
                
        except Exception as e:
            logger.exception(f"TTS generation failed: {e}")
            return False
