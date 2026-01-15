from pathlib import Path
from wvcr.pipeline import RuntimeContext, WorkingState, Pipeline
from wvcr.pipeline.steps.lifecycle_steps import InitState, PrepareOutputPath, Finalize
from wvcr.pipeline.steps.io_steps import PasteFromClipboard
from wvcr.pipeline.steps.notify import Notify
from wvcr.pipeline.step import Step
import pyaudio
from loguru import logger
from wvcr.voiceover import write_audio


class GenerateVoiceoverStep(Step):
    """Generate voiceover from clipboard text using OpenAI TTS."""
    name = "generate_voiceover"
    requires = {"text", "output_path"}
    provides = {"voiceover_file"}

    def execute(self, state, ctx):
        text = state.get("text")
        output_path = state.get("output_path")
        
        if not text:
            raise ValueError("No text in clipboard")
        
        logger.info(f"Generating voiceover for text: {text[:50]}...")
        
        # Get OpenAI config
        stt_cfg = ctx.get_stt_config()
        
        # Generate voiceover
        p = pyaudio.PyAudio()
        stream = p.open(format=8, channels=1, rate=24_000, output=True)
        
        try:
            success = write_audio(stream, text, stt_cfg, output_path, use_gpt_tts=True)
            if not success:
                raise RuntimeError("Failed to generate voiceover")
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
        
        state.set("voiceover_file", output_path)
        logger.info(f"Voiceover saved to {output_path}")


class VoiceoverPipelineMode:
    def __init__(self, ctx: RuntimeContext):
        self.ctx = ctx

    def build_pipeline(self) -> Pipeline:
        steps = [
            InitState("voiceover"),
            PrepareOutputPath(records_dir=self.ctx.output_dir / "voiceover"),
            PasteFromClipboard(key="text"),
            Notify(text="Generating voiceover..."),
            GenerateVoiceoverStep(),
            Notify(text="Voiceover saved"),
            Finalize(),
        ]
        return Pipeline(steps)

    def run(self):
        state = WorkingState()
        pipeline = self.build_pipeline()
        pipeline.run(state, self.ctx)
        return state
