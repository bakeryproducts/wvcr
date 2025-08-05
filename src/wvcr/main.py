#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path

from wvcr.config import OUTPUT, OAIConfig
from wvcr.notification_manager import NotificationManager
from wvcr.modes import ProcessingMode, ModeFactory
from wvcr.recorder import VoiceRecorder
from wvcr.services import create_audio_file_path


from loguru import logger
logger.add(
    OUTPUT / 'logs' / "{time:YYYY_MM}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)


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
    config = OAIConfig(args.model)

    try:
        mode_handler = ModeFactory.create_mode(mode, config, notifier)
        
        if mode == ProcessingMode.VOICEOVER:
            result_text, output_file = mode_handler.process(use_evdev=args.evdev)
            if output_file:
                logger.info(f"Voiceover saved to {output_file}")
            return

        logger.debug("Starting voice recording")
        audio_file = create_audio_file_path("records", "mp3")

        recorder = VoiceRecorder(notifier, use_evdev=args.evdev)
        recorder.record(audio_file)
        logger.debug(f"Recording saved to {audio_file}")

        result_text, output_file = mode_handler.process(audio_file)
        logger.debug(f"Processing completed. Result saved to {output_file}")

    except KeyboardInterrupt:
        logger.info("Program terminated by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
