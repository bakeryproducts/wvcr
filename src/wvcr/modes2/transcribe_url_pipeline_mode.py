from wvcr.pipeline import RuntimeContext, WorkingState, Pipeline
from wvcr.pipeline.steps.init_state import InitState
from wvcr.pipeline.steps.prepare_output_path import PrepareOutputPath
from wvcr.pipeline.steps.transcribe_audio_step import TranscribeAudioStep
from wvcr.pipeline.steps.save_transcript import SaveTranscript
from wvcr.pipeline.steps.set_key_from_arg import SetKeyFromArg
from wvcr.pipeline.steps.paste_from_clipboard import PasteFromClipboard
from wvcr.pipeline.steps.copy_to_clipboard import CopyToClipboard
from wvcr.pipeline.steps.notify import Notify, NotifyTranscription
from wvcr.pipeline.steps.finalize import Finalize
from wvcr.pipeline.steps.download_audio_step import DownloadAudioStep

class TranscribeUrlPipelineMode:
    def __init__(self, ctx: RuntimeContext):
        self.ctx = ctx

    def build_pipeline(self) -> Pipeline:
        # Access pipeline-specific config if available
        url = getattr(getattr(self.ctx, 'pipeline_cfg', object()), 'url', None)

        steps = [InitState("transcribe-url"), PrepareOutputPath(records_dir=self.ctx.output_dir / "records")]

        if url:
            steps.append(SetKeyFromArg(key="url", value=url))
        else:
            steps.append(PasteFromClipboard(key="url"))

        steps.extend([
            Notify(text="Downloading audio from URL..."),
            DownloadAudioStep(),
            Notify(text="Transcribing audio..."),
            TranscribeAudioStep(),
            SaveTranscript(output_dir=self.ctx.output_dir / 'transcribe'),
            CopyToClipboard(key="transcript"),
            NotifyTranscription(title="Transcription completed", key="transcript"),
            Finalize(),
        ])

        return Pipeline(steps)

    def run(self):
        state = WorkingState()
        pipeline = self.build_pipeline()
        pipeline.run(state, self.ctx)
        return state
