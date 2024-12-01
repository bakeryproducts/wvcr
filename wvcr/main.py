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
OUTPUT_TRANSCRIBE = OUTPUT / ProcessingMode.TRANSCRIBE.value.lower()
OUTPUT_TRANSCRIBE.mkdir(exist_ok=True)

logger.add(
    OUTPUT / 'logs' / "{time:YYYY_MM}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)

class TranscriptionHandler:
    def __init__(self):
        self.notifier = NotificationManager()

    def _send_notification(self, text: str):
        self.notifier.send_notification('Voice Transcription', text, font_size='28px')

    def _get_output_dir(self, mode: ProcessingMode) -> Path:
        dst = OUTPUT / mode.value.lower()
        dst.mkdir(exist_ok=True, parents=True)
        return dst

    def handle_transcription(self, audio_file: Path, mode: ProcessingMode) -> tuple[str, Path]:
        transcription = transcribe(audio_file)
        logger.debug(f"Transcription: {transcription}")
        transcript_file = OUTPUT_TRANSCRIBE / f"{audio_file.stem}.txt"
        with open(transcript_file, 'w', encoding='utf-8') as f:
            f.write(transcription)

        # this will check transcription for ketwords and process it accordingly
        processed_text, mode = process_text(transcription, mode)
        if mode != ProcessingMode.TRANSCRIBE:
            # keyword detected, some post-processing has been done
            output_dir = self._get_output_dir(mode)
            output_file = output_dir / f"{audio_file.stem}.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(processed_text)

        pyperclip.copy(processed_text)
        self._send_notification(processed_text)
        

def parse_args():
    parser = argparse.ArgumentParser(description='Voice recording and transcription tool')
    parser.add_argument('mode', nargs='?', default='transcribe',
                       choices=['transcribe', 'correct', 'answer', 'explain'],
                       help='Processing mode (default: transcribe)')
    return parser.parse_args()

def get_processing_mode(args) -> ProcessingMode:
    if not args.mode:
        return ProcessingMode.TRANSCRIBE
    
    mode_map = {
        'transcribe': ProcessingMode.TRANSCRIBE,
        'correct': ProcessingMode.CORRECT,
        'answer': ProcessingMode.ANSWER,
        'explain': ProcessingMode.EXPLAIN
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
        handler.handle_transcription(audio_file, mode)

    except KeyboardInterrupt:
        logger.info("Program terminated by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
