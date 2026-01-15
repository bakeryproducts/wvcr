from datetime import datetime

from google.genai import types
from google.adk.agents import LlmAgent
from google.adk.tools import google_search

from config import AgentConfig, InstructionMode


# Instructions
# Translate input speech from Russian to English.
INSTRUCTION_TRANSLATION = """You are a translator
# Instructions
Translate input speech from English to Russian.
Do not add anything.
You only output is translated input
Do not ask questions, do not provide explanations.
ONLY TRANSLATION"""

INSTRUCTION_SEARCH = f"""You are a agent that help the User with short information notices
Your typical behavior changed to strict and focused, minimal verbosity.

# Instructions
Its very important: concise, brief responses.
ALWAYS answer short, in one sentence until specifically asked to elaborate.
Do not use full sentences. You can answer partially, without repeating context.
Date and time: {datetime.now().strftime("%Y-%m-%d %H:%M, %A")}"""


def create_agent(agent_config: AgentConfig) -> LlmAgent:
    """Create an agent based on the provided configuration."""
    
    # Create speech config
    speech_config = types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=agent_config.voice_name)
        ),
        language_code=agent_config.language_code
    )
    
    # Get instruction based on mode
    if agent_config.instruction_mode == InstructionMode.TRANSLATION:
        instruction = INSTRUCTION_TRANSLATION
    elif agent_config.instruction_mode == InstructionMode.SEARCH:
        instruction = INSTRUCTION_SEARCH
    elif agent_config.instruction_mode == InstructionMode.CUSTOM:
        instruction = agent_config.custom_instruction or "You are a assistant."
    else:
        instruction = "You are an assistant."
    
    # Determine tools
    tools = [google_search] if agent_config.use_google_search else []
    
    return LlmAgent(
        name="agent",
        model=agent_config.model,
        description="Live voice assistant",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            speech_config=speech_config,
        ),
        tools=tools,
    )
