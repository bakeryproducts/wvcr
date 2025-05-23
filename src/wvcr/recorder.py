import wave
import pyaudio
import threading
import time
from pathlib import Path

import pyperclip
from loguru import logger

from wvcr.config import AudioConfig
from wvcr.common import create_key_monitor
from wvcr.notification_manager import NotificationManager


class VoiceRecorder:
    def __init__(self, notifier: NotificationManager = None, use_evdev=False):
        self.config = AudioConfig()
        self.notifier = notifier or NotificationManager()
        self.use_evdev = use_evdev
        self.recording = False
        self.frames = []
        
    def _record_audio(self):
        """Record audio in a separate thread."""
        p = pyaudio.PyAudio()
        
        # Open audio stream
        stream = p.open(
            format=self.config.FORMAT,
            channels=self.config.CHANNELS,
            rate=self.config.RATE,
            input=True,
            frames_per_buffer=self.config.CHUNK
        )
        
        logger.info("Recording started")
        self.notifier.send_notification("Recording", "Recording started. Press ESC to stop.")
        
        start_time = time.time()
        self.recording = True
        self.frames = []
        
        # Record audio in chunks
        while self.recording and (time.time() - start_time) < self.config.MAX_DURATION:
            data = stream.read(self.config.CHUNK)
            self.frames.append(data)
        
        # Clean up
        stream.stop_stream()
        stream.close()
        p.terminate()
        logger.info("Recording stopped")
        self.notifier.send_notification("Recording", "Recording finished")
    
    def record(self, output_file: Path) -> Path:
        """
        Start recording audio, stopping when escape key is pressed.
        
        Args:
            output_file: Path to save the recorded audio
            
        Returns:
            Path to the saved audio file
        """
        # Create directory if it doesn't exist
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Start recording in a separate thread
        record_thread = threading.Thread(target=self._record_audio)
        record_thread.start()
        
        # Monitor for keypress to stop recording
        stop_key = self.config.STOP_KEY
        key_monitor = create_key_monitor(stop_key, self._stop_recording, prefer_evdev=self.use_evdev)
        key_monitor.start()
        
        # Wait for recording to finish
        record_thread.join()
        key_monitor.stop()
        
        # Save the recording
        self._save_wav(output_file)
        
        return output_file
    
    def _stop_recording(self):
        """Stop the recording."""
        self.recording = False
    
    def _save_wav(self, output_file: Path):
        """Save the recorded audio frames to a WAV file."""
        p = pyaudio.PyAudio()
        wf = wave.open(str(output_file), 'wb')
        wf.setnchannels(self.config.CHANNELS)
        wf.setsampwidth(p.get_sample_size(self.config.FORMAT))
        wf.setframerate(self.config.RATE)
        wf.writeframes(b''.join(self.frames))
        wf.close()
        p.terminate()
        
        logger.info(f"Audio saved to {output_file}")