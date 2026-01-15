from omegaconf import DictConfig, OmegaConf
from wvcr.notification_manager import NotificationManager
from wvcr.pipeline import RuntimeContext
from wvcr.ipc import IPCVoiceRecorder
from wvcr.config import OUTPUT, OAIConfig, GeminiConfig


def build_runtime_context(cfg: DictConfig) -> RuntimeContext:
    from wvcr.config.hydra_schemas import ContextConfig
    ctx_cfg: ContextConfig = cfg.context  # type: ignore
    oai_cfg: OAIConfig = OmegaConf.to_object(ctx_cfg.oai)
    gemini_cfg: GeminiConfig = OmegaConf.to_object(ctx_cfg.gemini)
    options = {
        "language": ctx_cfg.language,
        "clipboard": ctx_cfg.clipboard,
        "notify": ctx_cfg.notify,
        "provider": ctx_cfg.provider,
        # audio overrides (flat for now)
        "rate": ctx_cfg.recorder.RATE,
        "channels": ctx_cfg.recorder.CHANNELS,
        "vad": ctx_cfg.recorder.ENABLE_VAD,
        "max_duration": ctx_cfg.recorder.MAX_DURATION,
    }
    runtime = RuntimeContext(
        oai_config=oai_cfg,
        gemini_config=gemini_cfg,
        notifier=NotificationManager(),
        output_dir=OUTPUT,  # TODO: consider honoring cfg.context.output_dir
        options=options,
        services={
            "recorder": IPCVoiceRecorder(config=ctx_cfg.recorder, use_evdev=ctx_cfg.use_evdev),
        },
    )
    return runtime