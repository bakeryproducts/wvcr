import os
from pathlib import Path

import dotenv
from loguru import logger


def get_package_root() -> Path:
    return Path(__file__).parent.parent.parent.parent.absolute()


def find_and_load_dotenv() -> str | None:
    package_root = get_package_root()
    dotenv_path = package_root / '.env'
    
    if dotenv_path.exists():
        dotenv.load_dotenv(str(dotenv_path))
        return str(dotenv_path)
    
    logger.warning("No .env file found. Ensure OPENAI_API_KEY/GEMINI_API_KEY are set.")
    return None


def get_api_key(provider: str) -> str:
    key_map = {
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
    }
    env_var = key_map.get(provider.lower(), "")
    return os.getenv(env_var, "")


# Auto-load on import
find_and_load_dotenv()

# Path constants
PACKAGE_ROOT = get_package_root()
OUTPUT = PACKAGE_ROOT / "output"
OUTPUT.mkdir(exist_ok=True)
