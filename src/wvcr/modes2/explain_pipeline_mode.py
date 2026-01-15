from wvcr.pipeline import RuntimeContext, WorkingState, Pipeline
from wvcr.pipeline.steps.lifecycle_steps import InitState, PrepareOutputPath, SetKeyFromArg, Finalize
from wvcr.pipeline.steps.configure_recording import ConfigureRecording
from wvcr.pipeline.steps.record_audio import RecordAudio
from wvcr.pipeline.steps.transcribe_audio_step import TranscribeAudioStep
from wvcr.pipeline.steps.io_steps import SaveTranscript, SaveExplanation, PasteFromClipboard, CopyToClipboard
from wvcr.pipeline.steps.explain_text_step import ExplainTextStep
from wvcr.pipeline.steps.notify import Notify, NotifyTranscription

class ExplainPipelineMode:
    def __init__(self, ctx: RuntimeContext):
        self.ctx = ctx

    def build_pipeline(self) -> Pipeline:
        # Access pipeline-specific config if available (Hydra composed config not directly stored in ctx)
        # For MVP we expect the caller to stash composed cfg on ctx under 'pipeline_cfg' optionally.
        instruction = getattr(getattr(self.ctx, 'pipeline_cfg', object()), 'instruction', None)
        thing = getattr(getattr(self.ctx, 'pipeline_cfg', object()), 'thing', None)

        steps = [InitState("explain"), PrepareOutputPath(records_dir=self.ctx.output_dir / "records")]

        if instruction:
            steps.append(SetKeyFromArg(key="transcript", value=instruction))
        else:
            steps.extend([
                ConfigureRecording(defaults={"format": "wav", "rate": 16000, "channels": 1}),
                Notify(text="Start record"),
                RecordAudio(),
                Notify(text="Stop record"),
                TranscribeAudioStep(),
                SaveTranscript(output_dir=self.ctx.output_dir / 'transcribe'),
            ])

        if thing:
            steps.append(SetKeyFromArg(key="thing", value=thing))
        else:
            steps.append(PasteFromClipboard(key="thing"))

        steps.extend([
            ExplainTextStep(),
            SaveExplanation(output_dir=self.ctx.output_dir / 'explain'),
            CopyToClipboard(key="explanation"),
            NotifyTranscription(title="Explanation completed", key="explanation"),
            Finalize(),
        ])

        return Pipeline(steps)

    def run(self):
        state = WorkingState()
        pipeline = self.build_pipeline()
        pipeline.run(state, self.ctx)
        return state
