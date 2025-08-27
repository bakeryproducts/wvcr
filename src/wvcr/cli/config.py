from dataclasses import dataclass, field
from typing import Any

from omegaconf import MISSING
from hydra.core.config_store import ConfigStore

from wvcr.config import (
    OUTPUT,
    OAIConfig,
    GeminiConfig,
    RecorderAudioConfig,
    PlayerAudioConfig,
)


@dataclass
class ContextConfig:
    provider: str = "gemini"  # openai|gemini (selects STT config)
    language: str = "ru"
    clipboard: bool = True
    notify: bool = True
    use_evdev: bool = True
    output_dir: str = str(OUTPUT)
    # Nested override-able configs
    oai: OAIConfig = field(default_factory=OAIConfig)
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    recorder: RecorderAudioConfig = field(default_factory=RecorderAudioConfig)
    player: PlayerAudioConfig = field(default_factory=PlayerAudioConfig)


@dataclass
class TranscribeConfig:
    context: ContextConfig = field(default_factory=ContextConfig)


@dataclass
class TranscribeUrlConfig:
    context: ContextConfig = field(default_factory=ContextConfig)
    url: str | None = None  # optional URL override


@dataclass
class AnswerConfig:
    context: ContextConfig = field(default_factory=ContextConfig)


@dataclass
class ExplainConfig:
    context: ContextConfig = field(default_factory=ContextConfig)
    instruction: str | None = None  # optional recorded transcript override
    thing: str | None = None        # optional clipboard override (text or path)


@dataclass
class VoiceoverConfig:
    context: ContextConfig = field(default_factory=ContextConfig)


@dataclass
class RootConfig:
    """Root config holding selected pipeline.

    Defaults now live in `config.yaml` to avoid Hydra's deprecated automatic
    schema matching (config file name == schema name) + defaults list combo.
    """
    pipeline: Any = MISSING  # populated from defaults list in config.yaml


def register():  # idempotent registration
    cs = ConfigStore.instance()
    cs.store(group="pipeline", name="transcribe", node=TranscribeConfig)
    cs.store(group="pipeline", name="transcribe-url", node=TranscribeUrlConfig)
    cs.store(group="pipeline", name="answer", node=AnswerConfig)
    cs.store(group="pipeline", name="explain", node=ExplainConfig)
    cs.store(group="pipeline", name="voiceover", node=VoiceoverConfig)
    # Register root schema under a distinct group to opt-out of deprecated
    # automatic schema matching (schema name == config file name).
    cs.store(group="schema", name="root", node=RootConfig)