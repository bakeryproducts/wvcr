import os
from dataclasses import dataclass, field

from .env import OUTPUT
from .providers import OAIConfig, GeminiConfig
from .audio import RecorderAudioConfig, PlayerAudioConfig


@dataclass
class WVCRConfig:
    # Provider & language
    provider: str = field(default_factory=lambda: os.getenv("WVCR_PROVIDER", "gemini"))
    language: str = "ru"

    # Feature flags
    clipboard: bool = True
    notify: bool = True
    notify_backend: str = field(
        default_factory=lambda: os.getenv("WVCR_NOTIFY_BACKEND", "system")
    )  # "hyprland" or "system"
    use_evdev: bool = field(
        default_factory=lambda: os.getenv("WVCR_USE_EVDEV", "true").lower() == "true"
    )

    # Output directory
    output_dir: str = field(default_factory=lambda: str(OUTPUT))

    # Nested configs
    oai: OAIConfig = field(default_factory=OAIConfig)
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    recorder: RecorderAudioConfig = field(default_factory=RecorderAudioConfig)
    player: PlayerAudioConfig = field(default_factory=PlayerAudioConfig)

    # Command-specific args
    url: str | None = None
    instruction: str | None = None
    thing: str | None = None


def get_default_config() -> WVCRConfig:
    return WVCRConfig()
