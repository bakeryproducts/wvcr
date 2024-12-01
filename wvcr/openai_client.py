import re
import os
import pyperclip
from enum import Enum
from dataclasses import dataclass

from loguru import logger

from openai import OpenAI
from wvcr.config import OAIConfig

# Initialize config and OpenAI client once
config = OAIConfig()
client = OpenAI(api_key=config.API_KEY)

class ProcessingMode(Enum):
    TRANSCRIBE = "transcribe"
    CORRECT = "correct"
    ANSWER = "answer"
    EXPLAIN = "explain"

@dataclass
class ProcessingKeywords:
    CORRECT = ["режим корректировка"]
    ANSWER = ["режим вопрос"]
    EXPLAIN = ["режим объяснение"]


def transcribe(audio_file):
    """Transcribe audio file using OpenAI Whisper API."""
    try:
        with open(audio_file, 'rb') as audio:
            transcription = client.audio.transcriptions.create(
                model=config.STT_MODEL,
                file=audio
            )
        return transcription.text
    except Exception as e:
        raise Exception(f"Transcription failed: {str(e)}")


def correct_transcript(transcript, temperature=0.3):
    logger.info(f"Correcting transcript: {transcript}")

    try:
        response = client.chat.completions.create(
            model=config.GPT_MODEL,
            temperature=temperature,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Please correct any grammar or spelling mistakes in the following transcript while preserving its original meaning:"
                },
                {
                    "role": "user",
                    "content": transcript
                }
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.exception(f"Could not process question: {str(e)}")
        return transcript


def answer_question(transcript, temperature=0.0):
    """Answer questions found in the transcript."""
    logger.info(f"Answering question: {transcript}")
    try:
        response = client.chat.completions.create(
            model=config.GPT_MODEL,
            temperature=temperature,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Please answer to the following question. Be concise and informative. Do not use full sentences"
                },
                {
                    "role": "user",
                    "content": transcript
                }
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.exception(f"Could not process question: {str(e)}")
        return transcript

def explain_text(transcript, temperature=0.0):
    """Explain the transcript in context of clipboard content."""
    logger.info(f"Explaining with context: {transcript}")
    try:
        clipboard_content = pyperclip.paste()
        response = client.chat.completions.create(
            model=config.GPT_MODEL,
            temperature=temperature,
            messages=[
                {
                    "role": "system",
                    "content": "You are a assistant. Please use the following context and proceed to user's question:"
                },
                {
                    "role": "user",
                    "content": clipboard_content
                },
                {
                    "role": "user",
                    "content": transcript
                }
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.exception(f"Could not process explanation: {str(e)}")
        return transcript

def detect_mode(transcript):
    """Detect processing mode based on keywords in transcript."""
    lower_transcript = transcript.lower()
    lower_transcript = re.sub(r'[^\w\s]', '', lower_transcript)
    
    if any(keyword in lower_transcript for keyword in ProcessingKeywords.CORRECT):
        return ProcessingMode.CORRECT
    elif any(keyword in lower_transcript for keyword in ProcessingKeywords.ANSWER):
        return ProcessingMode.ANSWER
    elif any(keyword in lower_transcript for keyword in ProcessingKeywords.EXPLAIN):
        return ProcessingMode.EXPLAIN

    return ProcessingMode.TRANSCRIBE

def process_text(text: str, mode: ProcessingMode = None) -> str:
    """Process text based on specified mode or detect mode from content."""
    if mode is None:
        mode = detect_mode(text)
    logger.debug(f"Processing text with mode: {mode}")
    
    if mode == ProcessingMode.CORRECT:
        return correct_transcript(text), mode
    elif mode == ProcessingMode.ANSWER:
        return answer_question(text), mode
    elif mode == ProcessingMode.EXPLAIN:
        return explain_text(text), mode
    return text, mode