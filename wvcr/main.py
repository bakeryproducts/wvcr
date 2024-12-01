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
from wvcr.openai_client import transcribe, ProcessingMode, process_text
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

    def handle_transcription(self, audio_file: Path, mode: ProcessingMode = None) -> tuple[str, Path]:
        text = transcribe(audio_file)
        processed_text = process_text(text, mode)
        
        transcript_file = OUTPUT / f"transcripts/{audio_file.stem}.txt"
        transcript_file.parent.mkdir(exist_ok=True, parents=True)
        
        with open(transcript_file, 'w', encoding='utf-8') as f:
            f.write(processed_text)
        
        pyperclip.copy(processed_text)
        self._send_notification(processed_text)
        
        return processed_text, transcript_file


def parse_args():
    parser = argparse.ArgumentParser(description='Voice recording and transcription tool')
    parser.add_argument('mode', nargs='?', default='transcribe',
                       choices=['transcribe', 'correct', 'answer'],
                       help='Processing mode (default: transcribe)')
    return parser.parse_args()

def get_processing_mode(args) -> ProcessingMode:
    if not args.mode:
        return None
    
    mode_map = {
        'transcribe': ProcessingMode.TRANSCRIBE_ONLY,
        'correct': ProcessingMode.CORRECT,
        'answer': ProcessingMode.ANSWER
    }
    return mode_map[args.mode]

def main():
    try:
        args = parse_args()
        mode = get_processing_mode(args)
        
        logger.debug("Starting voice recording")
        config = AudioConfig()
        audio_file = OUTPUT / f"records/{datetime.now().strftime('%Y-%m-%d_%H:%M:%S')}.{config.OUTPUT_FORMAT}"
        audio_file.parent.mkdir(exist_ok=True, parents=True)

        recorder = VoiceRecorder(config)
        recorder.record(audio_file)
        logger.debug(f"Recording saved to {audio_file}")

        handler = TranscriptionHandler()
        transcription, tr_file = handler.handle_transcription(audio_file, mode)
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
