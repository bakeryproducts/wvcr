from ..step import Step
from wvcr.services.text_processing_service import explain

class ExplainTextStep(Step):
    name = "explain"
    requires = {"transcript"}
    provides = {"explanation"}

    def execute(self, state, ctx):
        config = ctx.get_stt_config()  # reuse provider selection; explain() handles different config types
        transcript = state.get("transcript")
        explanation = explain(transcript, config, thing=state.get('thing'))
        state.set("explanation", explanation)
