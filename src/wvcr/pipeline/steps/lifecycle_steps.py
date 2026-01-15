"""Lifecycle steps: initialization, finalization, and output path preparation."""

from datetime import datetime
from pathlib import Path
import time
from ..step import Step


class InitState(Step):
    """Initialize pipeline state with mode and start time."""
    name = "init"
    provides = {"mode", "start_time"}

    def __init__(self, mode: str):
        self.mode = mode

    def execute(self, state, ctx):
        state.set("mode", self.mode)
        state.set("start_time", datetime.utcnow())


class PrepareOutputPath(Step):
    """Prepare timestamped output file path for audio recording."""
    name = "prepare_output"
    requires = {"mode"}
    provides = {"audio_file"}

    def __init__(self, records_dir, extension="wav"):
        self.records_dir = records_dir
        self.extension = extension

    def execute(self, state, ctx):
        self.records_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{state.get('mode')}_{state.get('start_time').strftime('%Y-%m-%d_%H:%M:%S')}.{self.extension}"
        path = self.records_dir / filename
        state.set("audio_file", path)


class Finalize(Step):
    """Compute and store elapsed time."""
    name = "finalize"
    requires = {"start_time"}

    def execute(self, state, ctx):
        start = state.get("start_time")
        if start:
            elapsed = time.time() - start.timestamp()
            state.set("elapsed_seconds", elapsed)


class SetKeyFromArg(Step):
    """Generic step to seed a value into state under a given key."""
    name = "set_key_from_arg"

    def __init__(self, key: str, value):
        self.key = key
        self.value = value
        self.provides = {key}

    def execute(self, state, ctx):
        state.set(self.key, self.value)
