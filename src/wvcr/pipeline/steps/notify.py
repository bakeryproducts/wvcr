from datetime import datetime

from ..step import Step


class Notify(Step):
    name = "notify"

    def __init__(self, title=None, text=None):
        self.title = title if title else "WVCR"
        self.text = text if text else datetime.utcnow().strftime("at %Y-%m-%d %H:%M:%S")

    def enabled(self, ctx, state):
        return ctx.options.get("notify", True)

    def execute(self, state, ctx):
        ctx.notifier.send_notification(self.title, self.text)

class NotifyTranscription(Notify):
    requires = {"transcript"}

    def execute(self, state, ctx):
        txt = state.get("transcript")
        cutoff = 100
        ctx.notifier.send_notification(self.title, txt[:cutoff] + ("..." if len(txt) > cutoff else ""))
