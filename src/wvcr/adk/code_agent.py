from google.adk.agents import LlmAgent
from google.adk.code_executors import BuiltInCodeExecutor

from .models import GEMINI_3_FLASH


code_agent = LlmAgent(
    name="code_agent",
    model=GEMINI_3_FLASH,
    description="Executes Python code for calculations, data analysis, and processing.",
    instruction="""You are a code execution specialist. Your job is to:
1. Write and execute Python code for calculations
2. Perform data analysis and processing
3. Return clear results with explanations

When given a task requiring computation, write and execute the code.
Respond in the same language as the user's query.""",
    code_executor=BuiltInCodeExecutor(),
)
