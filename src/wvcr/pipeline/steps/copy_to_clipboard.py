from ..step import Step
import pyperclip

class CopyToClipboard(Step):
    name = "clipboard"
    requires = {"transcript"}

    def enabled(self, ctx, state):
        return ctx.options.get("clipboard", True)

    def execute(self, state, ctx):
        pyperclip.copy(state.get("transcript"))
