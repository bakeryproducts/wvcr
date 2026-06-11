from __future__ import annotations

import subprocess

from loguru import logger

from .presets import Preset


def pick_preset(presets: list[Preset]) -> Preset | None:
    if not presets:
        return None
    lines = "\n".join(p.name for p in presets)
    try:
        result = subprocess.run(
            ["wofi", "--dmenu", "--prompt", "Translate to", "--lines", str(min(len(presets) + 1, 12))],
            input=lines,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        logger.error("wofi not installed")
        return None
    if result.returncode != 0:
        return None
    choice = result.stdout.strip()
    if not choice:
        return None
    for p in presets:
        if p.name == choice:
            return p
    logger.warning(f"wofi returned unknown name: {choice!r}")
    return None
