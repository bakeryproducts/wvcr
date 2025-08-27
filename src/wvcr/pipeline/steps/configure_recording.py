from ..step import Step

class ConfigureRecording(Step):
    name = "configure_recording"
    requires = {"audio_file"}
    provides = {"audio_params"}

    def __init__(self, defaults: dict):
        self.defaults = defaults

    def execute(self, state, ctx):
        # Merge defaults + ctx.options
        params = {**self.defaults}
        for k in ["rate", "channels", "max_duration", "format", "vad"]:
            if k in ctx.options:
                params[k] = ctx.options[k]
        state.set("audio_params", params)
