from ..step import Step


class SetKeyFromArg(Step):
    """Generic step to seed a value into state under a given key.

    Replaces specialized SetTranscriptFromArg, etc.
    """
    name = "set_key_from_arg"

    def __init__(self, key: str, value):
        self.key = key
        self.value = value
        self.provides = {key}

    def execute(self, state, ctx):
        state.set(self.key, self.value)
