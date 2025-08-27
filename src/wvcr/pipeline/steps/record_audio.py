from ..step import Step

class RecordAudio(Step):
    name = "record"
    requires = {"audio_file", "audio_params"}
    provides = {"raw_audio_meta"}

    def execute(self, state, ctx):
        recorder = ctx.services["recorder"]  # existing IPCVoiceRecorder instance
        audio_file = state.get("audio_file")
        fmt = state.get("audio_params")["format"]
        recorder.record(audio_file, format=fmt)
        # TODO: gather meta (duration, size)
        meta = {"size_bytes": audio_file.stat().st_size if audio_file.exists() else 0}
        state.set("raw_audio_meta", meta)
