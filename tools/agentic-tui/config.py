import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_project_root = Path(__file__).parent.parent.parent
load_dotenv(_project_root / ".env")


ADK_API_URL = os.getenv("ADK_API_URL")
ADK_APP_NAME = os.getenv("ADK_APP_NAME")
ADK_USER_ID = os.getenv("ADK_USER_ID")
