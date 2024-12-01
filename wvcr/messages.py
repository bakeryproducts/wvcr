from pathlib import Path
from typing import List, Dict
from loguru import logger


class Messages:
    def __init__(self, output_dir: Path = None):
        self.history = []
        self.output_dir = output_dir
        
    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        
    def get_messages(self) -> List[Dict[str, str]]:
        return self.history
    
    def clear_history(self):
        self.history = []
    
    def _print(self):
        for message in self.history:
            logger.info(f"{message['role']}: {message['content']}")

    

def get_prev_files(output_dir: Path, filenames: List[Path]=None):
    if filenames is None:
        filenames = list(output_dir.glob("*.txt"))
    else:
        # load from stems from output_dir
        filenames = [output_dir / f.name for f in filenames]
    logger.debug(f"Previous files: {filenames}")
    return filenames

        
def load_previous_responses(filenames, limit: int = 5) -> str:
    files = sorted(filenames, key=lambda x: x.stat().st_mtime, reverse=False)
    content = []
    
    for file in files[:limit]:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content.append(f.read().strip())
        except Exception as e:
            logger.exception(f"Could not read file: {file}")
    
    return content