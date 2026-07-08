from datetime import datetime

from ..step import Step
from wvcr.pipeline import RuntimeContext


class Notify(Step):
    name = "notify"

    def __init__(self, title=None, text=None):
        self.title = title if title else "WVCR"
        self.text = text if text else datetime.utcnow().strftime("at %Y-%m-%d %H:%M:%S")

    def enabled(self, ctx: RuntimeContext, state):
        return ctx.options.get("notify", True)

    def execute(self, state, ctx: RuntimeContext):
        ctx.notifier.send_notification(self.title, self.text)

class NotifyTranscription(Notify):
    def __init__(self, title: str = "WVCR", key: str = "transcript", cutoff: int = 2000):
        super().__init__(title=title)
        self.key = key
        self.cutoff = cutoff
        self.requires = {key}

    def execute(self, state, ctx: RuntimeContext):
        txt = state.get(self.key, "") or ""
        cutoff = self.cutoff
        if not isinstance(txt, str):
            txt = str(txt)
        snippet = txt[:cutoff] + ("..." if len(txt) > cutoff else "")
        ctx.notifier.send_notification(self.title, snippet, font_size="14px")
