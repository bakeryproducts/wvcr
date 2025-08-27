import logging
# for some reason httpx logs into stdout
logging.getLogger("httpx").setLevel(logging.WARNING)

from typing import Callable

from loguru import logger
from hydra import main
from hydra.core.hydra_config import HydraConfig
from omegaconf import DictConfig

from . import config as cfg_mod
from wvcr.cli.pipelines.explain import run as run_explain
from wvcr.cli.pipelines.transcribe import run as run_transcribe
from wvcr.cli.pipelines.transcribe_url import run_transcribe_url
from wvcr.cli.pipelines.placeholders import (
    run_answer,
    run_voiceover,
)

# Register structured configs early (idempotent) so Hydra finds `config`.
cfg_mod.register()

PIPELINE_HANDLERS: dict[str, Callable[[DictConfig], None]] = {
    "transcribe": run_transcribe,
    "transcribe-url": run_transcribe_url,
    "answer": run_answer,
    "explain": run_explain,
    "voiceover": run_voiceover,
}


@main(version_base=None, config_name="config", config_path=None)
def cli(cfg: DictConfig):  # noqa: D401
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