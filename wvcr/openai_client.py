import re
from enum import Enum
from dataclasses import dataclass

import pyperclip
from loguru import logger
from wvcr.config import OAIConfig, OUTPUT
from wvcr.messages import Messages, get_prev_files, load_previous_responses



class ProcessingMode(Enum):
    TRANSCRIBE = "transcribe"
    ANSWER = "answer"
    EXPLAIN = "explain"
    VOICEOVER = "voiceover"

@dataclass
class ProcessingKeywords:
    ANSWER = ["режим вопрос"]
    EXPLAIN = ["режим объяснение"]

# Create directories for all modes
MODE_DIRS = {mode: OUTPUT / mode.value.lower() for mode in ProcessingMode}
for dir in MODE_DIRS.values():
    dir.mkdir(exist_ok=True)


def transcribe(audio_file, config):
    """Transcribe audio file using OpenAI Whisper API."""
    try:
        with open(audio_file, 'rb') as audio:
            transcription = config.client.audio.transcriptions.create(
                model=config.STT_MODEL,
                file=audio
            )
        return transcription.text
    except Exception as e:
        raise Exception(f"Transcription failed: {str(e)}")


def answer_question(transcript, config: OAIConfig):
    """Answer questions found in the transcript."""
    logger.info(f"Answering question: {transcript}")

    messages = Messages()
    try:
        messages.clear_history()
        messages.add_message("system", "You are a helpful assistant. Please answer to the following question. Be concise and informative. Do not use full sentences. Your answer should start with most relevant information. Add more IF NECESSARY after.")

        # preload history
        _prev_answers = get_prev_files(MODE_DIRS[ProcessingMode.ANSWER])
        prev_answers = load_previous_responses(_prev_answers, limit=5)
        _prev_transcripts = get_prev_files(MODE_DIRS[ProcessingMode.TRANSCRIBE], _prev_answers)
        prev_transcripts = load_previous_responses(_prev_transcripts, limit=5)

        if len(prev_answers) != len(prev_transcripts):
            logger.warning("Previous answers and transcripts do not match")
        else:
            for a, t in zip(prev_answers, prev_transcripts):
                messages.add_message("user", t)
                messages.add_message("assistant", a)
                
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

def explain_text(transcript, config: OAIConfig):
    """Explain the transcript in context of clipboard content."""
    logger.info(f"Explaining with context: {transcript}")

    messages = Messages()
    messages.clear_history()
    clipboard_content = pyperclip.paste()
    messages.add_message("system", "You are a assistant. Please use the following context and proceed to user's question. Be concise and brief.")
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


def detect_mode(transcript):
    """Detect processing mode based on keywords in transcript."""
    lower_transcript = transcript.lower()
    lower_transcript = re.sub(r'[^\w\s]', '', lower_transcript)
    
    if any(keyword in lower_transcript for keyword in ProcessingKeywords.ANSWER):
        return ProcessingMode.ANSWER
    elif any(keyword in lower_transcript for keyword in ProcessingKeywords.EXPLAIN):
        return ProcessingMode.EXPLAIN

    return ProcessingMode.TRANSCRIBE


def process_text(text: str, mode: ProcessingMode = None, config: OAIConfig = None):
    """Process text based on specified mode or detect mode from content."""
    if mode is None:
        mode = detect_mode(text)
    logger.debug(f"Processing text with mode: {mode}")
    
    if mode == ProcessingMode.ANSWER:
        return answer_question(text, config), mode
    elif mode == ProcessingMode.EXPLAIN:
        return explain_text(text, config), mode
    return text, mode