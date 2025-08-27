from omegaconf import DictConfig
from wvcr.modes2.explain_pipeline_mode import ExplainPipelineMode
from ..runtime import build_runtime_context
from loguru import logger


def run(cfg: DictConfig):
    ctx = build_runtime_context(cfg)
    # Stash pipeline config so pipeline mode can access optional args
    ctx.pipeline_cfg = cfg  # type: ignore[attr-defined]
    mode = ExplainPipelineMode(ctx)
    state = mode.run()
    explanation = state.get("explanation")
    if explanation:
        logger.info(explanation)
        print(explanation)
