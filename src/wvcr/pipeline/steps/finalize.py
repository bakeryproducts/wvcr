import time
from ..step import Step

class Finalize(Step):
    name = "finalize"
    requires = {"start_time"}

    def execute(self, state, ctx):
        # Could compute elapsed or add summary info
        # Placeholder - compute elapsed and store
        start = state.get("start_time")
        if start:
            elapsed = time.time() - start.timestamp()
            state.set("elapsed_seconds", elapsed)
