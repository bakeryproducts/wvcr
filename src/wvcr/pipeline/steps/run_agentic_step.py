import os
import base64
from datetime import datetime

import httpx
from loguru import logger

from ..step import Step, StepError


def get_adk_config() -> dict:
    return {
        "url": os.getenv("ADK_API_URL"),
        "app_name": os.getenv("ADK_APP_NAME"),
        "user_id": os.getenv("ADK_USER_ID"),
    }


class RunAgenticStep(Step):
    name = "run_agentic"
    provides = {"agentic_result"}

    def execute(self, state, ctx):
        cfg = get_adk_config()
        default_session = str(datetime.now().strftime("%Y-%m-%d"))
        logger.debug(f"Using session_id: {state.get('session_id')} or default: {default_session}")
        session_id = state.get("session_id") or default_session
        app_name = state.get("app_name") or cfg["app_name"]

        try:
            with httpx.Client(timeout=120.0) as client:
                self._ensure_session(client, cfg, app_name, session_id)

                parts = self._build_parts(state)
                if not parts:
                    raise StepError("RunAgenticStep requires 'audio_part', 'instruction', or 'file_parts' in state")

                payload = {
                    "appName": app_name,
                    "userId": cfg["user_id"],
                    "sessionId": session_id,
                    "newMessage": {
                        "role": "user",
                        "parts": parts,
                    },
                }

                url = f"{cfg['url']}/run"
                logger.info(f"Calling ADK API: {url} payload {payload}")

                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            raise StepError(f"ADK API error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            raise StepError(f"ADK API request failed: {e}")

        result = self._extract_result(data)
        state.set("agentic_result", result)
        logger.info(f"Agentic completed, result length: {len(result)} chars")

    def _ensure_session(self, client: httpx.Client, cfg: dict, app_name: str, session_id: str):
        url = ( f"{cfg['url']}/apps/{app_name}/users/{cfg['user_id']}/sessions/{session_id}")

        try:
            resp = client.post(url, json={})
            if resp.status_code == 200:
                logger.info(f"Created new session: {session_id}")
            elif resp.status_code == 409:  # Conflict = already exists
                logger.debug(f"Session already exists: {session_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 409:
                logger.warning(f"Session creation returned {e.response.status_code}, continuing anyway")


    def _build_parts(self, state) -> list:
        parts = []

        # Audio part (from LoadAudioArtifact - types.Part object)
        audio_part = state.get("audio_part")
        if audio_part:
            parts.append(
                {
                    "inlineData": {
                        "mimeType": audio_part.inline_data.mime_type,
                        "data": base64.b64encode(audio_part.inline_data.data).decode(
                            "utf-8"
                        ),
                    }
                }
            )

        # Optional text instruction (additional context)
        instruction = state.get("instruction")
        if instruction:
            parts.append({"text": instruction})

        # File parts (already processed by LoadFileArtifacts)
        file_parts = state.get("file_parts", [])
        parts.extend(file_parts)

        return parts

    def _extract_result(self, data) -> str:
        # ADK API returns list of events, collect all text from model responses
        if isinstance(data, list):
            texts = []
            for event in data:
                if text := self._extract_text_from_event(event):
                    texts.append(text)
            if texts:
                return "\n".join(texts)
        elif isinstance(data, dict):
            if "content" in data:
                return self._extract_text_from_content(data["content"])
            if "result" in data:
                return str(data["result"])
            if "text" in data:
                return data["text"]
        return str(data)

    def _extract_text_from_event(self, event: dict) -> str | None:
        # Check for content.parts structure (model response)
        content = event.get("content")
        if content and isinstance(content, dict):
            if parts := content.get("parts"):
                return self._extract_text_from_parts(parts)
        # Direct parts
        if "parts" in event:
            return self._extract_text_from_parts(event["parts"])
        return None

    def _extract_text_from_content(self, content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, dict) and "parts" in content:
            return self._extract_text_from_parts(content["parts"])
        return str(content)

    def _extract_text_from_parts(self, parts: list) -> str:
        texts = []
        for part in parts:
            if isinstance(part, dict) and "text" in part:
                texts.append(part["text"])
            elif isinstance(part, str):
                texts.append(part)
        return "\n".join(texts)
