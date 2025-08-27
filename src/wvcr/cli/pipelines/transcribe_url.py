from omegaconf import DictConfig
from loguru import logger

from wvcr.modes2.transcribe_url_pipeline_mode import TranscribeUrlPipelineMode
from ..runtime import build_runtime_context


def run_transcribe_url(cfg: DictConfig):
    ctx = build_runtime_context(cfg)
    # Stash pipeline config so pipeline mode can access optional args
    ctx.pipeline_cfg = cfg  # type: ignore[attr-defined]
    mode = TranscribeUrlPipelineMode(ctx)
    state = mode.run()
    transcript = state.get("transcript")
    if transcript:
        logger.info(transcript)
        print(transcript)