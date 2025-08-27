from wvcr.pipeline import RuntimeContext, WorkingState, Pipeline
from wvcr.pipeline.steps.init_state import InitState
from wvcr.pipeline.steps.prepare_output_path import PrepareOutputPath
from wvcr.pipeline.steps.configure_recording import ConfigureRecording
from wvcr.pipeline.steps.record_audio import RecordAudio
from wvcr.pipeline.steps.transcribe_audio_step import TranscribeAudioStep
from wvcr.pipeline.steps.save_transcript import SaveTranscript
from wvcr.pipeline.steps.explain_text_step import ExplainTextStep
from wvcr.pipeline.steps.save_explanation import SaveExplanation
from wvcr.pipeline.steps.set_key_from_arg import SetKeyFromArg
from wvcr.pipeline.steps.paste_from_clipboard import PasteFromClipboard
from wvcr.pipeline.steps.copy_to_clipboard import CopyToClipboard
from wvcr.pipeline.steps.notify import Notify, NotifyTranscription
from wvcr.pipeline.steps.finalize import Finalize

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
            # Seed transcript directly
            steps.append(SetKeyFromArg(key="transcript", value=instruction))
        else:
            # Normal recording + transcription path
            steps.extend([
                ConfigureRecording(defaults={"format": "wav", "rate": 16000, "channels": 1}),
                Notify(text="Start record"),
                RecordAudio(),
                Notify(text="Stop record"),
                TranscribeAudioStep(),
                SaveTranscript(output_dir=self.ctx.output_dir / 'transcribe'),
            ])

        # Acquire thing (clipboard) only if not provided explicitly
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
