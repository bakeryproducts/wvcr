from ..step import Step, StepError


class RecordAudio(Step):
    name = "record"
    requires = {"audio_file", "audio_params"}
    provides = {"raw_audio_meta"}

    def execute(self, state, ctx):
        recorder = ctx.services["recorder"]  # existing IPCVoiceRecorder instance
        audio_file = state.get("audio_file")
        params = state.get("audio_params")
        fmt = params["format"]
        vad = params.get("vad")
        _, duration = recorder.record(audio_file, format=fmt, vad=vad)

        if duration < 3:
            raise StepError(
                f"Recording too short ({duration:.1f}s < 3s), likely accidental - cancelled",
                recoverable=False,
            )

        meta = {
            "size_bytes": audio_file.stat().st_size if audio_file.exists() else 0,
            "duration": duration,
        }
        state.set("raw_audio_meta", meta)
