from __future__ import annotations

import os
import select
import threading
from typing import Callable

from loguru import logger

try:
    import evdev
    from evdev import ecodes

    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False


def _keycode(name: str) -> int | None:
    attr = f"KEY_{name.strip('<>').upper()}"
    return getattr(ecodes, attr, None)


class EvdevHotkey:
    """Global hotkey via evdev (Wayland-friendly). Reads real keyboards directly."""

    def __init__(self, key_name: str, callback: Callable[[], None]):
        self.key_name = key_name
        self.callback = callback
        self.running = False
        self.thread: threading.Thread | None = None

    def _is_keyboard(self, device) -> bool:
        try:
            caps = device.capabilities().get(ecodes.EV_KEY, [])
            if len(caps) < 30:
                return False
            for k in (ecodes.KEY_A, ecodes.KEY_SPACE, ecodes.KEY_ENTER):
                if k not in caps:
                    return False
            return True
        except Exception:
            return False

    def _loop(self) -> None:
        target = _keycode(self.key_name)
        if target is None:
            logger.error(f"unknown key '{self.key_name}'")
            return
        try:
            devices = [evdev.InputDevice(p) for p in evdev.list_devices()]
        except Exception as e:
            logger.error(f"cannot open input devices (need input group?): {e}")
            return
        kbds = [d for d in devices if self._is_keyboard(d)]
        if not kbds:
            logger.error("no keyboard devices found for evdev")
            return
        for d in kbds:
            logger.info(f"listening on {d.name}")
        fdmap = {d.fd: d for d in kbds}
        self.running = True
        while self.running:
            r, _, _ = select.select(fdmap, [], [], 0.1)
            for fd in r:
                try:
                    for ev in fdmap[fd].read():
                        if ev.type == ecodes.EV_KEY and ev.value == 1:
                            if ev.code == target:
                                logger.info(f"hotkey {self.key_name} pressed")
                                self.callback()
                except OSError:
                    pass

    def start(self) -> None:
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)


class PynputHotkey:
    """Global hotkey via pynput (X11)."""

    def __init__(self, hotkey: str, callback: Callable[[], None]):
        from pynput import keyboard

        self._hk = keyboard.GlobalHotKeys({hotkey: callback})

    def start(self) -> None:
        self._hk.start()

    def stop(self) -> None:
        self._hk.stop()


def create_hotkey(hotkey: str, callback: Callable[[], None]):
    prefer_evdev = os.environ.get("WVCR_USE_EVDEV", "").lower() in ("1", "true", "yes")
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    if (prefer_evdev or wayland) and EVDEV_AVAILABLE:
        logger.info("using evdev hotkey")
        return EvdevHotkey(hotkey, callback)
    logger.info("using pynput hotkey")
    return PynputHotkey(hotkey, callback)
