import logging
# for some reason httpx logs into stdout
logging.getLogger("httpx").setLevel(logging.WARNING)

from typing import Callable
from hydra import main
from omegaconf import DictConfig

from . import config as cfg_mod
from wvcr.cli.pipelines.transcribe import run as run_transcribe
from wvcr.cli.pipelines.placeholders import (
    run_transcribe_url,
    run_answer,
    run_explain,
    run_voiceover,
)

# Register structured configs early (idempotent) so Hydra finds `config`.
cfg_mod.register()

PIPELINE_HANDLERS: dict[str, Callable[[DictConfig], None]] = {
    "transcribe": run_transcribe,
    "transcribe_url": run_transcribe_url,
    "answer": run_answer,
    "explain": run_explain,
    "voiceover": run_voiceover,
}


@main(version_base=None, config_name="config", config_path=None)
def cli(cfg: DictConfig):  # noqa: D401
    selected = "transcribe"
    if "defaults" in cfg and isinstance(cfg.defaults, list):
        for item in cfg.defaults:
            if isinstance(item, dict) and "pipeline" in item:
                selected = item["pipeline"]
    handler = PIPELINE_HANDLERS.get(selected)
    if handler is None:
        print(f"[wvcr] Unknown pipeline '{selected}'")
        return
    if cfg.pipeline is None:
        print("[wvcr] Error: pipeline config not composed (cfg.pipeline is None)")
        return
    handler(cfg.pipeline)