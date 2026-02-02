from wvcr.pipeline import RuntimeContext, WorkingState, Pipeline
from wvcr.pipeline.steps.lifecycle_steps import (
    InitState,
    PrepareOutputPath,
    SetKeyFromArg,
    Finalize,
)
from wvcr.pipeline.steps.configure_recording import ConfigureRecording
from wvcr.pipeline.steps.record_audio import RecordAudio
from wvcr.pipeline.steps.load_audio_artifact import LoadAudioArtifact
from wvcr.pipeline.steps.load_file_artifacts import LoadFileArtifacts
from wvcr.pipeline.steps.io_steps import (
    SaveAgenticResult,
    CopyToClipboard,
)
from wvcr.pipeline.steps.run_agentic_step import RunAgenticStep
from wvcr.pipeline.steps.notify import Notify, NotifyTranscription


class AgenticPipelineMode:
    def __init__(self, ctx: RuntimeContext):
        self.ctx = ctx

    def build_pipeline(self) -> Pipeline:
        instruction = self.ctx.options.get("instruction")
        session_id = self.ctx.options.get("session_id")
        app_name = self.ctx.options.get("app_name")
        files = self.ctx.options.get("files")

        steps = [
            InitState("agentic"),
            PrepareOutputPath(records_dir=self.ctx.output_dir / "records"),
        ]

        # Set session_id in state if provided
        if session_id:
            steps.append(SetKeyFromArg(key="session_id", value=session_id))

        # Set app_name in state if provided (otherwise step uses env default)
        if app_name:
            steps.append(SetKeyFromArg(key="app_name", value=app_name))

        # Set files in state if provided
        if files:
            steps.append(SetKeyFromArg(key="files", value=files))

        # Optional text instruction (additional context)
        if instruction:
            steps.append(SetKeyFromArg(key="instruction", value=instruction))

        # Audio input: always record and pass raw audio
        steps.extend(
            [
                ConfigureRecording(defaults={"rate": 16000, "channels": 1}),
                Notify(text="Start record"),
                RecordAudio(),
                Notify(text="Stop record"),
                LoadAudioArtifact(),
            ]
        )

        # Load file artifacts
        steps.append(LoadFileArtifacts())

        # Run agentic
        steps.append(RunAgenticStep())

        # Output
        steps.extend(
            [
                SaveAgenticResult(output_dir=self.ctx.output_dir / "agentic"),
                CopyToClipboard(key="agentic_result"),
                NotifyTranscription(title="Agentic completed", key="agentic_result"),
                Finalize(),
            ]
        )

        return Pipeline(steps)

    def run(self):
        state = WorkingState()
        pipeline = self.build_pipeline()
        pipeline.run(state, self.ctx)
        return state
