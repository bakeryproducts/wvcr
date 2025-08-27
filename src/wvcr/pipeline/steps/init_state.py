from datetime import datetime
from ..step import Step

class InitState(Step):
    name = "init"
    provides = {"mode", "start_time"}

    def __init__(self, mode: str):
        self.mode = mode

    def execute(self, state, ctx):
        state.set("mode", self.mode)
        state.set("start_time", datetime.utcnow())
