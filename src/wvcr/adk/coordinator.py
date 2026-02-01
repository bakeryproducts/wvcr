from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from google.adk.planners import BuiltInPlanner
from google.genai import types

from .models import GEMINI_3_FLASH
from .search_agent import search_agent
from .code_agent import code_agent
from .memory_agent import memory_agent
from .tools import memory_toolset


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
- search_agent: subagent for web search, news, facts
- code_agent: subagent for calculations, data analysis, code
- memory_toolset: read/write/search personal notes knowledge base vault

Delegate to the right specialist. Can use multiple.
Synthesize results into a clear response.
Always respond in Russian, be concise
""",
    tools=[
        AgentTool(agent=search_agent),
        AgentTool(agent=code_agent),
        # AgentTool(agent=memory_agent),
        memory_toolset,
    ],
)
