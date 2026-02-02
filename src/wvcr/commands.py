from enum import Enum
from typing import Callable, Dict, Any
from dataclasses import dataclass


class Command(str, Enum):
    """Available WVCR commands."""

    TRANSCRIBE = "transcribe"
    TRANSCRIBE_URL = "transcribe-url"
    EXPLAIN = "explain"
    VOICEOVER = "voiceover"
    RESEARCH = "research"
    AGENTIC = "agentic"
    # Daemon-specific
    PING = "ping"
    SHUTDOWN = "shutdown"


@dataclass
class CommandSpec:
    """Specification for a command."""

    name: Command
    description: str
    args: list[str]  # Required/optional argument names
    pipeline_mode: str | None = None  # Class name if applicable


# Command registry with metadata
COMMAND_REGISTRY: Dict[Command, CommandSpec] = {
    Command.TRANSCRIBE: CommandSpec(
        name=Command.TRANSCRIBE,
        description="Record and transcribe audio",
        args=["language", "provider"],
        pipeline_mode="TranscribePipelineMode",
    ),
    Command.TRANSCRIBE_URL: CommandSpec(
        name=Command.TRANSCRIBE_URL,
        description="Transcribe audio from URL (YouTube, etc)",
        args=["url", "language", "provider"],
        pipeline_mode="TranscribeUrlPipelineMode",
    ),
    Command.EXPLAIN: CommandSpec(
        name=Command.EXPLAIN,
        description="Record a question and explain something",
        args=["instruction", "thing", "language", "provider"],
        pipeline_mode="ExplainPipelineMode",
    ),
    Command.VOICEOVER: CommandSpec(
        name=Command.VOICEOVER,
        description="Generate voiceover from clipboard text",
        args=["language", "provider"],
        pipeline_mode="VoiceoverPipelineMode",
    ),
    Command.RESEARCH: CommandSpec(
        name=Command.RESEARCH,
        description="Run research pipeline using ADK agents",
        args=["instruction", "language", "provider"],
        pipeline_mode="ResearchPipelineMode",
    ),
    Command.AGENTIC: CommandSpec(
        name=Command.AGENTIC,
        description="Run agentic pipeline via external ADK API Server",
        args=["session_id", "app_name", "instruction", "files", "language"],
        pipeline_mode="AgenticPipelineMode",
    ),
    Command.PING: CommandSpec(
        name=Command.PING,
        description="Ping daemon to check if alive",
        args=[],
        pipeline_mode=None,
    ),
    Command.SHUTDOWN: CommandSpec(
        name=Command.SHUTDOWN,
        description="Shutdown daemon",
        args=[],
        pipeline_mode=None,
    ),
}


def get_user_commands() -> list[Command]:
    """Get user-facing commands (exclude daemon control commands)."""
    return [
        Command.TRANSCRIBE,
        Command.TRANSCRIBE_URL,
        Command.EXPLAIN,
        Command.VOICEOVER,
        Command.RESEARCH,
        Command.AGENTIC,
        Command.PING,
    ]


def get_all_command_names() -> list[str]:
    """Get all command names as strings."""
    return [cmd.value for cmd in Command]


def get_user_command_names() -> list[str]:
    """Get user-facing command names as strings."""
    return [cmd.value for cmd in get_user_commands()]
