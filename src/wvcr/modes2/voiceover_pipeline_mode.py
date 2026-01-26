from pathlib import Path
from wvcr.pipeline import RuntimeContext, WorkingState, Pipeline
from wvcr.pipeline.steps.lifecycle_steps import InitState, PrepareOutputPath, Finalize
from wvcr.pipeline.steps.io_steps import PasteFromClipboard
from wvcr.pipeline.steps.notify import Notify
from wvcr.pipeline.steps.play_tts import PlayTextToSpeech
from wvcr.pipeline.step import Step


class SetVoiceoverFormat(Step):
    """Override format to wav for voiceover output."""
    name = "set_voiceover_format"
    provides = set()
    
    def execute(self, state, ctx):
        ctx.options["format"] = "wav"


class VoiceoverPipelineMode:
    def __init__(self, ctx: RuntimeContext):
        self.ctx = ctx

    def build_pipeline(self) -> Pipeline:
        steps = [
            InitState("voiceover"),
            SetVoiceoverFormat(),
            PrepareOutputPath(records_dir=self.ctx.output_dir / "voiceover"),
            PasteFromClipboard(key="text"),
            Notify(text="Generating voiceover..."),
            PlayTextToSpeech(),
            Notify(text="Voiceover saved"),
            Finalize(),
        ]
        return Pipeline(steps)

    def run(self):
        state = WorkingState()
        pipeline = self.build_pipeline()
        pipeline.run(state, self.ctx)
        return state
