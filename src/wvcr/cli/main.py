import time
start = time.monotonic()
import logging
# for some reason httpx logs into stdout
logging.getLogger("httpx").setLevel(logging.WARNING)

from typing import Callable

from loguru import logger
from hydra import main
from hydra.core.hydra_config import HydraConfig
from omegaconf import DictConfig

from . import config as cfg_mod
from .runtime import build_runtime_context
from wvcr.modes2.explain_pipeline_mode import ExplainPipelineMode
from wvcr.modes2.transcribe_pipeline_mode import TranscribePipelineMode
from wvcr.modes2.transcribe_url_pipeline_mode import TranscribeUrlPipelineMode
from wvcr.modes2.voiceover_pipeline_mode import VoiceoverPipelineMode
from wvcr.config import OUTPUT

logger.add(
    OUTPUT / 'logs' / "{time:YYYY_MM}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)
logger.debug(f"[wvcr] CLI modules loaded in {time.monotonic() - start:.3f} seconds")

# Register structured configs early (idempotent) so Hydra finds `config`.
cfg_mod.register()


def _run_pipeline(mode_class, cfg: DictConfig):
    """Generic pipeline runner."""
    ctx = build_runtime_context(cfg)
    ctx.pipeline_cfg = cfg  # type: ignore[attr-defined]
    mode = mode_class(ctx)
    state = mode.run()
    return state


def _run_transcribe(cfg: DictConfig):
    state = _run_pipeline(TranscribePipelineMode, cfg)
    if transcript := state.get("transcript"):
        logger.info(transcript)
        print(transcript)


def _run_transcribe_url(cfg: DictConfig):
    state = _run_pipeline(TranscribeUrlPipelineMode, cfg)
    if transcript := state.get("transcript"):
        logger.info(transcript)
        print(transcript)


def _run_explain(cfg: DictConfig):
    state = _run_pipeline(ExplainPipelineMode, cfg)
    if explanation := state.get("explanation"):
        logger.info(explanation)
        print(explanation)


def _run_answer(cfg: DictConfig):
    print("Pipeline 'answer' not implemented")


def _run_voiceover(cfg: DictConfig):
    state = _run_pipeline(VoiceoverPipelineMode, cfg)
    if voiceover_file := state.get("voiceover_file"):
        logger.info(f"Voiceover saved to {voiceover_file}")
        print(f"Voiceover saved to {voiceover_file}")


PIPELINE_HANDLERS: dict[str, Callable] = {
    "transcribe": _run_transcribe,
    "transcribe-url": _run_transcribe_url,
    "answer": _run_answer,
    "explain": _run_explain,
    "voiceover": _run_voiceover,
}


@main(version_base=None, config_name="config", config_path=None)
def cli(cfg):
    try:
        selected = HydraConfig.get().runtime.choices.get("pipeline", "transcribe")
    except Exception:
        selected = "transcribe"

    handler = PIPELINE_HANDLERS.get(selected)
    if handler is None:
        logger.debug(f"[wvcr] Unknown pipeline '{selected}'")
        return
    if cfg.pipeline is None:
        logger.debug("[wvcr] Error: pipeline config not composed (cfg.pipeline is None)")
        return
    handler(cfg.pipeline)