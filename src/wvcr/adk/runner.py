import asyncio
from typing import Optional

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .coordinator import coordinator


# Shared session service (in-memory for now)
_session_service = InMemorySessionService()


async def run_research_async(
    query: str = None,
    audio_part: Optional[types.Part] = None,
    user_id: str = "wvcr_user",
    session_id: Optional[str] = None,
) -> str:
    """Execute research query through the coordinator agent.

    Args:
        query: The user's research question (text)
        audio_part: Optional audio Part to send directly to ADK without transcription
        user_id: User identifier for session management
        session_id: Optional existing session ID to continue conversation

    Returns:
        The research result as a string
    """
    if query is None and audio_part is None:
        raise ValueError("Either query or audio_part must be provided")

    runner = Runner(
        agent=coordinator,
        app_name="wvcr_research",
        session_service=_session_service,
    )

    # Create or get session
    if session_id is None:
        session = await _session_service.create_session(
            app_name="wvcr_research",
            user_id=user_id,
        )
        session_id = session.id

    # Build user message content with text or audio
    parts = []
    if audio_part is not None:
        parts.append(audio_part)
    if query is not None:
        parts.append(types.Part(text=query))

    content = types.Content(
        role="user",
        parts=parts,
    )

    # Run the agent and collect response
    result_parts = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        # Collect text from agent responses
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    result_parts.append(part.text)

    return (
        "\n".join(result_parts) if result_parts else "No response from research agent."
    )


def run_research(
    query: str = None,
    audio_part: Optional[types.Part] = None,
    user_id: str = "wvcr_user",
    session_id: Optional[str] = None,
) -> str:
    return asyncio.run(run_research_async(query, audio_part, user_id, session_id))
