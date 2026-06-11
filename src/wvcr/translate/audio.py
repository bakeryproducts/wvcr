from __future__ import annotations

import subprocess
from dataclasses import dataclass

from loguru import logger

SINK_NAME = "wvcr-virtmic"
SINK_DESCRIPTION = "WVCR Virtual Mic"
MIC_NAME = "wvcr-mic"
MIC_DESCRIPTION = "WVCR Mic"
LOOPBACK_TAG = "wvcr_loopback"
SAMPLE_RATE = 24000
CHANNELS = 1
SAMPLE_WIDTH = 2
FRAME_MS = 20
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000


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
        if m.name == "module-null-sink" and f"sink_name={SINK_NAME}" in m.args:
            return m
    return None


def _find_remap_source_module() -> ModuleEntry | None:
    for m in _list_modules():
        if m.name == "module-remap-source" and f"source_name={MIC_NAME}" in m.args:
            return m
    return None


def _find_loopback_modules() -> list[ModuleEntry]:
    found: list[ModuleEntry] = []
    for m in _list_modules():
        if m.name != "module-loopback":
            continue
        if f"sink={SINK_NAME}" in m.args and LOOPBACK_TAG in m.args:
            found.append(m)
    return found


def sink_exists() -> bool:
    return _find_sink_module() is not None


def remap_source_exists() -> bool:
    return _find_remap_source_module() is not None


def loopback_running() -> bool:
    return len(_find_loopback_modules()) > 0


def create_sink() -> None:
    if sink_exists():
        logger.info(f"sink {SINK_NAME} already exists")
        return
    _pactl(
        "load-module",
        "module-null-sink",
        f"sink_name={SINK_NAME}",
        f"sink_properties=device.description={SINK_DESCRIPTION}",
        "rate=24000",
        "channels=1",
    )
    logger.info(f"created sink {SINK_NAME}")


def remove_sink() -> None:
    stop_loopback()
    remove_remap_source()
    m = _find_sink_module()
    if m is None:
        return
    _pactl("unload-module", str(m.module_id))
    logger.info(f"removed sink {SINK_NAME}")


def create_remap_source() -> None:
    if remap_source_exists():
        logger.info(f"remap source {MIC_NAME} already exists")
        return
    _pactl(
        "load-module",
        "module-remap-source",
        f"source_name={MIC_NAME}",
        f"master={SINK_NAME}.monitor",
        "channels=1",
        "channel_map=mono",
        "master_channel_map=mono",
        f"source_properties=device.description={MIC_DESCRIPTION}",
    )
    logger.info(f"created remap source {MIC_NAME}")


def remove_remap_source() -> None:
    m = _find_remap_source_module()
    if m is None:
        return
    _pactl("unload-module", str(m.module_id))
    logger.info(f"removed remap source {MIC_NAME}")


def start_loopback() -> None:
    if loopback_running():
        return
    _pactl(
        "load-module",
        "module-loopback",
        "source=@DEFAULT_SOURCE@",
        f"sink={SINK_NAME}",
        "latency_msec=20",
        f"source_output_properties=media.name={LOOPBACK_TAG}",
        f"sink_input_properties=media.name={LOOPBACK_TAG}",
    )
    logger.info("started loopback real-mic -> virtmic")


def stop_loopback() -> None:
    for m in _find_loopback_modules():
        try:
            _pactl("unload-module", str(m.module_id))
        except subprocess.CalledProcessError as e:
            logger.warning(f"failed to unload loopback module {m.module_id}: {e}")
    if _find_loopback_modules():
        logger.warning("loopback modules still present after unload")
    else:
        logger.info("stopped loopback")


def setup() -> None:
    create_sink()
    create_remap_source()
    start_loopback()


def teardown() -> None:
    remove_sink()
