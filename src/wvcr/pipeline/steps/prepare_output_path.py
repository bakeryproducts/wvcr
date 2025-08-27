from pathlib import Path
from ..step import Step

class PrepareOutputPath(Step):
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
