#!/usr/bin/env python3

import sys
import time
import argparse 
from pathlib import Path
import importlib.resources
from datetime import datetime

import wave
import pyaudio
import pyperclip
from loguru import logger
from pynput import keyboard

from wvcr.config import AudioConfig
from wvcr.notification_manager import NotificationManager
from wvcr.openai_client import transcribe_audio, ProcessingMode


PACKAGE_ROOT = Path(importlib.resources.files("wvcr"))
OUTPUT = PACKAGE_ROOT.parent / "output"
OUTPUT.mkdir(exist_ok=True)

logger.add(
    OUTPUT / 'logs' / "{time:YYYY_MM}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)

class VoiceRecorder:
    def __init__(self, config: AudioConfig):
        self.config = config
        self.recording = False
        self.frames = []
        self.listener = None
        self.start_time = None
        self.notifier = NotificationManager()

    def _setup_audio(self):
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=self.config.LOW_QUALITY_FORMAT,
            channels=self.config.CHANNELS,
            rate=self.config.LOW_QUALITY_RATE,
            input=True,
            frames_per_buffer=self.config.LOW_QUALITY_CHUNK
        )

    def _send_notification(self, title: str, text: str):
        self.notifier.send_notification(title, text, timeout=1, color='#FF0000', font_size='14px')

    def _on_key_press(self, key):
        if key == self.config.STOP_KEY:  # Direct comparison with Key enum
            self.recording = False
            self.listener.stop()

    def _monitor_stop_key(self):
        self.listener = keyboard.Listener(on_press=self._on_key_press)
        self.listener.start()

    def _check_duration(self) -> bool:
        if self.start_time is None:
            return True
        elapsed = time.time() - self.start_time
        if elapsed >= self.config.MAX_DURATION:
            logger.info(f"Maximum recording duration ({self.config.MAX_DURATION}s) reached")
            self.recording = False
            return False
        return True

    def record(self, filename: Path) -> None:
        self._setup_audio()
        self.recording = True
        self.start_time = time.time()
        self._send_notification('Recording Started', 'recording')

        self._monitor_stop_key()  # Start key listener

        while self.recording and self._check_duration():
            self.frames.append(self.stream.read(self.config.CHUNK))

        self._cleanup()
        self._save_to_file(filename)

    def _cleanup(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

    def _save_to_file(self, filename: Path):
        with wave.open(str(filename), 'wb') as wf:
            wf.setnchannels(self.config.CHANNELS)
            wf.setsampwidth(self.p.get_sample_size(self.config.LOW_QUALITY_FORMAT))
            wf.setframerate(self.config.LOW_QUALITY_RATE)
            wf.writeframes(b''.join(self.frames))


class TranscriptionHandler:
    def __init__(self):
        self.notifier = NotificationManager()

    def _send_notification(self, text: str):
        self.notifier.send_notification('Voice Transcription', text, font_size='28px')

    # Convert other static methods to instance methods
    def handle_transcription(self, audio_file: Path) -> tuple[str, Path]:
        transcription = transcribe_audio(audio_file)
        transcript_file = OUTPUT / f"transcripts/{audio_file.stem}.txt"
        transcript_file.parent.mkdir(exist_ok=True, parents=True)
        
        with open(transcript_file, 'w', encoding='utf-8') as f:
            f.write(transcription)
        
        pyperclip.copy(transcription)
        self._send_notification(transcription)
        
        return transcription, transcript_file


def main():
    parser = argparse.ArgumentParser(description='Voice Recording and Transcription Tool')
    parser.add_argument('--test1', action='store_true', help='Test the notification system')
    parser.add_argument('--test2', action='store_true', help='Test the OpenAI client')
    args = parser.parse_args()

    if args.test1:
        logger.info("Running notification test")
        notifier = NotificationManager()
        notifier.test_notification()
        return

    if args.test2:
        logger.info("Running OpenAI client test")
        handler = TranscriptionHandler()
        transcription = transcribe_audio(None, mode=ProcessingMode.TEST)
        logger.info(f"Test transcription result: {transcription}")
        handler._send_notification(transcription)
        return

    try:
        logger.debug("Starting voice recording")
        config = AudioConfig()
        audio_file = OUTPUT / f"records/{datetime.now().strftime('%Y-%m-%d_%H:%M:%S')}.{config.OUTPUT_FORMAT}"
        audio_file.parent.mkdir(exist_ok=True, parents=True)

        recorder = VoiceRecorder(config)
        recorder.record(audio_file)
        logger.debug(f"Recording saved to {audio_file}")

        handler = TranscriptionHandler()
        transcription, tr_file = handler.handle_transcription(audio_file)
        logger.debug(f"Transcription saved to {tr_file}")
        logger.info(f"Transcription: {transcription}")

    except KeyboardInterrupt:
        logger.info("Program terminated by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
