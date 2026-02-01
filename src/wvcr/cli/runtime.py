from wvcr.notification_manager import NotificationManager
from wvcr.pipeline import RuntimeContext
from wvcr.ipc import IPCVoiceRecorder
from wvcr.config import OUTPUT
from wvcr.config.simple_config import WVCRConfig, get_default_config
from wvcr.services.tts_service import TTSService


def build_runtime_context(cfg: WVCRConfig | None = None) -> RuntimeContext:
    if cfg is None:
        cfg = get_default_config()
    
    options = {
        "language": cfg.language,
        "clipboard": cfg.clipboard,
        "notify": cfg.notify,
        "provider": cfg.provider,
        # audio overrides (flat for now)
        "rate": cfg.recorder.RATE,
        "channels": cfg.recorder.CHANNELS,
        "format": cfg.recorder.AUDIO_FORMAT,
        "vad": cfg.recorder.ENABLE_VAD,
        "max_duration": cfg.recorder.MAX_DURATION,
        # command-specific args
        "url": cfg.url,
        "instruction": cfg.instruction,
        "thing": cfg.thing,
    }
    runtime = RuntimeContext(
        oai_config=cfg.oai,
        gemini_config=cfg.gemini,
        notifier=NotificationManager(),
        output_dir=OUTPUT,
        options=options,
        services={
            "recorder": IPCVoiceRecorder(config=cfg.recorder, use_evdev=cfg.use_evdev),
            "tts": TTSService(oai_config=cfg.oai, gemini_config=cfg.gemini),
        },
    )
    return runtime