from __future__ import annotations

import subprocess
from dataclasses import dataclass

from loguru import logger

BUS_NAME = "wvcr-hintbus"
BUS_DESCRIPTION = "WVCR Hint Bus"
MIC_TAG = "wvcr_hint_mic"
SYS_TAG = "wvcr_hint_sys"
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2
FRAME_MS = 20
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
CAPTURE_DEVICE = f"{BUS_NAME}.monitor"


@dataclass
class ModuleEntry:
    module_id: int
    name: str
    args: str


def _pactl(*args: str) -> str:
    result = subprocess.run(
        ["pactl", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _list_modules() -> list[ModuleEntry]:
    out = _pactl("list", "short", "modules")
    entries: list[ModuleEntry] = []
    for line in out.splitlines():
        parts = line.split("\t", 2)
        if len(parts) < 2:
            continue
        try:
            mid = int(parts[0])
        except ValueError:
            continue
        name = parts[1]
        args = parts[2] if len(parts) > 2 else ""
        entries.append(ModuleEntry(mid, name, args))
    return entries


def _find_sink_module() -> ModuleEntry | None:
    for m in _list_modules():
        if m.name == "module-null-sink" and f"sink_name={BUS_NAME}" in m.args:
            return m
    return None


def _find_loopback_modules(tag: str) -> list[ModuleEntry]:
    found: list[ModuleEntry] = []
    for m in _list_modules():
        if m.name != "module-loopback":
            continue
        if f"sink={BUS_NAME}" in m.args and tag in m.args:
            found.append(m)
    return found


def sink_exists() -> bool:
    return _find_sink_module() is not None


def loopbacks_running() -> bool:
    return bool(_find_loopback_modules(MIC_TAG)) and bool(
        _find_loopback_modules(SYS_TAG)
    )


def _create_sink() -> None:
    if sink_exists():
        logger.info(f"hint bus {BUS_NAME} already exists")
        return
    _pactl(
        "load-module",
        "module-null-sink",
        f"sink_name={BUS_NAME}",
        f"sink_properties=device.description={BUS_DESCRIPTION}",
        f"rate={SAMPLE_RATE}",
        f"channels={CHANNELS}",
    )
    logger.info(f"created hint bus {BUS_NAME}")


def _create_loopback(source: str, tag: str) -> None:
    if _find_loopback_modules(tag):
        return
    _pactl(
        "load-module",
        "module-loopback",
        f"source={source}",
        f"sink={BUS_NAME}",
        "latency_msec=40",
        f"source_output_properties=media.name={tag}",
        f"sink_input_properties=media.name={tag}",
    )
    logger.info(f"started hint loopback {source} -> {BUS_NAME} ({tag})")


def _remove_loopbacks() -> None:
    for tag in (MIC_TAG, SYS_TAG):
        for m in _find_loopback_modules(tag):
            try:
                _pactl("unload-module", str(m.module_id))
            except subprocess.CalledProcessError as e:
                logger.warning(f"failed to unload loopback {m.module_id}: {e}")


def setup() -> None:
    _create_sink()
    # mic + everything you hear in headphones -> one bus, mixed by PulseAudio
    _create_loopback("@DEFAULT_SOURCE@", MIC_TAG)
    _create_loopback("@DEFAULT_MONITOR@", SYS_TAG)


def teardown() -> None:
    _remove_loopbacks()
    m = _find_sink_module()
    if m is not None:
        _pactl("unload-module", str(m.module_id))
        logger.info(f"removed hint bus {BUS_NAME}")
