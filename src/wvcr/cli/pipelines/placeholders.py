from omegaconf import DictConfig


def _placeholder(name: str):
    print(f"Pipeline '{name}' not implemented")




def run_answer(cfg: DictConfig):
    _placeholder("answer")


def run_explain(cfg: DictConfig):
    _placeholder("explain")


def run_voiceover(cfg: DictConfig):
    _placeholder("voiceover")