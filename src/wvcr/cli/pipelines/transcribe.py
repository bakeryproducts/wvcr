from omegaconf import DictConfig
from wvcr.modes2.transcribe_pipeline_mode import TranscribePipelineMode
from ..runtime import build_runtime_context

from loguru import logger


def run(cfg: DictConfig):
    ctx = build_runtime_context(cfg)
    mode = TranscribePipelineMode(ctx)
    state = mode.run()
    transcript = state.get("transcript")

    if transcript:
        logger.info(transcript)
        print(transcript)