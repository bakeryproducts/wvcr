import threading

from pynput.keyboard import Key
from loguru import logger
from ..step import Step


class PlayTextToSpeech(Step):
    name = "play_tts"
    requires = {"text", "audio_file"}
    provides = {"voiceover_file"}

    def execute(self, state, ctx):
        text = state.get("text")
        output_file = state.get("audio_file")
        
        if not text:
            raise ValueError("No text provided for TTS")
        
        logger.info(f"Generating voiceover for text: {text[:50]}...")
        
        # Get TTS service from context
        tts_service = ctx.services.get("tts")
        if not tts_service:
            raise RuntimeError("TTS service not initialized in context")
        
        # Create stop flag for playback
        stop_playback = threading.Event()
        
        # Import and start key monitor for ESC key
        from wvcr.common import create_key_monitor
        
        def stop_callback():
            logger.info('ESC key pressed, stopping playback')
            stop_playback.set()
            if ctx.notifier:
                ctx.notifier.send_notification("Playback", "Stopped by user")
        
        # Start key monitor using context settings
        use_evdev = ctx.options.get("use_evdev", True)
        key_monitor = create_key_monitor(Key.esc, stop_callback, prefer_evdev=use_evdev)
        key_monitor.start()
        
        try:
            # Get provider from context options
            provider = ctx.options.get("provider", "openai")
            
            # Play audio in separate thread so we can monitor for stop key
            play_thread = threading.Thread(
                target=tts_service.generate_and_play,
                args=(text, output_file, provider, stop_playback)
            )
            play_thread.start()
            
            # Wait for playback to finish or stop key
            play_thread.join()
        finally:
            # Clean up key monitor
            key_monitor.stop()
        
        state.set("voiceover_file", output_file)
        logger.info(f"Voiceover saved to {output_file}")
