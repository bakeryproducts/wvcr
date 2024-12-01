#!/usr/bin/env python3

import sys
import argparse 
from pathlib import Path
import importlib.resources
from datetime import datetime

import pyperclip
from loguru import logger

from wvcr.config import AudioConfig
from wvcr.notification_manager import NotificationManager
from wvcr.openai_client import transcribe_audio, ProcessingMode
from wvcr.recorder import VoiceRecorder

PACKAGE_ROOT = Path(importlib.resources.files("wvcr"))
OUTPUT = PACKAGE_ROOT.parent / "output"
OUTPUT.mkdir(exist_ok=True)

logger.add(
    OUTPUT / 'logs' / "{time:YYYY_MM}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)

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
