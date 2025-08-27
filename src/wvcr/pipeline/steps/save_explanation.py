from pathlib import Path
from ..step import Step

class SaveExplanation(Step):
    name = "save_explanation"
    requires = {"explanation", "start_time", "mode"}
    provides = {"explanation_file"}

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def execute(self, state, ctx):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{state.get('mode')}_{state.get('start_time').strftime('%Y-%m-%d_%H:%M:%S')}.txt"
        out = self.output_dir / filename
        out.write_text(state.get("explanation"), encoding="utf-8")
        state.set("explanation_file", out)
