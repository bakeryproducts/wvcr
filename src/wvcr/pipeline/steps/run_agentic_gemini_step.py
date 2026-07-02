import base64

import requests
from loguru import logger
from google.genai import types

from ..step import Step, StepError

SYSTEM_INSTRUCTION = (
    "You are a helpful assistant answering a spoken question. "
    "Be concise and informative. Start with the most relevant information. "
    "Add more detail only if necessary. "
    "Do not include URLs, links, or citation markers in your answer; "
    "just state the facts in plain prose."
)


class RunAgenticGeminiStep(Step):
    name = "run_agentic_gemini"
    provides = {"agentic_result"}

    def execute(self, state, ctx):
        config = ctx.gemini_config
        if config is None:
            raise StepError("Gemini backend requested but gemini_config is not configured")

        parts = self._build_parts(state)
        if not parts:
            raise StepError(
                "RunAgenticGeminiStep requires 'audio_part', 'instruction', or 'file_parts' in state"
            )

        grounding = ctx.options.get("grounding", True)
        citations = ctx.options.get("citations", True)
        tools = None
        if grounding:
            tools = [types.Tool(google_search=types.GoogleSearch())]

        client = config.get_client()
        logger.info(
            f"Calling Gemini directly (model={config.GPT_MODEL}) with {len(parts)} parts"
            f", grounding={'on' if grounding else 'off'}"
            f", citations={'on' if citations else 'off'}"
        )

        try:
            response = client.models.generate_content(
                model=config.GPT_MODEL,
                config=types.GenerateContentConfig(
                    temperature=config.temperature,
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=tools,
                ),
                contents=parts,
            )
        except Exception as e:
            raise StepError(f"Gemini request failed: {e}")

        text = getattr(response, "text", None) or ""
        if citations:
            text = self._add_citations(response, text)
        text = text.strip()
        state.set("agentic_result", text)
        logger.info(f"Agentic (gemini) completed, result length: {len(text)} chars")

    def _build_parts(self, state) -> list:
        parts = []

        audio_part = state.get("audio_part")
        if audio_part:
            parts.append(audio_part)

        instruction = state.get("instruction")
        if instruction:
            parts.append(types.Part(text=instruction))

        for fp in state.get("file_parts", []):
            inline = fp.get("inlineData", {})
            data = inline.get("data")
            mime_type = inline.get("mimeType")
            if data and mime_type:
                parts.append(
                    types.Part.from_bytes(
                        data=base64.b64decode(data),
                        mime_type=mime_type,
                    )
                )

        return parts

    def _add_citations(self, response, text: str) -> str:
        if not text:
            return text
        try:
            candidate = response.candidates[0]
            meta = candidate.grounding_metadata
            chunks = meta.grounding_chunks or []
        except (AttributeError, IndexError, TypeError):
            return text

        if not chunks:
            return text

        # Collect unique source URLs in order of appearance.
        sources = []
        seen = set()
        for chunk in chunks:
            if not (chunk.web and chunk.web.uri):
                continue
            uri = self._resolve_url(chunk.web.uri)
            if uri in seen:
                continue
            seen.add(uri)
            title = (chunk.web.title or uri).strip()
            sources.append((title, uri))

        if not sources:
            return text

        lines = [f"{i + 1}. [{title}]({uri})" for i, (title, uri) in enumerate(sources)]
        return text + "\n\nSources:\n" + "\n".join(lines)

    @staticmethod
    def _resolve_url(url: str) -> str:
        if "grounding-api-redirect" not in url:
            return url
        try:
            resp = requests.head(url, allow_redirects=True, timeout=5)
            return resp.url or url
        except requests.RequestException:
            return url
