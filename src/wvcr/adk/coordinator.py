from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from google.adk.planners import BuiltInPlanner
from google.genai import types

from .models import GEMINI_3_FLASH
from .search_agent import search_agent
from .code_agent import code_agent


coordinator_planner = BuiltInPlanner(
    thinking_config=types.ThinkingConfig(
        thinking_level=types.ThinkingLevel.MEDIUM,
    )
)
# coordinator_config = types.GenerateContentConfigDict()

coordinator = LlmAgent(
    name="coordinator",
    model=GEMINI_3_FLASH,
    planner=coordinator_planner,
    # generate_content_config=coordinator_config,
    description="Main agent that coordinates between other specialist agents.",
    instruction="""You are a coordinator. Analyze queries and delegate to specialists.

Tools:
- search_agent: web search, news, facts
- code_agent: calculations, data analysis, code

Delegate to the right specialist. Can use multiple.
Synthesize results into a clear response.
Always respond in Russian, be concise
""",
    tools=[AgentTool(agent=search_agent), AgentTool(agent=code_agent)],
)
