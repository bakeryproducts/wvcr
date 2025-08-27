from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from wvcr.config import OAIConfig, GeminiConfig
from wvcr.notification_manager import NotificationManager

@dataclass
class RuntimeContext:
    """Holds shared services/config for steps."""
    oai_config: OAIConfig
    gemini_config: GeminiConfig | None
    notifier: NotificationManager
    output_dir: Path
    options: Dict[str, Any]  # CLI overrides (model, language, flags)
    services: Dict[str, Any]  # recorder, transcription, etc.

    def get_stt_config(self):
        # Decide which config to use (could use options['provider'])
        provider = self.options.get("provider", "openai")
        if provider == "gemini" and self.gemini_config:
            return self.gemini_config
        return self.oai_config
