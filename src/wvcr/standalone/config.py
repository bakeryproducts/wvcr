from enum import Enum
from dataclasses import dataclass
from typing import Optional


class StreamingMode(Enum):
    TURN_BASED = "turn_based"
    SIMULTANEOUS = "simultaneous"


class InstructionMode(Enum):
    TRANSLATION = "translation"
    SEARCH = "search"
    CUSTOM = "custom"


@dataclass
class SimultaneousConfig:
    activity_restart_interval: int = 100  # Number of audio chunks before restarting activity
    buffer_management: bool = True
    no_interruption: bool = True


@dataclass
class AgentConfig:
    instruction_mode: InstructionMode = InstructionMode.TRANSLATION
    custom_instruction: Optional[str] = None
    language_code: str = "ru-RU"
    voice_name: str = "Orus"
    model: str = "gemini-live-2.5-flash-preview"
    use_google_search: bool = False


@dataclass
class StreamingConfig:
    mode: StreamingMode = StreamingMode.TURN_BASED
    simultaneous_config: Optional[SimultaneousConfig] = None
    enable_vad: bool = True
    # vad_aggressiveness: int = 2  # 0-3, higher = more aggressive
    # IPC audio defaults
    socket_path: str = "/tmp/adk_audio.sock"
    ipc_rcvbuf_bytes: int = 4_194_304
    ipc_sndbuf_bytes: int = 4_194_304
    ipc_max_frames: int = 128
    # Capture timing defaults
    rate: int = 16000
    chunk_ms: int = 20
    batch_ms: int = 140
    
    def __post_init__(self):
        if self.mode == StreamingMode.SIMULTANEOUS and self.simultaneous_config is None:
            self.simultaneous_config = SimultaneousConfig()


@dataclass 
class AppConfig:
    streaming: StreamingConfig
    agent: AgentConfig
    
    @classmethod
    def create_translation(cls, language_code: str = "ru-RU", voice_name: str = "Orus"):
                          
        return cls(
            streaming=StreamingConfig(
                mode=StreamingMode.SIMULTANEOUS,
                simultaneous_config=SimultaneousConfig(),
                enable_vad=True,
                # enable_vad=False,
            ),
            agent=AgentConfig(
                instruction_mode=InstructionMode.TRANSLATION,
                language_code=language_code,
                voice_name=voice_name
            )
        )
    
    @classmethod
    def create_search(cls, language_code: str = "en-US", voice_name: str = "Algenib"):
        return cls(
            streaming=StreamingConfig(mode=StreamingMode.TURN_BASED,
                                      enable_vad=True),
            agent=AgentConfig(
                instruction_mode=InstructionMode.SEARCH,
                language_code=language_code,
                voice_name=voice_name,
                use_google_search=True
            )
        )
