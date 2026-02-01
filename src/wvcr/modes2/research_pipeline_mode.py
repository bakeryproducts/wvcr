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
from wvcr.pipeline.steps.io_steps import (
    SaveResearchResult,
    CopyToClipboard,
)
from wvcr.pipeline.steps.run_research_agent_step import RunResearchAgentStep
from wvcr.pipeline.steps.notify import Notify, NotifyTranscription


class ResearchPipelineMode:
    def __init__(self, ctx: RuntimeContext):
        self.ctx = ctx

    def build_pipeline(self) -> Pipeline:
        # Access pipeline-specific config if available
        instruction = getattr( getattr(self.ctx, "pipeline_cfg", object()), "instruction", None)

        steps = [
            InitState("research"),
            PrepareOutputPath(records_dir=self.ctx.output_dir / "records"),
        ]

        if instruction:
            # Text input mode: use provided text instruction
            steps.append(SetKeyFromArg(key="transcript", value=instruction))
        else:
            # Audio input mode: record audio and send to ADK directly
            steps.extend(
                [
                    ConfigureRecording(defaults={"rate": 16000, "channels": 1}),
                    Notify(text="Start record"),
                    RecordAudio(),
                    Notify(text="Stop record"),
                    LoadAudioArtifact(),
                ]
            )

        # Run research (handles both text and audio)
        steps.append(RunResearchAgentStep())

        # Common completion steps
        steps.extend(
            [
                SaveResearchResult(output_dir=self.ctx.output_dir / "research"),
                CopyToClipboard(key="research_result"),
                NotifyTranscription(title="Research completed", key="research_result"),
                Finalize(),
            ]
        )

        return Pipeline(steps)

    def run(self):
        state = WorkingState()
        pipeline = self.build_pipeline()
        pipeline.run(state, self.ctx)
        return state
