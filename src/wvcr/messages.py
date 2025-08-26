from io import BytesIO
from PIL import Image
from pathlib import Path
from typing import List, Dict
from loguru import logger
import base64


class Messages:
    def __init__(self, output_dir: Path = None):
        self.history = []
        self.output_dir = output_dir
        
    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})

    def add_image(self, image: Image.Image):
        self.history.append({"role": "user", "image": image})

    def get_messages(self) -> List[Dict[str, str]]:
        return self.history
    
    def clear_history(self):
        self.history = []
    
    def _print(self):
        for message in self.history:
            if "content" in message:
                logger.info(f"{message['role']}: {message['content']}")
            elif "image" in message:
                img = message["image"]
                logger.info(f"{message['role']}: <image {img.width}x{img.height}>")

    def to_oai(self) -> List[Dict]:
        """Convert internal history (with optional PIL Images) to OpenAI chat format."""
        converted = []
        for msg in self.history:
            if "image" in msg:
                img: Image.Image = msg["image"]
                buf = BytesIO()
                img.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                converted.append({
                    "role": msg["role"],
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64}"
                            }
                        }
                    ]
                })
            else:
                # plain text passthrough
                converted.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        return converted

    

def get_prev_files(output_dir: Path, filenames: List[Path]=None):
    if filenames is None:
        filenames = list(output_dir.glob("*.txt"))
    else:
        # load from stems from output_dir
        filenames = [output_dir / f.name for f in filenames]
    return filenames

        
def load_previous_responses(filenames, limit: int = 5) -> str:
    files = sorted(filenames, key=lambda x: x.stat().st_mtime, reverse=False)
    files = files[-limit:]

    content = []
    
    for file in files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content.append(f.read().strip())
        except Exception as e:
            logger.exception(f"Could not read file: {file}")
    
    return content