from ..step import Step
import pyperclip


class CopyToClipboard(Step):
    name = "clipboard"

    def __init__(self, key: str = "transcript"):
        # dynamic requirement so step can be reused for explanation, answers, etc.
        self.key = key
        self.requires = {key}

    def enabled(self, ctx, state):
        return ctx.options.get("clipboard", True)

    def execute(self, state, ctx):
        value = state.get(self.key)
        if value:
            pyperclip.copy(value)
