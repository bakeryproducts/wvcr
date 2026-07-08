from __future__ import annotations

import os
import signal
import threading
import time

from loguru import logger

from wvcr.notification_manager import LayerShellNotificationManager as SystemNotificationManager

from .audio import setup, teardown, watch_defaults
from .buffer import RingBuffer
from .hotkey import create_hotkey
from .llm import MODE_META, get_hint
from .picker import pick

DEBUG_DUMP_AUDIO = os.environ.get("WVCR_HINT_DEBUG_AUDIO", "").lower() in ("1", "true", "yes")


class HintRunner:
    def __init__(
        self,
        api_key: str,
        hotkey: str = "bookmarks",
        window_seconds: float = 600.0,
        context: str | None = None,
    ):
        self.api_key = api_key
        self.hotkey = hotkey
        self.context = context
        self.buffer = RingBuffer(window_seconds=window_seconds)
        self._hotkeys = None
        self._busy = threading.Lock()
        self._stop = threading.Event()
        self._watcher: threading.Thread | None = None

    def _on_hotkey(self) -> None:
        # Never block the listener thread; drop the press if one is in flight.
        if not self._busy.acquire(blocking=False):
            logger.info("hint request already in flight, ignoring press")
            return
        threading.Thread(target=self._handle_request, daemon=True).start()

    def _handle_request(self) -> None:
        try:
            mode = pick(MODE_META)
            if mode is None:
                logger.info("hint mode selection cancelled")
                return
            mp3 = self.buffer.snapshot_mp3()
            if len(mp3) < 512:
                logger.info("buffer too small, skipping")
                return
            if DEBUG_DUMP_AUDIO:
                dump_path = f"/tmp/wvcr-hint-{mode}-{int(time.time())}.mp3"
                try:
                    with open(dump_path, "wb") as f:
                        f.write(mp3)
                    logger.info(f"debug dumped audio to {dump_path}")
                except OSError as e:
                    logger.warning(f"failed to dump debug audio: {e}")
            logger.info(f"sending {len(mp3)} bytes of mp3 audio to Gemini, mode={mode}")
            SystemNotificationManager.send_notification(
                title="Hint", text="thinking...", timeout=2, position="bottom", keyboard_interactive=True
            )
            text = get_hint(mode, mp3, self.api_key, context=self.context)
            if text:
                SystemNotificationManager.send_notification(
                    title="Hint", text=text, timeout=0, position="bottom", keyboard_interactive=True
                )
            else:
                SystemNotificationManager.send_notification(
                    title="Hint", text="(no answer)", timeout=3, position="bottom", keyboard_interactive=True
                )
        except Exception as e:
            logger.exception(e)
            SystemNotificationManager.send_notification(
                title="Hint error", text=str(e), timeout=4, color="#e74c3c", position="bottom", keyboard_interactive=True
            )
        finally:
            self._busy.release()

    def run(self) -> None:
        setup()
        self.buffer.start()
        self._watcher = threading.Thread(
            target=watch_defaults, args=(self._stop,), daemon=True
        )
        self._watcher.start()
        self._hotkeys = create_hotkey(self.hotkey, self._on_hotkey)
        self._hotkeys.start()
        logger.info(f"hint listening, press {self.hotkey}")
        SystemNotificationManager.send_notification(
            title="Hint ON", text=f"press {self.hotkey}", timeout=2, position="bottom", keyboard_interactive=True
        )

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: self._stop.set())

        try:
            self._stop.wait()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        if self._hotkeys is not None:
            self._hotkeys.stop()
        # stop the device watcher before teardown so a late event can't
        # recreate the bus after we remove it
        self._stop.set()
        if self._watcher is not None and self._watcher.is_alive():
            self._watcher.join(timeout=2)
        self.buffer.stop()
        teardown()
        SystemNotificationManager.send_notification(
            title="Hint OFF", text="stopped", timeout=2, position="bottom", keyboard_interactive=True
        )
        logger.info("hint stopped")


def run_hint(
    api_key: str,
    hotkey: str = "bookmarks",
    window_seconds: float = 600.0,
    context: str | None = None,
) -> None:
    HintRunner(api_key, hotkey=hotkey, window_seconds=window_seconds, context=context).run()
