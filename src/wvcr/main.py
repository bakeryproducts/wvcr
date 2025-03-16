#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path
from datetime import datetime

import pyperclip

from wvcr.config import OUTPUT, OAIConfig
from wvcr.notification_manager import NotificationManager
from wvcr.openai_client import transcribe, ProcessingMode, process_text, MODE_DIRS
from wvcr.recorder import VoiceRecorder
from wvcr.voiceover import voiceover_clipboard


from loguru import logger
logger.add(
    OUTPUT / 'logs' / "{time:YYYY_MM}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)


class TranscriptionHandler:
    def __init__(self, model, notifier):
        self.notifier = notifier
        self.oai_config = OAIConfig(model)

    def _send_notification(self, text: str, cutoff=None):
        self.notifier.send_notification('Voice Transcription', text, font_size='28px', cutoff=cutoff)

    def _get_output_dir(self, mode: ProcessingMode) -> Path:
        dst = OUTPUT / mode.value.lower()
        dst.mkdir(exist_ok=True, parents=True)
        return dst

    def handle_transcription(self, audio_file: Path, mode: ProcessingMode) -> tuple[str, Path]:
        transcription = transcribe(audio_file, self.oai_config)
        logger.debug(f"Transcription: {transcription}")
        transcript_file = MODE_DIRS[ProcessingMode.TRANSCRIBE] / f"{audio_file.stem}.txt"
        with open(transcript_file, 'w', encoding='utf-8') as f:
            f.write(transcription)

        # Process with mode directory for context
        mode_dir = MODE_DIRS[mode]
        processed_text, mode = process_text(transcription, mode, config=self.oai_config)
        
        if mode != ProcessingMode.TRANSCRIBE:
            output_file = mode_dir / f"{audio_file.stem}.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(processed_text)

        pyperclip.copy(processed_text)
        cutoff = 100 if mode == ProcessingMode.TRANSCRIBE else None
        self._send_notification(processed_text, cutoff=cutoff)
        


def parse_args():
    parser = argparse.ArgumentParser(description='Voice recording and transcription tool')
    parser.add_argument('mode', nargs='?', default='transcribe',
                       choices=['transcribe', 'answer', 'explain', 'voiceover'],
                       help='Processing mode (default: transcribe)')
    parser.add_argument('--model', default=None,
                       help='GPT model to use (uses default from config if not specified)')
    parser.add_argument('--evdev', action='store_true', 
                       help='Use evdev for keyboard monitoring (for Wayland systems)')
    return parser.parse_args()

def get_processing_mode(args) -> ProcessingMode:
    if not args.mode:
        return ProcessingMode.TRANSCRIBE
    
    mode_map = {
        'transcribe': ProcessingMode.TRANSCRIBE,
        'answer': ProcessingMode.ANSWER,
        'explain': ProcessingMode.EXPLAIN,
        'voiceover': ProcessingMode.VOICEOVER
    }
    return mode_map[args.mode]

def main():
    args = parse_args()
    mode = get_processing_mode(args)
    notifier = NotificationManager()

    try:
        if mode == ProcessingMode.VOICEOVER:
            audio_file = OUTPUT / f"voiceover/{datetime.now().strftime('%Y-%m-%d_%H:%M:%S')}.wav"
            audio_file.parent.mkdir(exist_ok=True, parents=True)
            notifier.send_notification('Voiceover started', 'Voiceover started, press escape to stop')
            if voiceover_clipboard(audio_file, OAIConfig(), notifier=notifier, play=True, use_evdev=args.evdev):
                logger.info(f"Voiceover saved to {audio_file}")
            return


        logger.debug("Starting voice recording")
        audio_file = OUTPUT / f"records/{datetime.now().strftime('%Y-%m-%d_%H:%M:%S')}.mp3"
        audio_file.parent.mkdir(exist_ok=True, parents=True)

        recorder = VoiceRecorder(notifier, use_evdev=args.evdev)
        recorder.record(audio_file)
        logger.debug(f"Recording saved to {audio_file}")

        handler = TranscriptionHandler(args.model, notifier)
        handler.handle_transcription(audio_file, mode)


    except KeyboardInterrupt:
        logger.info("Program terminated by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
