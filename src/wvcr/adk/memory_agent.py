from google.adk.agents import LlmAgent

from wvcr.adk.models import GEMINI_3_FLASH
from wvcr.adk.tools import memory_toolset


memory_agent = LlmAgent(
    name="memory_agent",
    model=GEMINI_3_FLASH,
    description="Manages knowledge vault - reads, writes, searches notes.",
    instruction="Manage vault notes. Store and retrieve information.",
    tools=[
        memory_toolset
    ],
)
