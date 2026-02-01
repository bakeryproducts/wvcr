from pathlib import Path

import pyperclip
from loguru import logger

from ..step import Step


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
        # Nothing found; leave key unset


class CopyToClipboard(Step):
    name = "clipboard"

    def __init__(self, key: str = "transcript"):
        self.key = key
        self.requires = {key}

    def enabled(self, ctx, state):
        return ctx.options.get("clipboard", True)

    def execute(self, state, ctx):
        value = state.get(self.key)
        if value:
            pyperclip.copy(value)


class SaveTranscript(Step):
    name = "save_transcript"
    requires = {"transcript", "start_time", "mode"}
    provides = {"transcript_file"}

    def __init__(self, output_dir):
        self.output_dir = output_dir

    def execute(self, state, ctx):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{state.get('mode')}_{state.get('start_time').strftime('%Y-%m-%d_%H:%M:%S')}.txt"
        out = self.output_dir / filename
        out.write_text(state.get("transcript"), encoding="utf-8")
        state.set("transcript_file", out)


class SaveExplanation(Step):
    name = "save_explanation"
    requires = {"explanation", "start_time", "mode"}
    provides = {"explanation_file"}

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def execute(self, state, ctx):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{state.get('mode')}_{state.get('start_time').strftime('%Y-%m-%d_%H:%M:%S')}.txt"
        out = self.output_dir / filename
        out.write_text(state.get("explanation"), encoding="utf-8")
        state.set("explanation_file", out)


class SaveResearchResult(Step):
    name = "save_research_result"
    requires = {"research_result", "start_time", "mode"}
    provides = {"research_result_file"}

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def execute(self, state, ctx):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{state.get('mode')}_{state.get('start_time').strftime('%Y-%m-%d_%H:%M:%S')}.txt"
        out = self.output_dir / filename
        out.write_text(state.get("research_result"), encoding="utf-8")
        state.set("research_result_file", out)
