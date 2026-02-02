import asyncio
from typing import Optional

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from loguru import logger

from .coordinator import coordinator


# Shared session service (in-memory for now)
_session_service = InMemorySessionService()

APP_NAME = "wvcr_research"


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
    logger.info(f"Starting research with user_id={user_id}, has_query={query is not None}, has_audio={audio_part is not None}")
    
    if query is None and audio_part is None:
        logger.error("No query or audio provided to run_research_async")
        raise ValueError("Either query or audio_part must be provided")

    logger.debug(f"Creating runner for session_id={session_id}")
    runner = Runner(
        agent=coordinator,
        app_name=APP_NAME,
        session_service=_session_service,
    )

    # Create or get session
    if session_id is None:
        logger.debug(f"Creating new session for user_id={user_id}")
        session = await _session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
        )
        session_id = session.id
        logger.info(f"Created new session: {session_id}")
    else:
        logger.debug(f"Using existing session: {session_id}")

    # Build user message content with text or audio
    parts = []
    if audio_part is not None:
        parts.append(audio_part)
        logger.debug("Added audio part to message")
    if query is not None:
        parts.append(types.Part(text=query))
        logger.debug(f"Added text query ({len(query)} chars) to message")

    content = types.Content(
        role="user",
        parts=parts,
    )

    logger.info(f"Running research agent with {len(parts)} parts")
    
    # Run the agent and collect response
    result_parts = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,):
        logger.debug(f"Received event: {event}")
        # Collect text from agent responses
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    result_parts.append(part.text)
                    logger.debug(f"Collected response part: {len(part.text)} chars")

    result = "\n".join(result_parts) if result_parts else "No response from research agent."
    logger.info(f"Research completed: {len(result)} chars, {len(result_parts)} parts")
    return result


def run_research(
    query: str = None,
    audio_part: Optional[types.Part] = None,
    user_id: str = "wvcr_user",
    session_id: Optional[str] = None,
) -> str:
    logger.debug(f"run_research called: query={'...' if query else None}, audio_part={audio_part is not None}, user_id={user_id}")
    try:
        result = asyncio.run(run_research_async(query, audio_part, user_id, session_id))
        logger.debug("run_research completed successfully")
        return result
    except Exception as e:
        logger.error(f"run_research failed: {type(e).__name__}: {e}")
        raise


