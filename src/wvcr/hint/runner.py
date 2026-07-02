from __future__ import annotations

import signal
import threading

from loguru import logger

from wvcr.notification_manager import LayerShellNotificationManager as SystemNotificationManager

from .audio import setup, teardown
from .buffer import RingBuffer
from .hotkey import create_hotkey
from .llm import get_hint


class HintRunner:
    def __init__(self, api_key: str, hotkey: str = "bookmarks", window_seconds: float = 600.0):
        self.api_key = api_key
        self.hotkey = hotkey
        self.buffer = RingBuffer(window_seconds=window_seconds)
        self._hotkeys = None
        self._busy = threading.Lock()
        self._stop = threading.Event()

    def _on_hotkey(self) -> None:
        # Never block the listener thread; drop the press if one is in flight.
        if not self._busy.acquire(blocking=False):
            logger.info("hint request already in flight, ignoring press")
            return
        threading.Thread(target=self._handle_request, daemon=True).start()

    def _handle_request(self) -> None:
        try:
            mp3 = self.buffer.snapshot_mp3()
            if len(mp3) < 512:
                logger.info("buffer too small, skipping")
                return
            logger.info(f"sending {len(mp3)} bytes of mp3 audio to Gemini")
            SystemNotificationManager.send_notification(
                title="Hint", text="thinking...", timeout=2, position="bottom"
            )
            text = get_hint(mp3, self.api_key)
            if text:
                SystemNotificationManager.send_notification(
                    title="Hint", text=text, timeout=0, position="bottom"
                )
            else:
                SystemNotificationManager.send_notification(
                    title="Hint", text="(no answer)", timeout=3, position="bottom"
                )
        except Exception as e:
            logger.exception(e)
            SystemNotificationManager.send_notification(
                title="Hint error", text=str(e), timeout=4, color="#e74c3c", position="bottom"
            )
        finally:
            self._busy.release()

    def run(self) -> None:
        setup()
        self.buffer.start()
        self._hotkeys = create_hotkey(self.hotkey, self._on_hotkey)
        self._hotkeys.start()
        logger.info(f"hint listening, press {self.hotkey}")
        SystemNotificationManager.send_notification(
            title="Hint ON", text=f"press {self.hotkey}", timeout=2, position="bottom"
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
        self.buffer.stop()
        teardown()
        SystemNotificationManager.send_notification(
            title="Hint OFF", text="stopped", timeout=2, position="bottom"
        )
        logger.info("hint stopped")


def run_hint(api_key: str, hotkey: str = "bookmarks", window_seconds: float = 600.0) -> None:
    HintRunner(api_key, hotkey=hotkey, window_seconds=window_seconds).run()
