"""Сервис для обработки текста через OpenAI API."""

import re
import pyperclip
from loguru import logger
from wvcr.config import OAIConfig
from wvcr.messages import Messages, get_prev_files, load_previous_responses
from wvcr.config import OUTPUT


def answer_question(transcript: str, config: OAIConfig) -> str:
    """Ответить на вопрос из транскрипции."""
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


def explain_text(transcript: str, config: OAIConfig) -> str:
    """Объяснить текст в контексте содержимого буфера обмена."""
    logger.info(f"Explaining with context: {transcript}")

    messages = Messages()
    messages.clear_history()
    clipboard_content = pyperclip.paste()
    
    messages.add_message(
        "system", 
        "You are a assistant. Please use the following context and proceed to user's question. "
        "Be concise and brief."
    )
    messages.add_message("user", transcript)
    messages.add_message("user", clipboard_content)

    messages._print()

    try:
        response = config.client.chat.completions.create(
            model=config.GPT_MODEL,
            temperature=config.temperature,
            messages=messages.get_messages()
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.exception(f"Could not process explanation: {str(e)}")
        return transcript


def detect_mode_from_text(transcript: str) -> str:
    """Определить режим обработки на основе ключевых слов в тексте."""
    lower_transcript = transcript.lower()
    lower_transcript = re.sub(r'[^\w\s]', '', lower_transcript)
    
    answer_keywords = ["режим вопрос"]
    explain_keywords = ["режим объяснение"]
    
    if any(keyword in lower_transcript for keyword in answer_keywords):
        return "answer"
    elif any(keyword in lower_transcript for keyword in explain_keywords):
        return "explain"

    return "transcribe"
