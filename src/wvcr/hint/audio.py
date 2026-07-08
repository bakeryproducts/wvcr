from __future__ import annotations

import select
import subprocess
import threading
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


def _loopback_source_arg(m: ModuleEntry) -> str | None:
    for tok in m.args.split():
        if tok.startswith("source="):
            return tok[len("source="):]
    return None


def _ensure_loopback(desired_source: str, tag: str) -> None:
    """Make sure exactly one loopback for `tag` exists, pointed at
    `desired_source`. Reloads it if it drifted to the wrong source (e.g. the
    default output device changed), removes duplicates."""
    matches = _find_loopback_modules(tag)
    correct = [m for m in matches if _loopback_source_arg(m) == desired_source]
    stale = [m for m in matches if _loopback_source_arg(m) != desired_source]
    for m in stale:
        try:
            _pactl("unload-module", str(m.module_id))
            logger.info(f"removed stale hint loopback {tag} (was {_loopback_source_arg(m)})")
        except subprocess.CalledProcessError as e:
            logger.warning(f"failed to unload stale loopback {m.module_id}: {e}")
    # drop extra correct duplicates, keep one
    for m in correct[1:]:
        try:
            _pactl("unload-module", str(m.module_id))
        except subprocess.CalledProcessError:
            pass
    if not correct:
        _create_loopback(desired_source, tag)


def _default_source() -> str:
    return _pactl("get-default-source").strip()


def _default_sink_monitor() -> str:
    return f"{_pactl('get-default-sink').strip()}.monitor"


def _remove_loopbacks() -> None:
    for tag in (MIC_TAG, SYS_TAG):
        for m in _find_loopback_modules(tag):
            try:
                _pactl("unload-module", str(m.module_id))
            except subprocess.CalledProcessError as e:
                logger.warning(f"failed to unload loopback {m.module_id}: {e}")


def _default_sink_monitor() -> str:
    sink = _pactl("get-default-sink").strip()
    return f"{sink}.monitor"


def reconcile() -> None:
    """Idempotently ensure the bus + both loopbacks exist and point at the
    *current* default devices. Safe to call repeatedly."""
    _create_sink()
    # mic + everything you hear -> one bus, mixed by PulseAudio.
    # @DEFAULT_MONITOR@/@DEFAULT_SOURCE@ are resolved once at load time (and
    # @DEFAULT_MONITOR@ is broken under PipeWire's pulse-compat, resolving to
    # the mic), so resolve explicit device names and reconcile on change.
    _ensure_loopback(_default_source(), MIC_TAG)
    _ensure_loopback(_default_sink_monitor(), SYS_TAG)


def setup() -> None:
    reconcile()


def watch_defaults(stop_event: threading.Event) -> None:
    """Follow default-device changes: re-point loopbacks whenever the default
    sink/source changes (e.g. plugging Bluetooth/HDMI). Returns when stopped.

    Uses select() so it wakes periodically to observe `stop_event` instead of
    blocking forever on subscribe output -- lets the caller join it *before*
    teardown, so a late event can't recreate the bus after teardown."""
    try:
        proc = subprocess.Popen(
            ["pactl", "subscribe"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        logger.warning("pactl not found; default-device following disabled")
        return
    try:
        assert proc.stdout is not None
        while not stop_event.is_set():
            ready, _, _ = select.select([proc.stdout], [], [], 0.3)
            if not ready:
                continue
            line = proc.stdout.readline()
            if not line:
                break
            # default sink/source changes surface as a 'server' change event
            if "on server" in line and not stop_event.is_set():
                try:
                    reconcile()
                except Exception as e:
                    logger.warning(f"hint reconcile failed: {e}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()


def teardown() -> None:
    _remove_loopbacks()
    m = _find_sink_module()
    if m is not None:
        _pactl("unload-module", str(m.module_id))
        logger.info(f"removed hint bus {BUS_NAME}")
