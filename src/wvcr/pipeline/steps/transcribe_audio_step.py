from ..step import Step
from wvcr.services.transcription_service import transcribe_audio

class TranscribeAudioStep(Step):
    name = "transcribe"
    requires = {"audio_file"}
    provides = {"transcript"}

    def execute(self, state, ctx):
        config = ctx.get_stt_config()
        language = ctx.options.get("language", "ru")
        transcript = transcribe_audio(state.get("audio_file"), config, language=language)
        state.set("transcript", transcript)
