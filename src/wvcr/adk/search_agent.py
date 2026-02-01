from google.adk.agents import LlmAgent
from google.adk.tools.google_search_tool import google_search
from google.adk.planners import BuiltInPlanner
from google.genai import types

from .models import GEMINI_3_FLASH


search_planner = BuiltInPlanner(
    thinking_config=types.ThinkingConfig(
        thinking_level=types.ThinkingLevel.LOW,
    )
)
# search_config = types.GenerateContentConfigDict()

search_agent = LlmAgent(
    name="search_agent",
    model=GEMINI_3_FLASH,
    planner=search_planner,
    # generate_content_config=search_config,
    description="Performs web research using Google Search to find up-to-date information.",
    instruction="""You are a web research specialist. Your job is to:
1. Search the web for relevant, up-to-date information
2. Analyze and synthesize findings from multiple sources
3. Provide clear, factual answers with sources when available

Always cite your sources. If you're unsure about something, say so.
Respond in the same language as the user's query.""",
    tools=[google_search],
)
