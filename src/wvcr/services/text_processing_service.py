import re
from pathlib import Path
from PIL import Image

from loguru import logger

from wvcr.config import OUTPUT
from wvcr.config import OAIConfig, GeminiConfig
from wvcr.messages import Messages, get_prev_files, load_previous_responses


def answer_question(transcript: str, config: OAIConfig) -> str:
    logger.info(f"Answering question: {transcript}")

    messages = Messages()
    try:
        messages.clear_history()
        messages.add_message(
            "system", 
            "You are a helpful assistant. Please answer to the following question. "
            "Be concise and informative. Do not use full sentences. "
            "Your answer should start with most relevant information. Add more IF NECESSARY after."
        )

        # Загружаем историю
        answer_dir = OUTPUT / "answer"
        transcribe_dir = OUTPUT / "transcribe"
        
        prev_answers_files = get_prev_files(answer_dir)
        prev_answers = load_previous_responses(prev_answers_files, limit=5)
        
        prev_transcripts_files = get_prev_files(transcribe_dir, prev_answers_files)
        prev_transcripts = load_previous_responses(prev_transcripts_files, limit=5)

        if len(prev_answers) != len(prev_transcripts):
            logger.warning("Previous answers and transcripts do not match")
        else:
            for answer, transcript in zip(prev_answers, prev_transcripts):
                messages.add_message("user", transcript)
                messages.add_message("assistant", answer)
                
        messages.add_message("user", transcript)
        messages._print()
        
        response = config.client.chat.completions.create(
            model=config.GPT_MODEL,
            temperature=config.temperature,
            messages=messages.get_messages()
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.exception(f"Could not process question: {str(e)}")
        return transcript


def explain(transcript: str, config: OAIConfig | GeminiConfig, thing) -> str:
    logger.info(f"Explaining with context: {transcript}")
    messages = Messages()
    messages.clear_history()

    messages.add_message(
        "system",
        "You are a assistant. Please use the following context and proceed to user's question. "
        "Be concise and brief."
    )
    if transcript:
        messages.add_message("user", transcript)

    if thing and isinstance(thing, str):
        p = Path(thing)
        if p.exists() and p.is_file():
            suffix = p.suffix.lower()
            try:
                if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                    data = p.read_bytes()
                    messages.add_image(data)
                else:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    if text.strip():
                        messages.add_message("user", text.strip())
            except Exception as e:
                logger.warning(f"Failed to load thing file '{p}': {e}; using literal string")
                messages.add_message("user", thing)
        else:
            messages.add_message("user", thing)
    elif isinstance(thing, Image.Image):
        messages.add_image(thing)


    messages._print()

    if isinstance(config, OAIConfig):
        return explain_oai(messages, config)
    elif isinstance(config, GeminiConfig):
        raise NotImplementedError("GeminiConfig is not supported yet.")
    return ""


def explain_oai(messages, config: OAIConfig) -> str:
    client = config.get_client()

    try:
        response = client.chat.completions.create(
            model=config.EXPLAIN_MODEL,
            # temperature=config.temperature,
            reasoning_effort='minimal',
            messages=messages.to_oai()  # changed: include image parts in proper format
        )
        logger.debug(f"Response usage: {response.usage}")
        return response.choices[0].message.content
    except Exception as e:
        logger.exception(f"Could not process explanation: {str(e)}")
        return ""


def detect_mode_from_text(transcript: str) -> str:
    lower_transcript = transcript.lower()
    lower_transcript = re.sub(r'[^\w\s]', '', lower_transcript)
    
    answer_keywords = ["режим вопрос"]
    explain_keywords = ["режим объяснение"]
    
    if any(keyword in lower_transcript for keyword in answer_keywords):
        return "answer"
    elif any(keyword in lower_transcript for keyword in explain_keywords):
        return "explain"

    return "transcribe"