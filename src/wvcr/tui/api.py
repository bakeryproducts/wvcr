import os
from typing import Optional

import httpx

import wvcr.config  # ensure .env is loaded


async def list_apps() -> list[str]:
    url = os.getenv("ADK_API_URL")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{url}/list-apps", timeout=5.0)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return []


async def list_sessions(app_name: str, user_id: Optional[str] = None) -> list[dict]:
    url = os.getenv("ADK_API_URL")
    user = user_id or os.getenv("ADK_USER_ID")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{url}/apps/{app_name}/users/{user}/sessions",
                timeout=5.0,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return []
