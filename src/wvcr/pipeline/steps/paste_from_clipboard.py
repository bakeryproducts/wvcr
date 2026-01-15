from ..step import Step
import pyperclip
from loguru import logger


class PasteFromClipboard(Step):
    name = "paste"

    def __init__(self, key: str):
        self.key = key
        self.provides = {key}

    def execute(self, state, ctx):
        # Try text first
        try:
            clipboard_content = pyperclip.paste()
        except Exception as e:
            logger.debug(f"Clipboard text fetch failed: {e}")
            clipboard_content = ""

        if clipboard_content and clipboard_content.strip():
            state.set(self.key, clipboard_content.strip())
            return

        # Fallback to image
        try:
            from wvcr.services.clipboard import _paste_linux_wlpaste
            image = _paste_linux_wlpaste()
            if image:
                state.set(self.key, image)
                return
        except Exception as e:
            logger.debug(f"Clipboard image fetch failed: {e}")
        # Nothing found; leave key unset (pipeline will proceed with transcript only)