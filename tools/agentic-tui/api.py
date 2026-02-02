from typing import Optional

import httpx

from config import ADK_API_URL, ADK_USER_ID


async def list_apps() -> list[str]:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{ADK_API_URL}/list-apps", timeout=5.0)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return []


async def list_sessions(app_name: str, user_id: Optional[str] = None) -> list[dict]:
    user = user_id or ADK_USER_ID
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{ADK_API_URL}/apps/{app_name}/users/{user}/sessions",
                timeout=5.0,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return []
