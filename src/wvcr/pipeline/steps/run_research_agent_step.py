from ..step import Step
from wvcr.adk import run_research

from loguru import logger


class RunResearchAgentStep(Step):
    name = "run_research_agent"
    # requires = {}
    provides = {"research_result"}

    def execute(self, state, ctx):
        # Try audio first, fallback to text
        audio_part = state.get("audio_part") if "audio_part" in state else None
        query = state.get("transcript") if "transcript" in state else None
        if not query and not audio_part:
            raise ValueError("RunResearchAgentStep requires either 'transcript' or 'audio_part' in state")

        result = run_research(query=query, audio_part=audio_part)
        state.set("research_result", result)
        logger.info(f"Research completed, result length: {len(result)} chars")
