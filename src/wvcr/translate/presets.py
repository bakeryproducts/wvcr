from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from loguru import logger

DEFAULT_PRESETS = [
    {"name": "Spanish", "language": "es"},
    {"name": "French", "language": "fr"},
    {"name": "German", "language": "de"},
    {"name": "Japanese", "language": "ja"},
    {"name": "Russian", "language": "ru"},
    {"name": "English", "language": "en"},
]


@dataclass
class Preset:
    name: str
    language: str
    backend: str = "openai"
    echo_target_language: bool = True


def config_path() -> Path:
    xdg = os.getenv("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(xdg) / "wvcr" / "translate.yaml"


def load_presets() -> list[Preset]:
    path = config_path()
    if not path.exists():
        logger.info(f"no preset file at {path}, using defaults")
        return [Preset(p["name"], p["language"]) for p in DEFAULT_PRESETS]
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    raw = data.get("presets") or []
    out: list[Preset] = []
    for item in raw:
        try:
            out.append(
                Preset(
                    name=item["name"],
                    language=item["language"],
                    backend=item.get("backend", "openai"),
                    echo_target_language=item.get("echo_target_language", True),
                )
            )
        except KeyError as e:
            logger.warning(f"skipping preset missing key {e}: {item}")
    if not out:
        logger.warning("preset file present but empty, using defaults")
        return [Preset(p["name"], p["language"]) for p in DEFAULT_PRESETS]
    return out


def write_default_config() -> Path:
    path = config_path()
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        yaml.safe_dump({"presets": DEFAULT_PRESETS}, f, sort_keys=False)
    logger.info(f"wrote default presets to {path}")
    return path
