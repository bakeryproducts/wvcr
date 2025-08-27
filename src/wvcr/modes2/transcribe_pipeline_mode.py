from pathlib import Path
from wvcr.pipeline import RuntimeContext, WorkingState, Pipeline
from wvcr.pipeline.steps.init_state import InitState
from wvcr.pipeline.steps.prepare_output_path import PrepareOutputPath
from wvcr.pipeline.steps.configure_recording import ConfigureRecording
from wvcr.pipeline.steps.record_audio import RecordAudio
from wvcr.pipeline.steps.transcribe_audio_step import TranscribeAudioStep
from wvcr.pipeline.steps.save_transcript import SaveTranscript
from wvcr.pipeline.steps.copy_to_clipboard import CopyToClipboard
from wvcr.pipeline.steps.notify import Notify, NotifyTranscription
from wvcr.pipeline.steps.finalize import Finalize

class TranscribePipelineMode:
    def __init__(self, ctx: RuntimeContext):
        self.ctx = ctx

    def build_pipeline(self) -> Pipeline:
        steps = [
            InitState("transcribe"),
            PrepareOutputPath(records_dir=self.ctx.output_dir / "records"),
            ConfigureRecording(defaults={"format": "wav", "rate": 16000, "channels": 1}),
            Notify(text="Start record"),
            RecordAudio(),
            Notify(text="Stop record"),
            TranscribeAudioStep(),
            SaveTranscript(output_dir=self.ctx.output_dir / 'transcribe'),
            CopyToClipboard(),
            NotifyTranscription(title="Transcription completed"),
            Finalize(),
        ]
        return Pipeline(steps)

    def run(self):
        state = WorkingState()
        pipeline = self.build_pipeline()
        pipeline.run(state, self.ctx)
        return state
